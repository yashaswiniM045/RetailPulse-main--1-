from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from src.models.audit_log import AuditLog
from src.models.customer import Customer
from src.models.data_quality import DataQualityIssue, DataQualityIssueEvent, ReconciliationRun
from src.models.inventory import Inventory, InventoryMovement, InventoryMovementType
from src.models.product import Product, ProductStatus
from src.models.reporting import ReportHistory
from src.models.sale import Sale, SaleItem
from src.models.user import User
from src.schemas.data_quality import IssueStatusUpdate
from src.services.audit_service import AuditAction, create_audit_log

UNRESOLVED_STATUSES = ("Open", "Investigating")
CHECKS = (
	("sale_stock", "Sale stock availability", "sales"),
	("inventory_ledger", "Inventory and movement ledger", "inventory"),
	("sales_references", "Sales product and customer references", "sales"),
	("product_integrity", "Product SKU and required fields", "products"),
	("customer_integrity", "Customer required fields", "customers"),
	("sale_totals", "Sales totals and reporting data", "reports"),
)


def _finding(
	*,
	check_key: str,
	issue_type: str,
	severity: str,
	module: str,
	record_type: str,
	record_id: int | str,
	record_name: str | None,
	description: str,
	details: dict[str, Any] | None = None,
) -> dict[str, Any]:
	return {
		"checkKey": check_key,
		"fingerprint": f"{issue_type}:{record_type.lower()}:{record_id}",
		"issueType": issue_type,
		"severity": severity,
		"module": module,
		"recordType": record_type,
		"recordId": str(record_id),
		"recordName": record_name,
		"description": description,
		"details": details or {},
	}


def _check_sale_stock(db: Session, company_id: int, sale_ids: set[int] | None = None) -> list[dict[str, Any]]:
	statement = (
		select(Sale, SaleItem, Product)
		.join(SaleItem, SaleItem.sale_id == Sale.id)
		.outerjoin(Product, and_(Product.id == SaleItem.product_id, Product.company_id == company_id))
		.where(Sale.company_id == company_id)
	)
	if sale_ids is not None:
		statement = statement.where(Sale.id.in_(sale_ids))
	sales = db.execute(statement.order_by(Sale.id, SaleItem.id)).all()
	movements_by_invoice_product: dict[tuple[str, int], list[InventoryMovement]] = defaultdict(list)
	product_ids = {product.id for _, _, product in sales if product is not None}
	if product_ids:
		movement_statement = (
			select(InventoryMovement, Product)
			.join(Inventory, Inventory.id == InventoryMovement.inventory_id)
			.join(Product, Product.id == Inventory.product_id)
			.where(
				Inventory.company_id == company_id,
				Product.id.in_(product_ids),
				InventoryMovement.movement_type == InventoryMovementType.SALE,
			)
			.order_by(InventoryMovement.id)
		)
		for movement, product in db.execute(movement_statement).all():
			invoice = movement.reason.removeprefix("Sale ").strip()
			movements_by_invoice_product[(invoice, product.id)].append(movement)

	findings = []
	used_movement_ids: set[int] = set()
	for sale, item, product in sales:
		if product is None or product.company_id != company_id:
			continue
		candidates = movements_by_invoice_product.get((sale.invoice_number, product.id), [])
		movement = next((candidate for candidate in candidates if candidate.id not in used_movement_ids), None)
		if movement is None:
			if item.quantity > 0:
				findings.append(
					_finding(
						check_key="sale_stock",
						issue_type="sale_missing_stock_movement",
						severity="warning",
						module="Sales / Inventory",
						record_type="Sale",
						record_id=sale.id,
						record_name=sale.invoice_number,
						description=f"Sale item for {product.name} has no matching stock movement.",
						details={"saleId": sale.id, "productId": product.id, "productName": product.name, "quantitySold": item.quantity},
					)
				)
			continue
		used_movement_ids.add(movement.id)
		movement_quantity = abs(movement.quantity_changed)
		if movement_quantity > movement.previous_quantity or movement.updated_quantity < 0:
			findings.append(
				_finding(
					check_key="sale_stock",
					issue_type="sale_exceeds_available_stock",
					severity="error",
					module="Sales / Inventory",
					record_type="Sale",
					record_id=sale.id,
					record_name=sale.invoice_number,
					description=f"Sale of {movement_quantity} {product.name} units exceeded the {movement.previous_quantity} units recorded before the sale.",
					details={
						"saleId": sale.id,
						"saleInvoice": sale.invoice_number,
						"productId": product.id,
						"productName": product.name,
						"movementId": movement.id,
						"quantitySold": movement_quantity,
						"availableBeforeSale": movement.previous_quantity,
						"currentQuantity": movement.updated_quantity,
						"difference": max(movement_quantity - movement.previous_quantity, 0),
					},
				)
			)
		if movement_quantity != item.quantity:
			findings.append(
				_finding(
					check_key="sale_stock",
					issue_type="sale_movement_quantity_mismatch",
					severity="error",
					module="Sales / Inventory",
					record_type="Sale",
					record_id=sale.id,
					record_name=sale.invoice_number,
					description=f"Sale item quantity ({item.quantity}) does not match its stock movement ({movement_quantity}).",
					details={"saleId": sale.id, "productId": product.id, "productName": product.name, "quantitySold": item.quantity, "movementQuantity": movement_quantity, "movementId": movement.id},
				)
			)
	return findings


def _check_inventory_ledger(db: Session, company_id: int, product_ids: set[int] | None = None) -> list[dict[str, Any]]:
	statement = (
		select(Inventory, Product)
		.join(Product, and_(Product.id == Inventory.product_id, Product.company_id == company_id))
		.where(Inventory.company_id == company_id)
	)
	if product_ids is not None:
		statement = statement.where(Product.id.in_(product_ids))
	findings = []
	inventory_rows = db.execute(statement).all()
	inventory_ids = [inventory.id for inventory, _ in inventory_rows]
	movements_by_inventory: dict[int, list[InventoryMovement]] = defaultdict(list)
	if inventory_ids:
		all_movements = db.scalars(
			select(InventoryMovement)
			.where(InventoryMovement.inventory_id.in_(inventory_ids))
			.order_by(InventoryMovement.created_at, InventoryMovement.id)
		).all()
		for movement in all_movements:
			movements_by_inventory[movement.inventory_id].append(movement)
	for inventory, product in inventory_rows:
		if product.stock_quantity != inventory.current_stock:
			findings.append(
				_finding(
					check_key="inventory_ledger",
					issue_type="product_inventory_quantity_mismatch",
					severity="error",
					module="Inventory / Products",
					record_type="Product",
					record_id=product.id,
					record_name=product.name,
					description=f"Product stock ({product.stock_quantity}) differs from inventory current stock ({inventory.current_stock}).",
					details={"productId": product.id, "productName": product.name, "currentQuantity": inventory.current_stock, "productQuantity": product.stock_quantity, "difference": product.stock_quantity - inventory.current_stock},
				)
			)
		movements = movements_by_inventory.get(inventory.id, [])
		previous_updated = None
		for movement in movements:
			expected_updated = movement.previous_quantity + movement.quantity_changed
			is_invalid = movement.updated_quantity != expected_updated
			breaks_chain = previous_updated is not None and movement.previous_quantity != previous_updated
			if is_invalid or breaks_chain:
				expected_previous = previous_updated if breaks_chain else movement.previous_quantity
				findings.append(
					_finding(
						check_key="inventory_ledger",
						issue_type="stock_movement_inconsistent",
						severity="error",
						module="Inventory",
						record_type="Stock Movement",
						record_id=movement.id,
						record_name=product.name,
						description=f"Stock movement {movement.id} has inconsistent previous, changed, and updated quantities.",
						details={
							"productId": product.id,
							"productName": product.name,
							"inventoryId": inventory.id,
							"movementId": movement.id,
							"movementType": movement.movement_type.value,
							"previousQuantity": movement.previous_quantity,
							"expectedPreviousQuantity": expected_previous,
							"quantityChanged": movement.quantity_changed,
							"updatedQuantity": movement.updated_quantity,
							"expectedQuantity": expected_updated,
							"currentQuantity": inventory.current_stock,
							"difference": movement.updated_quantity - expected_updated,
							"reason": movement.reason,
						},
					)
				)
			previous_updated = movement.updated_quantity
		if movements and movements[-1].updated_quantity != inventory.current_stock:
			latest = movements[-1]
			findings.append(
				_finding(
					check_key="inventory_ledger",
					issue_type="inventory_movement_balance_mismatch",
					severity="error",
					module="Inventory",
					record_type="Product",
					record_id=product.id,
					record_name=product.name,
					description=f"Inventory is {inventory.current_stock}, but the latest stock movement records {latest.updated_quantity}.",
					details={"productId": product.id, "productName": product.name, "inventoryId": inventory.id, "currentQuantity": inventory.current_stock, "expectedQuantity": latest.updated_quantity, "difference": inventory.current_stock - latest.updated_quantity, "movementId": latest.id},
				)
			)
	return findings


def _check_sales_references(
	db: Session,
	company_id: int,
	sale_ids: set[int] | None = None,
	product_ids: set[int] | None = None,
	customer_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
	statement = (
		select(Sale, SaleItem, Product)
		.outerjoin(SaleItem, SaleItem.sale_id == Sale.id)
		.outerjoin(Product, and_(Product.id == SaleItem.product_id, Product.company_id == company_id))
		.where(Sale.company_id == company_id)
	)
	if sale_ids is not None:
		statement = statement.where(Sale.id.in_(sale_ids))
	if product_ids is not None:
		statement = statement.where(SaleItem.product_id.in_(product_ids))
	if customer_ids is not None:
		statement = statement.where(Sale.customer_id.in_(customer_ids))
	sale_rows = db.execute(statement).all()
	referenced_customer_ids = {sale.customer_id for sale, _, _ in sale_rows if sale.customer_id is not None}
	customers_by_id = {
		customer.id: customer
		for customer in db.scalars(select(Customer).where(Customer.company_id == company_id, Customer.id.in_(referenced_customer_ids))).all()
	} if referenced_customer_ids else {}
	findings = []
	for sale, item, product in sale_rows:
		if item is not None and (product is None or product.company_id != company_id):
			findings.append(
				_finding(check_key="sales_references", issue_type="sale_invalid_product", severity="error", module="Sales / Products", record_type="Sale", record_id=sale.id, record_name=sale.invoice_number, description="Sale references a missing product or a product owned by another company.", details={"saleId": sale.id, "productId": item.product_id})
			)
		elif product is not None and product.status == ProductStatus.INACTIVE:
			findings.append(
				_finding(check_key="sales_references", issue_type="sale_inactive_product", severity="warning", module="Sales / Products", record_type="Sale", record_id=sale.id, record_name=sale.invoice_number, description=f"Sale references inactive product {product.name}.", details={"saleId": sale.id, "productId": product.id, "productName": product.name})
			)
		customer = customers_by_id.get(sale.customer_id) if sale.customer_id else None
		if sale.customer_id and (customer is None or customer.company_id != company_id or customer.is_deleted):
			findings.append(
				_finding(check_key="sales_references", issue_type="sale_invalid_customer", severity="error", module="Sales / Customers", record_type="Sale", record_id=sale.id, record_name=sale.invoice_number, description="Sale references a missing, deleted, or different-company customer.", details={"saleId": sale.id, "customerId": sale.customer_id, "customerName": sale.customer_name})
			)
		elif customer is not None and customer.status.value == "inactive":
			findings.append(
				_finding(check_key="sales_references", issue_type="sale_inactive_customer", severity="warning", module="Sales / Customers", record_type="Sale", record_id=sale.id, record_name=sale.invoice_number, description=f"Sale references inactive customer {customer.full_name}.", details={"saleId": sale.id, "customerId": customer.id, "customerName": customer.full_name})
			)
	return findings


def _check_products(db: Session, company_id: int, product_ids: set[int] | None = None) -> list[dict[str, Any]]:
	statement = select(Product).where(Product.company_id == company_id)
	if product_ids is not None:
		statement = statement.where(Product.id.in_(product_ids))
	products = db.scalars(statement.order_by(Product.id)).all()
	findings = []
	by_sku: dict[str, list[Product]] = defaultdict(list)
	for product in products:
		sku = (product.sku or "").strip().casefold()
		if not product.name.strip() or not sku:
			missing = [field for field, value in (("name", product.name), ("SKU", product.sku)) if not (value or "").strip()]
			findings.append(
				_finding(check_key="product_integrity", issue_type="product_required_field_missing", severity="error", module="Products", record_type="Product", record_id=product.id, record_name=product.name or product.sku, description=f"Product is missing mandatory information: {', '.join(missing)}.", details={"productId": product.id, "missingFields": missing})
			)
		if sku:
			by_sku[sku].append(product)
	for sku, duplicates in by_sku.items():
		if len(duplicates) < 2:
			continue
		product_ids_found = sorted(product.id for product in duplicates)
		for product in duplicates:
			findings.append(
				_finding(check_key="product_integrity", issue_type="duplicate_product_sku", severity="error", module="Products", record_type="Product", record_id=product.id, record_name=product.name, description=f"SKU '{product.sku}' is duplicated within this company.", details={"productId": product.id, "productName": product.name, "sku": sku, "affectedProductIds": product_ids_found})
			)
	return findings


def _check_customers(db: Session, company_id: int, customer_ids: set[int] | None = None) -> list[dict[str, Any]]:
	statement = select(Customer).where(Customer.company_id == company_id, Customer.is_deleted.is_(False))
	if customer_ids is not None:
		statement = statement.where(Customer.id.in_(customer_ids))
	customers = db.scalars(statement).all()
	findings = []
	for customer in customers:
		missing = [field for field, value in (("name", customer.full_name), ("email", customer.email), ("phone", customer.phone_number)) if not (value or "").strip()]
		if missing:
			findings.append(
				_finding(check_key="customer_integrity", issue_type="customer_required_field_missing", severity="error", module="Customers", record_type="Customer", record_id=customer.id, record_name=customer.full_name, description=f"Customer is missing mandatory information: {', '.join(missing)}.", details={"customerId": customer.id, "missingFields": missing})
			)
	return findings


def _check_sale_totals(db: Session, company_id: int, sale_ids: set[int] | None = None) -> list[dict[str, Any]]:
	statement = (
		select(Sale.id, Sale.invoice_number, Sale.total_amount, func.coalesce(func.sum(SaleItem.total), 0))
		.outerjoin(SaleItem, SaleItem.sale_id == Sale.id)
		.where(Sale.company_id == company_id)
		.group_by(Sale.id)
	)
	if sale_ids is not None:
		statement = statement.where(Sale.id.in_(sale_ids))
	findings = []
	for sale_id, invoice, reported_total, transaction_total in db.execute(statement).all():
		reported = float(reported_total or 0)
		actual = float(transaction_total or 0)
		if abs(reported - actual) > 0.01:
			findings.append(
				_finding(check_key="sale_totals", issue_type="report_total_mismatch", severity="error", module="Sales / Reports", record_type="Sale", record_id=sale_id, record_name=invoice, description=f"Sale total ({reported:.2f}) differs from its line-item total ({actual:.2f}).", details={"saleId": sale_id, "invoiceNumber": invoice, "reportedTotal": reported, "transactionTotal": actual, "difference": round(reported - actual, 2)})
			)
	return findings


def _count_records(db: Session, company_id: int) -> int:
	counts = (
		db.scalar(select(func.count(Sale.id)).where(Sale.company_id == company_id)) or 0,
		db.scalar(select(func.count(Product.id)).where(Product.company_id == company_id)) or 0,
		db.scalar(select(func.count(Customer.id)).where(Customer.company_id == company_id)) or 0,
		db.scalar(select(func.count(Inventory.id)).where(Inventory.company_id == company_id)) or 0,
		db.scalar(select(func.count(InventoryMovement.id)).join(Inventory, Inventory.id == InventoryMovement.inventory_id).where(Inventory.company_id == company_id)) or 0,
		db.scalar(select(func.count(ReportHistory.id)).where(ReportHistory.company_id == company_id)) or 0,
	)
	return int(sum(counts))


def _write_issue_event(
	db: Session,
	issue: DataQualityIssue,
	*,
	previous_status: str,
	new_status: str,
	user: User | None,
	note: str | None,
	request: Request | None,
) -> None:
	db.add(
		DataQualityIssueEvent(
			company_id=issue.company_id,
			issue_id=issue.id,
			changed_by_id=user.id if user else None,
			changed_by_name=user.name if user else "Reconciliation",
			previous_status=previous_status,
			new_status=new_status,
			note=note,
		)
	)
	create_audit_log(
		db,
		company_id=issue.company_id,
		user_id=user.id if user else None,
		performed_by=user.name if user else "Reconciliation",
		entity_type="Data Quality Issue",
		resource_id=issue.id,
		entity_name=issue.record_name or issue.record_id,
		action=AuditAction.DATA_QUALITY_ISSUE_STATUS_CHANGED,
		request=request,
		description=note or f"Issue status changed from {previous_status} to {new_status}.",
		before_values={"status": previous_status},
		after_values={"status": new_status, "resolutionNote": note},
	)


def _apply_findings(
	db: Session,
	*,
	company_id: int,
	findings: list[dict[str, Any]],
	user: User | None,
	request: Request | None,
	run: ReconciliationRun | None,
	affected_scopes: dict[str, set[tuple[str, str]]] | None = None,
) -> tuple[int, int, int]:
	deduplicated = {finding["fingerprint"]: finding for finding in findings}
	fingerprints = set(deduplicated)
	existing_issues = db.scalars(select(DataQualityIssue).where(DataQualityIssue.company_id == company_id)).all()
	issues_by_fingerprint = {issue.fingerprint: issue for issue in existing_issues}
	new_count = 0
	updated_count = 0
	resolved_count = 0
	now = datetime.now(timezone.utc)
	for fingerprint, finding in deduplicated.items():
		issue = issues_by_fingerprint.get(fingerprint)
		if issue is None:
			issue = DataQualityIssue(
				company_id=company_id,
				fingerprint=fingerprint,
				check_key=finding["checkKey"],
				issue_type=finding["issueType"],
				severity=finding["severity"],
				module=finding["module"],
				record_type=finding["recordType"],
				record_id=finding["recordId"],
				record_name=finding["recordName"],
				description=finding["description"],
				details=finding["details"],
				status="Open",
				last_seen_run_id=run.id if run else None,
			)
			db.add(issue)
			new_count += 1
			continue
		previous_status = issue.status
		issue.severity = finding["severity"]
		issue.module = finding["module"]
		issue.record_name = finding["recordName"]
		issue.description = finding["description"]
		issue.details = finding["details"]
		issue.last_seen_at = now
		issue.last_seen_run_id = run.id if run else issue.last_seen_run_id
		updated_count += 1
		if previous_status == "Resolved":
			issue.status = "Open"
			issue.resolved_at = None
			issue.resolved_by_id = None
			issue.resolved_by_name = None
			issue.resolution_note = None
			db.flush()
			_write_issue_event(db, issue, previous_status=previous_status, new_status="Open", user=user, note="Issue re-detected by reconciliation.", request=request)

	failed_keys = {result["key"] for result in (run.check_results or []) if result.get("status") == "Failed"} if run else set()
	for issue in existing_issues:
		if issue.status not in UNRESOLVED_STATUSES or issue.fingerprint in fingerprints or issue.check_key in failed_keys:
			continue
		if run is None:
			scopes = (affected_scopes or {}).get(issue.check_key, set())
			if not scopes:
				continue
			issue_scopes = {(issue.record_type.casefold(), issue.record_id)}
			for key, record_type in (("saleId", "sale"), ("productId", "product"), ("customerId", "customer"), ("movementId", "stock movement")):
				value = (issue.details or {}).get(key)
				if value is not None:
					issue_scopes.add((record_type, str(value)))
			if not scopes.intersection(issue_scopes):
				continue
		previous_status = issue.status
		issue.status = "Resolved"
		issue.resolved_at = now
		issue.resolved_by_id = user.id if user else None
		issue.resolved_by_name = user.name if user else "Reconciliation"
		issue.resolution_note = f"Automatically cleared by reconciliation run {run.id}." if run else "Automatically cleared after the affected record was updated."
		resolved_count += 1
		db.flush()
		_write_issue_event(db, issue, previous_status=previous_status, new_status="Resolved", user=user, note=issue.resolution_note, request=request)
	return new_count, updated_count, resolved_count


def run_reconciliation(db: Session, user: User, request: Request | None = None) -> dict[str, Any]:
	run = ReconciliationRun(
		company_id=user.company_id,
		triggered_by_id=user.id,
		triggered_by_name=user.name,
		started_at=datetime.now(timezone.utc),
		status="Running",
		check_results=[],
	)
	db.add(run)
	db.commit()
	db.refresh(run)
	findings: list[dict[str, Any]] = []
	check_funcs = (
		("sale_stock", lambda: _check_sale_stock(db, user.company_id)),
		("inventory_ledger", lambda: _check_inventory_ledger(db, user.company_id)),
		("sales_references", lambda: _check_sales_references(db, user.company_id)),
		("product_integrity", lambda: _check_products(db, user.company_id)),
		("customer_integrity", lambda: _check_customers(db, user.company_id)),
		("sale_totals", lambda: _check_sale_totals(db, user.company_id)),
	)
	for key, checker in check_funcs:
		try:
			check_findings = checker()
			findings.extend(check_findings)
			run.check_results = [*run.check_results, {"key": key, "name": dict((item[0], item[1]) for item in CHECKS)[key], "status": "Completed", "issuesFound": len(check_findings)}]
			db.commit()
			db.commit()
		except Exception as error:
			db.rollback()
			run = db.get(ReconciliationRun, run.id)
			run.check_results = [*run.check_results, {"key": key, "name": dict((item[0], item[1]) for item in CHECKS)[key], "status": "Failed", "issuesFound": 0, "error": str(error)[:500]}]
			db.commit()
			db.commit()
			findings = [finding for finding in findings if finding["checkKey"] != key]
			failed_checks = sum(1 for item in run.check_results if item.get("status") == "Failed")
			if failed_checks == len(check_funcs):
				run.status = "Failed"
				run.error_message = str(error)[:1000]
				run.completed_at = datetime.now(timezone.utc)
				db.commit()
				return {"run": run, "newIssues": 0, "updatedIssues": 0}

	records_checked = _count_records(db, user.company_id)
	warning_count = len({(finding["recordType"], finding["recordId"]) for finding in findings if finding["severity"] == "warning"})
	error_count = len({(finding["recordType"], finding["recordId"]) for finding in findings if finding["severity"] == "error"})
	new_count, updated_count, resolved_count = _apply_findings(
		db,
		company_id=user.company_id,
		findings=findings,
		user=user,
		request=request,
		run=run,
	)
	db.flush()
	unresolved_count = int(
		db.scalar(
			select(func.count(DataQualityIssue.id)).where(
				DataQualityIssue.company_id == user.company_id,
				DataQualityIssue.status.in_(UNRESOLVED_STATUSES),
			)
		)
		or 0
	)
	affected_records = {(finding["recordType"], finding["recordId"]) for finding in findings}
	failed_checks = sum(1 for item in run.check_results if item.get("status") == "Failed")
	run.records_checked = records_checked
	run.valid_records = max(records_checked - len(affected_records), 0)
	run.warning_count = warning_count
	run.error_count = error_count
	run.issues_detected = len({finding["fingerprint"] for finding in findings})
	run.issues_resolved = resolved_count
	run.failed_checks = failed_checks
	run.status = "Failed" if failed_checks == len(check_funcs) else "Completed with Issues" if findings or unresolved_count else "Completed"
	run.completed_at = datetime.now(timezone.utc)
	create_audit_log(
		db,
		company_id=user.company_id,
		user_id=user.id,
		performed_by=user.name,
		entity_type="Data Quality Reconciliation",
		resource_id=run.id,
		entity_name=f"Reconciliation {run.id}",
		action=AuditAction.DATA_QUALITY_RECONCILIATION_COMPLETED,
		request=request,
		status="failed" if run.status == "Failed" else "success",
		description=f"Reconciliation {run.id} checked {records_checked} records and found {run.issues_detected} issues.",
		after_values={"status": run.status, "recordsChecked": records_checked, "issuesDetected": run.issues_detected, "issuesResolved": resolved_count, "failedChecks": failed_checks},
	)
	db.commit()
	db.refresh(run)
	return {"run": run, "newIssues": new_count, "updatedIssues": updated_count}


def get_overview(db: Session, company_id: int) -> dict[str, Any]:
	last_run = db.scalar(select(ReconciliationRun).where(ReconciliationRun.company_id == company_id).order_by(ReconciliationRun.started_at.desc()).limit(1))
	unresolved = db.scalar(
		select(func.count(DataQualityIssue.id)).where(
			DataQualityIssue.company_id == company_id,
			DataQualityIssue.status.in_(UNRESOLVED_STATUSES),
		)
	) or 0
	return {
		"recordsChecked": last_run.records_checked if last_run else 0,
		"validRecords": last_run.valid_records if last_run else 0,
		"warningRecords": last_run.warning_count if last_run else 0,
		"errorRecords": last_run.error_count if last_run else 0,
		"unresolvedIssues": int(unresolved),
		"lastReconciliationAt": last_run.completed_at if last_run else None,
		"lastRunStatus": last_run.status if last_run else None,
	}


def get_issue_filter_options(db: Session, company_id: int) -> dict[str, list[str]]:
	issues = db.scalars(select(DataQualityIssue).where(DataQualityIssue.company_id == company_id)).all()
	return {
		"issueTypes": sorted({issue.issue_type for issue in issues}),
		"severities": sorted({issue.severity for issue in issues}),
		"modules": sorted({issue.module for issue in issues}),
		"statuses": ["Open", "Investigating", "Resolved", "Ignored"],
	}


def list_issues(
	db: Session,
	company_id: int,
	*,
	page: int = 1,
	page_size: int = 25,
	search: str | None = None,
	issue_type: str | None = None,
	severity: str | None = None,
	module: str | None = None,
	status_filter: str | None = None,
	start_date: datetime | None = None,
	end_date: datetime | None = None,
	sort_by: str = "detectedAt",
	sort_direction: str = "desc",
) -> dict[str, Any]:
	if start_date and end_date and start_date > end_date:
		raise HTTPException(status_code=422, detail="startDate must be before or equal to endDate")
	statement = select(DataQualityIssue).where(DataQualityIssue.company_id == company_id)
	if search:
		term = f"%{search.strip()}%"
		statement = statement.where(or_(DataQualityIssue.description.ilike(term), DataQualityIssue.record_name.ilike(term), DataQualityIssue.record_id.ilike(term), DataQualityIssue.issue_type.ilike(term)))
	if issue_type:
		statement = statement.where(DataQualityIssue.issue_type == issue_type)
	if severity:
		statement = statement.where(DataQualityIssue.severity == severity)
	if module:
		statement = statement.where(DataQualityIssue.module == module)
	if status_filter:
		statement = statement.where(DataQualityIssue.status == status_filter)
	if start_date:
		statement = statement.where(DataQualityIssue.detected_at >= start_date)
	if end_date:
		statement = statement.where(DataQualityIssue.detected_at <= end_date)
	sort_columns = {
		"detectedAt": DataQualityIssue.detected_at,
		"severity": DataQualityIssue.severity,
		"status": DataQualityIssue.status,
		"issueType": DataQualityIssue.issue_type,
		"module": DataQualityIssue.module,
	}
	sort_column = sort_columns.get(sort_by, DataQualityIssue.detected_at)
	statement = statement.order_by(sort_column.desc() if sort_direction == "desc" else sort_column.asc(), DataQualityIssue.id.desc())
	total_statement = select(func.count()).select_from(statement.order_by(None).subquery())
	total = int(db.scalar(total_statement) or 0)
	items = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
	return {"items": items, "total": total, "page": page, "pageSize": page_size, "totalPages": (total + page_size - 1) // page_size if total else 0}


def get_issue(db: Session, company_id: int, issue_id: int) -> DataQualityIssue:
	issue = db.scalar(select(DataQualityIssue).where(DataQualityIssue.company_id == company_id, DataQualityIssue.id == issue_id))
	if issue is None:
		raise HTTPException(status_code=404, detail="Data quality issue not found")
	return issue


def get_issue_detail(db: Session, company_id: int, issue_id: int) -> dict[str, Any]:
	issue = get_issue(db, company_id, issue_id)
	details = issue.details or {}
	product_id = details.get("productId")
	if not product_id and issue.record_type == "Product":
		product_id = int(issue.record_id)
	context: dict[str, Any] = {"product": None, "inventory": None, "stockMovements": [], "relatedSales": [], "customer": None, "sale": None}
	if product_id:
		product = db.scalar(select(Product).where(Product.id == product_id, Product.company_id == company_id))
		if product:
			context["product"] = {"id": product.id, "name": product.name, "sku": product.sku, "status": product.status.value, "stockQuantity": product.stock_quantity}
			inventory = db.scalar(select(Inventory).where(Inventory.company_id == company_id, Inventory.product_id == product.id))
			if inventory:
				movements = db.scalars(
					select(InventoryMovement)
					.where(InventoryMovement.inventory_id == inventory.id)
					.order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc())
					.limit(25)
				).all()
				latest = movements[0] if movements else None
				context["inventory"] = {
					"currentQuantity": inventory.current_stock,
					"availableQuantity": inventory.available_stock,
					"expectedQuantity": latest.updated_quantity if latest else None,
					"difference": inventory.current_stock - latest.updated_quantity if latest else None,
				}
				context["stockMovements"] = [
					{"id": movement.id, "type": movement.movement_type.value, "previousQuantity": movement.previous_quantity, "quantityChanged": movement.quantity_changed, "updatedQuantity": movement.updated_quantity, "reason": movement.reason, "createdAt": movement.created_at}
					for movement in movements
				]
			sales = db.execute(
				select(Sale, SaleItem)
				.join(SaleItem, SaleItem.sale_id == Sale.id)
				.where(Sale.company_id == company_id, SaleItem.product_id == product.id)
				.order_by(Sale.sale_date.desc())
				.limit(25)
			).all()
			context["relatedSales"] = [
				{"id": sale.id, "invoiceNumber": sale.invoice_number, "quantity": item.quantity, "total": float(item.total), "saleDate": sale.sale_date, "status": sale.payment_status.value}
				for sale, item in sales
			]
	if issue.record_type == "Sale":
		sale = db.scalar(select(Sale).where(Sale.company_id == company_id, Sale.id == int(issue.record_id)))
		if sale:
			context["sale"] = {"id": sale.id, "invoiceNumber": sale.invoice_number, "totalAmount": float(sale.total_amount), "saleDate": sale.sale_date, "customerName": sale.customer_name}
			if sale.customer_id:
				customer = db.scalar(select(Customer).where(Customer.company_id == company_id, Customer.id == sale.customer_id))
				if customer:
					context["customer"] = {"id": customer.id, "name": customer.full_name, "email": customer.email, "status": customer.status.value}
	if issue.record_type == "Customer":
		customer = db.scalar(select(Customer).where(Customer.company_id == company_id, Customer.id == int(issue.record_id)))
		if customer:
			context["customer"] = {"id": customer.id, "name": customer.full_name, "email": customer.email, "phone": customer.phone_number, "status": customer.status.value}
	events = db.scalars(
		select(DataQualityIssueEvent)
		.where(DataQualityIssueEvent.company_id == company_id, DataQualityIssueEvent.issue_id == issue.id)
		.order_by(DataQualityIssueEvent.created_at.desc(), DataQualityIssueEvent.id.desc())
	).all()
	return {"issue": issue, "context": context, "events": events}


def update_issue_status(db: Session, user: User, issue_id: int, payload: IssueStatusUpdate, request: Request | None = None) -> DataQualityIssue:
	issue = get_issue(db, user.company_id, issue_id)
	if issue.status == payload.status:
		if payload.status == "Resolved" and payload.resolution_note:
			issue.resolution_note = payload.resolution_note
			db.commit()
			db.refresh(issue)
		return issue
	previous_status = issue.status
	issue.status = payload.status
	if payload.status == "Resolved":
		issue.resolved_at = datetime.now(timezone.utc)
		issue.resolved_by_id = user.id
		issue.resolved_by_name = user.name
		issue.resolution_note = payload.resolution_note
	else:
		issue.resolved_at = None
		issue.resolved_by_id = None
		issue.resolved_by_name = None
		issue.resolution_note = None
	db.flush()
	_write_issue_event(db, issue, previous_status=previous_status, new_status=payload.status, user=user, note=payload.resolution_note, request=request)
	db.commit()
	db.refresh(issue)
	return issue


def list_reconciliation_runs(db: Session, company_id: int, page: int = 1, page_size: int = 25) -> dict[str, Any]:
	statement = select(ReconciliationRun).where(ReconciliationRun.company_id == company_id).order_by(ReconciliationRun.started_at.desc())
	total = int(db.scalar(select(func.count(ReconciliationRun.id)).where(ReconciliationRun.company_id == company_id)) or 0)
	items = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
	return {"items": items, "total": total, "page": page, "pageSize": page_size, "totalPages": (total + page_size - 1) // page_size if total else 0}


def run_incremental_checks(
	db: Session,
	user: User,
	*,
	sale_ids: set[int] | None = None,
	product_ids: set[int] | None = None,
	customer_ids: set[int] | None = None,
	request: Request | None = None,
) -> int:
	findings: list[dict[str, Any]] = []
	affected_scopes: dict[str, set[tuple[str, str]]] = defaultdict(set)
	if sale_ids:
		findings.extend(_check_sale_stock(db, user.company_id, sale_ids))
		findings.extend(_check_sales_references(db, user.company_id, sale_ids))
		findings.extend(_check_sale_totals(db, user.company_id, sale_ids))
		for sale_id in sale_ids:
			for check_key in ("sale_stock", "sales_references", "sale_totals"):
				affected_scopes[check_key].add(("sale", str(sale_id)))
	if product_ids:
		findings.extend(_check_inventory_ledger(db, user.company_id, product_ids))
		findings.extend(_check_products(db, user.company_id, product_ids))
		findings.extend(_check_sales_references(db, user.company_id, product_ids=product_ids))
		for product_id in product_ids:
			for check_key in ("inventory_ledger", "product_integrity", "sales_references"):
				affected_scopes[check_key].add(("product", str(product_id)))
	if customer_ids:
		findings.extend(_check_customers(db, user.company_id, customer_ids))
		findings.extend(_check_sales_references(db, user.company_id, customer_ids=customer_ids))
		for customer_id in customer_ids:
			for check_key in ("customer_integrity", "sales_references"):
				affected_scopes[check_key].add(("customer", str(customer_id)))
	if findings:
		_apply_findings(db, company_id=user.company_id, findings=findings, user=user, request=request, run=None, affected_scopes=affected_scopes)
	else:
		_apply_findings(db, company_id=user.company_id, findings=[], user=user, request=request, run=None, affected_scopes=affected_scopes)
		return len({finding["fingerprint"] for finding in findings})
	return len({finding["fingerprint"] for finding in findings})