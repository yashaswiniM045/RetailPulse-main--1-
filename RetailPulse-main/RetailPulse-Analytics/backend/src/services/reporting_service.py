import csv
import io
import json
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.category import Category
from src.models.customer import Customer, CustomerPurchaseSummary, CustomerStatus
from src.models.inventory import Inventory, InventoryMovement, StockStatus
from src.models.product import Product
from src.models.reporting import ReportHistory, ScheduledReport
from src.models.sale import PaymentStatus, Sale, SaleItem
from src.models.user import User
from src.schemas.reporting import ReportFilters, ScheduleCreate

REPORT_NAMES = {
	"sales": "Sales Report",
	"inventory": "Inventory Report",
	"customers": "Customer Report",
	"product-performance": "Product Performance Report",
	"stock-movement": "Stock Movement Report",
}


def _filters_dict(filters: ReportFilters | dict) -> dict:
	if isinstance(filters, ReportFilters):
		values = filters.model_dump(by_alias=True, exclude_none=True)
		return {key: value.isoformat() if isinstance(value, datetime) else value for key, value in values.items()}
	return {key: value for key, value in filters.items() if value is not None}


def _as_datetime(value: str | datetime | None) -> datetime | None:
	if value is None or isinstance(value, datetime):
		return value
	return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _query_rows(db: Session, company_id: int, report_type: str, filters: dict) -> list[dict]:
	start = _as_datetime(filters.get("startDate"))
	end = _as_datetime(filters.get("endDate"))
	product_id = filters.get("productId")
	category_id = filters.get("categoryId")
	brand = filters.get("brand")
	customer_id = filters.get("customerId")
	user_id = filters.get("userId")
	stock_status = filters.get("stockStatus")
	sales_status = filters.get("salesStatus")
	product_filters = [Product.company_id == company_id]
	if product_id:
		product_filters.append(Product.id == product_id)
	if category_id:
		product_filters.append(Product.category_id == category_id)
	if brand:
		product_filters.append(func.lower(Product.brand) == brand.strip().lower())

	if report_type == "sales":
		statement = (
			select(Sale, SaleItem, Product, Category)
			.join(SaleItem, SaleItem.sale_id == Sale.id)
			.join(Product, Product.id == SaleItem.product_id)
			.join(Category, Category.id == Product.category_id)
			.where(Sale.company_id == company_id, *product_filters)
		)
		if start:
			statement = statement.where(Sale.sale_date >= start)
		if end:
			statement = statement.where(Sale.sale_date <= end)
		if customer_id:
			statement = statement.where(Sale.customer_id == customer_id)
		if user_id:
			statement = statement.where(Sale.created_by == user_id)
		if sales_status:
			statement = statement.where(Sale.payment_status == PaymentStatus(sales_status))
		statement = statement.order_by(Sale.sale_date.desc(), Sale.id.desc())
		return [
			{
				"saleId": sale.id,
				"invoice": sale.invoice_number,
				"date": sale.sale_date.isoformat(),
				"customer": sale.customer_name,
				"product": product.name,
				"sku": product.sku,
				"category": category.name,
				"brand": product.brand or "",
				"quantity": item.quantity,
				"unitPrice": float(item.unit_price),
				"total": float(item.total),
				"status": sale.payment_status.value,
				"user": sale.creator.name if sale.creator else "",
			}
			for sale, item, product, category in db.execute(statement).all()
		]

	if report_type in {"inventory", "product-performance"}:
		if report_type == "inventory":
			statement = (
				select(Inventory, Product, Category)
				.join(Product, Product.id == Inventory.product_id)
				.join(Category, Category.id == Product.category_id)
				.where(Inventory.company_id == company_id, *product_filters)
			)
			if stock_status:
				statement = statement.where(Inventory.stock_status == StockStatus(stock_status))
			statement = statement.order_by(Product.name.asc())
			return [
				{
					"productId": product.id,
					"product": product.name,
					"sku": product.sku,
					"category": category.name,
					"brand": product.brand or "",
					"currentStock": inventory.current_stock,
					"reservedStock": inventory.reserved_stock,
					"availableStock": inventory.available_stock,
					"reorderLevel": inventory.reorder_level,
					"status": inventory.stock_status.value,
					"updatedAt": inventory.updated_at.isoformat(),
				}
				for inventory, product, category in db.execute(statement).all()
			]

		statement = (
			select(
				Product,
				Category,
				Inventory,
				func.coalesce(func.sum(SaleItem.quantity), 0),
				func.coalesce(func.sum(SaleItem.total), 0),
			)
			.join(Category, Category.id == Product.category_id)
			.outerjoin(Inventory, Inventory.product_id == Product.id)
			.outerjoin(SaleItem, SaleItem.product_id == Product.id)
			.outerjoin(Sale, Sale.id == SaleItem.sale_id)
			.where(*product_filters)
		)
		if start:
			statement = statement.where((Sale.id.is_(None)) | (Sale.sale_date >= start))
		if end:
			statement = statement.where((Sale.id.is_(None)) | (Sale.sale_date <= end))
		if customer_id:
			statement = statement.where(Sale.customer_id == customer_id)
		if user_id:
			statement = statement.where(Sale.created_by == user_id)
		if sales_status:
			statement = statement.where(Sale.payment_status == PaymentStatus(sales_status))
		if stock_status:
			statement = statement.where(Inventory.stock_status == StockStatus(stock_status))
		statement = statement.group_by(Product.id, Category.id, Inventory.id).order_by(Product.name.asc())
		return [
			{
				"productId": product.id,
				"product": product.name,
				"sku": product.sku,
				"category": category.name,
				"brand": product.brand or "",
				"quantitySold": int(quantity or 0),
				"revenue": float(revenue or 0),
				"currentStock": inventory.current_stock if inventory else product.stock_quantity,
				"stockStatus": inventory.stock_status.value if inventory else "out-of-stock",
			}
			for product, category, inventory, quantity, revenue in db.execute(statement).all()
		]

	if report_type == "customers":
		statement = (
			select(Customer, CustomerPurchaseSummary)
			.outerjoin(CustomerPurchaseSummary, CustomerPurchaseSummary.customer_id == Customer.id)
			.where(Customer.company_id == company_id, Customer.is_deleted.is_(False))
		)
		if customer_id:
			statement = statement.where(Customer.id == customer_id)
		if sales_status:
			statement = statement.where(Customer.status == CustomerStatus(sales_status))
		if start:
			statement = statement.where(CustomerPurchaseSummary.last_purchase_at >= start)
		if end:
			statement = statement.where(CustomerPurchaseSummary.last_purchase_at <= end)
		if product_id or category_id or brand or user_id:
			# Purchase-level product/user filters are resolved through existing sale rows.
			sales = select(Sale.customer_id).join(SaleItem, SaleItem.sale_id == Sale.id).join(Product, Product.id == SaleItem.product_id).where(Sale.company_id == company_id)
			if product_id:
				sales = sales.where(Product.id == product_id)
			if category_id:
				sales = sales.where(Product.category_id == category_id)
			if brand:
				sales = sales.where(func.lower(Product.brand) == brand.strip().lower())
			if user_id:
				sales = sales.where(Sale.created_by == user_id)
			if start:
				sales = sales.where(Sale.sale_date >= start)
			if end:
				sales = sales.where(Sale.sale_date <= end)
			statement = statement.where(Customer.id.in_(sales))
		statement = statement.order_by(Customer.full_name.asc())
		return [
			{
				"customerId": customer.id,
				"customerCode": customer.customer_code,
				"customer": customer.full_name,
				"email": customer.email,
				"type": customer.customer_type.value,
				"segment": customer.segment.value,
				"status": customer.status.value,
				"orders": summary.total_orders if summary else 0,
				"revenue": float(summary.total_revenue or 0) if summary else 0,
				"lastPurchase": summary.last_purchase_at.isoformat() if summary and summary.last_purchase_at else "",
			}
			for customer, summary in db.execute(statement).all()
		]

	if report_type == "stock-movement":
		statement = (
			select(InventoryMovement, Inventory, Product, Category, User)
			.join(Inventory, Inventory.id == InventoryMovement.inventory_id)
			.join(Product, Product.id == Inventory.product_id)
			.join(Category, Category.id == Product.category_id)
			.outerjoin(User, User.id == InventoryMovement.performed_by)
			.where(Inventory.company_id == company_id, *product_filters)
		)
		if start:
			statement = statement.where(InventoryMovement.created_at >= start)
		if end:
			statement = statement.where(InventoryMovement.created_at <= end)
		if user_id:
			statement = statement.where(InventoryMovement.performed_by == user_id)
		if stock_status:
			statement = statement.where(Inventory.stock_status == StockStatus(stock_status))
		statement = statement.order_by(InventoryMovement.created_at.desc())
		return [
			{
				"movementId": movement.id,
				"date": movement.created_at.isoformat(),
				"product": product.name,
				"sku": product.sku,
				"category": category.name,
				"brand": product.brand or "",
				"movement": movement.movement_type.value,
				"previous": movement.previous_quantity,
				"change": movement.quantity_changed,
				"updated": movement.updated_quantity,
				"reason": movement.reason,
				"user": user.name if user else "",
			}
			for movement, inventory, product, category, user in db.execute(statement).all()
		]
	return []


def _page_rows(rows: list[dict], *, page: int, page_size: int, sort_by: str | None, sort_direction: str) -> dict:
	if sort_by and rows and sort_by in rows[0]:
		rows = sorted(
			rows,
			key=lambda item: (
				item.get(sort_by) is None,
				item.get(sort_by).lower() if isinstance(item.get(sort_by), str) else item.get(sort_by),
			),
			reverse=sort_direction == "desc",
		)
	total = len(rows)
	return {
		"items": rows[(page - 1) * page_size : page * page_size],
		"total": total,
		"page": page,
		"pageSize": page_size,
		"totalPages": (total + page_size - 1) // page_size if total else 0,
	}


def _history_payload(history: ReportHistory, rows: list[dict], *, page: int = 1, page_size: int = 25, sort_by: str | None = None, sort_direction: str = "asc") -> dict:
	return {
		"history": history,
		"page": _page_rows(rows, page=page, page_size=page_size, sort_by=sort_by, sort_direction=sort_direction),
	}


def generate_report(db: Session, user: User, report_type: str, filters: ReportFilters, schedule_id: int | None = None, export_format: str = "view") -> dict:
	filters_value = _filters_dict(filters)
	history = ReportHistory(
		company_id=user.company_id,
		generated_by_id=user.id,
		generated_by_name=user.name,
		schedule_id=schedule_id,
		report_type=report_type,
		filters=filters_value,
		total_rows=0,
		export_format=export_format,
		status="success",
	)
	db.add(history)
	rows = []
	try:
		rows = _query_rows(db, user.company_id, report_type, filters_value)
		history.total_rows = len(rows)
	except Exception as error:
		db.rollback()
		history = ReportHistory(
			company_id=user.company_id,
			generated_by_id=user.id,
			generated_by_name=user.name,
			schedule_id=schedule_id,
			report_type=report_type,
			filters=filters_value,
			total_rows=0,
			export_format=export_format,
			status="failed",
			error_message=str(error)[:1000],
		)
		db.add(history)
	db.commit()
	db.refresh(history)
	return _history_payload(history, rows)


def get_report_history(db: Session, company_id: int, history_id: int) -> ReportHistory:
	history = db.scalar(select(ReportHistory).where(ReportHistory.id == history_id, ReportHistory.company_id == company_id))
	if not history:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report history not found")
	return history


def get_report_result(
	db: Session,
	company_id: int,
	history_id: int,
	*,
	page: int = 1,
	page_size: int = 25,
	sort_by: str | None = None,
	sort_direction: str = "asc",
) -> dict:
	history = get_report_history(db, company_id, history_id)
	rows = _query_rows(db, company_id, history.report_type, history.filters) if history.status == "success" else []
	return _history_payload(history, rows, page=page, page_size=page_size, sort_by=sort_by, sort_direction=sort_direction)


def list_report_history(db: Session, company_id: int, page: int, page_size: int) -> dict:
	statement = select(ReportHistory).where(ReportHistory.company_id == company_id).order_by(ReportHistory.created_at.desc())
	total = int(db.scalar(select(func.count(ReportHistory.id)).where(ReportHistory.company_id == company_id)) or 0)
	items = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
	return {"items": items, "total": total, "page": page, "pageSize": page_size, "totalPages": (total + page_size - 1) // page_size if total else 0}


def get_report_filters(db: Session, company_id: int) -> dict:
	return {
		"products": [{"id": row.id, "name": row.name} for row in db.scalars(select(Product).where(Product.company_id == company_id).order_by(Product.name)).all()],
		"categories": [{"id": row.id, "name": row.name} for row in db.scalars(select(Category).where(Category.company_id == company_id).order_by(Category.name)).all()],
		"brands": [value for value in db.scalars(select(Product.brand).where(Product.company_id == company_id, Product.brand.is_not(None), Product.brand != "").distinct().order_by(Product.brand)).all()],
		"customers": [{"id": row.id, "name": row.full_name} for row in db.scalars(select(Customer).where(Customer.company_id == company_id, Customer.is_deleted.is_(False)).order_by(Customer.full_name)).all()],
		"users": [{"id": row.id, "name": row.name} for row in db.scalars(select(User).where(User.company_id == company_id).order_by(User.name)).all()],
	}


def _next_run(frequency: str, execution_time: str, now: datetime | None = None) -> datetime:
	now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(tzinfo=None)
	hour, minute = (int(value) for value in execution_time.split(":"))
	candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
	if candidate <= now:
		candidate += timedelta(days=1)
	if frequency == "weekly":
		candidate += timedelta(days=(7 - candidate.weekday()) % 7)
		if candidate <= now:
			candidate += timedelta(days=7)
	elif frequency == "monthly":
		candidate = candidate.replace(day=1)
		if candidate <= now:
			month = candidate.month + 1
			candidate = candidate.replace(year=candidate.year + (month - 1) // 12, month=(month - 1) % 12 + 1)
	return candidate


def _schedule_dict(schedule: ScheduledReport) -> dict:
	return {
		"id": schedule.id,
		"name": schedule.name,
		"report_type": schedule.report_type,
		"filters": schedule.filters,
		"frequency": schedule.frequency,
		"execution_time": schedule.execution_time,
		"recipients": schedule.recipients,
		"export_format": schedule.export_format,
		"is_active": schedule.is_active,
		"next_run_at": schedule.next_run_at,
	}


def list_scheduled_reports(db: Session, company_id: int) -> list[ScheduledReport]:
	return db.scalars(select(ScheduledReport).where(ScheduledReport.company_id == company_id).order_by(ScheduledReport.created_at.desc())).all()


def create_scheduled_report(db: Session, user: User, payload: ScheduleCreate) -> ScheduledReport:
	values = payload.model_dump(by_alias=False)
	values["filters"] = _filters_dict(payload.filters)
	values["recipients"] = [str(email) for email in payload.recipients]
	values["next_run_at"] = _next_run(payload.frequency, payload.execution_time)
	schedule = ScheduledReport(company_id=user.company_id, created_by_id=user.id, **values)
	db.add(schedule)
	db.commit()
	db.refresh(schedule)
	return schedule


def update_scheduled_report(db: Session, user: User, schedule_id: int, payload: ScheduleCreate) -> ScheduledReport:
	schedule = db.scalar(select(ScheduledReport).where(ScheduledReport.id == schedule_id, ScheduledReport.company_id == user.company_id))
	if not schedule:
		raise HTTPException(status_code=404, detail="Scheduled report not found")
	values = payload.model_dump(by_alias=False)
	values["filters"] = _filters_dict(payload.filters)
	values["recipients"] = [str(email) for email in payload.recipients]
	for field, value in values.items():
		setattr(schedule, field, value)
	schedule.next_run_at = _next_run(schedule.frequency, schedule.execution_time)
	db.commit()
	db.refresh(schedule)
	return schedule


def set_schedule_active(db: Session, user: User, schedule_id: int, is_active: bool) -> ScheduledReport:
	schedule = db.scalar(select(ScheduledReport).where(ScheduledReport.id == schedule_id, ScheduledReport.company_id == user.company_id))
	if not schedule:
		raise HTTPException(status_code=404, detail="Scheduled report not found")
	schedule.is_active = is_active
	if is_active:
		schedule.next_run_at = _next_run(schedule.frequency, schedule.execution_time)
	db.commit()
	db.refresh(schedule)
	return schedule


def delete_scheduled_report(db: Session, user: User, schedule_id: int) -> None:
	schedule = db.scalar(select(ScheduledReport).where(ScheduledReport.id == schedule_id, ScheduledReport.company_id == user.company_id))
	if not schedule:
		raise HTTPException(status_code=404, detail="Scheduled report not found")
	db.delete(schedule)
	db.commit()


def _csv_bytes(history: ReportHistory, rows: list[dict]) -> bytes:
	stream = io.StringIO()
	writer = csv.writer(stream)
	writer.writerow([REPORT_NAMES.get(history.report_type, "Report")])
	writer.writerow(["Period", history.filters.get("startDate", "Any"), history.filters.get("endDate", "Any")])
	writer.writerow(["Applied filters", json.dumps(history.filters, ensure_ascii=True)])
	if rows:
		writer.writerow(list(rows[0].keys()))
		for row in rows:
			writer.writerow([row.get(key, "") for key in rows[0]])
	return stream.getvalue().encode("utf-8-sig")


def _pdf_bytes(history: ReportHistory, rows: list[dict]) -> bytes:
	lines = [REPORT_NAMES.get(history.report_type, "Report"), f"Period: {history.filters.get('startDate', 'Any')} - {history.filters.get('endDate', 'Any')}", f"Filters: {json.dumps(history.filters, ensure_ascii=True)}", ""]
	if rows:
		lines.append(" | ".join(rows[0].keys()))
		lines.extend(" | ".join(str(value) for value in row.values()) for row in rows)
	lines = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("latin-1", "replace").decode("latin-1")[:150] for line in lines]
	pages = [lines[index : index + 45] for index in range(0, max(len(lines), 1), 45)]
	objects = [b"<< /Type /Catalog /Pages 2 0 R >>"]
	page_ids = [3 + index * 2 for index in range(len(pages))]
	objects.append(f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(pages)} >>".encode())
	for index, page_lines in enumerate(pages):
		page_id = page_ids[index]
		content_id = page_id + 1
		commands = ["BT", "/F1 8 Tf", "40 800 Td"]
		for line in page_lines:
			commands.append(f"({line}) Tj")
			commands.append("0 -16 Td")
		commands.append("T*" if len(commands) == 3 else "")
		commands.append("ET")
		content = "\n".join(command for command in commands if command).encode("latin-1", "replace")
		objects.extend([
			f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {content_id} 0 R >>".encode(),
			b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
		])
	output = bytearray(b"%PDF-1.4\n")
	offsets = [0]
	for index, obj in enumerate(objects, start=1):
		offsets.append(len(output))
		output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
	xref = len(output)
	output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
	for offset in offsets[1:]:
		output.extend(f"{offset:010d} 00000 n \n".encode())
	output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
	return bytes(output)


def export_history(db: Session, company_id: int, history_id: int, export_format: str) -> tuple[bytes, str, str]:
	history = get_report_history(db, company_id, history_id)
	if history.status != "success":
		raise HTTPException(status_code=409, detail="Failed reports cannot be exported")
	history.export_format = export_format
	db.commit()
	name = REPORT_NAMES.get(history.report_type, "Report").lower().replace(" ", "-")
	rows = _query_rows(db, company_id, history.report_type, history.filters)
	return (_csv_bytes(history, rows), "text/csv", f"{name}.csv") if export_format == "csv" else (_pdf_bytes(history, rows), "application/pdf", f"{name}.pdf")


def _deliver_schedule(schedule: ScheduledReport, history: ReportHistory, attachment: bytes, media_type: str, file_name: str) -> None:
	host = os.getenv("REPORT_SMTP_HOST")
	sender = os.getenv("REPORT_SMTP_FROM")
	if not host or not sender:
		raise RuntimeError("Scheduled report delivery requires REPORT_SMTP_HOST and REPORT_SMTP_FROM")
	message = EmailMessage()
	message["Subject"] = f"{REPORT_NAMES[schedule.report_type]}: {schedule.name}"
	message["From"] = sender
	message["To"] = ", ".join(schedule.recipients)
	message.set_content(f"Attached is your scheduled {REPORT_NAMES[schedule.report_type]} generated by RetailPulse.")
	maintype, subtype = media_type.split("/", 1)
	message.add_attachment(attachment, maintype=maintype, subtype=subtype, filename=file_name)
	port = int(os.getenv("REPORT_SMTP_PORT", "587"))
	with smtplib.SMTP(host, port, timeout=20) as server:
		if os.getenv("REPORT_SMTP_STARTTLS", "true").lower() == "true":
			server.starttls()
		username = os.getenv("REPORT_SMTP_USERNAME")
		password = os.getenv("REPORT_SMTP_PASSWORD")
		if username and password:
			server.login(username, password)
		server.send_message(message)


def run_due_schedules(db: Session) -> None:
	now = datetime.now(timezone.utc).replace(tzinfo=None)
	due = db.scalars(select(ScheduledReport).where(ScheduledReport.is_active.is_(True), ScheduledReport.next_run_at <= now)).all()
	for schedule in due:
		creator = db.get(User, schedule.created_by_id)
		if not creator:
			schedule.last_status = "failed"
			schedule.last_error = "Schedule owner no longer exists"
			schedule.last_run_at = now
			schedule.next_run_at = _next_run(schedule.frequency, schedule.execution_time, now)
			db.commit()
			continue
		result = generate_report(db, creator, schedule.report_type, ReportFilters.model_validate(schedule.filters), schedule.id, schedule.export_format)
		history = get_report_history(db, schedule.company_id, result["history"].id)
		error = None
		try:
			rows = _query_rows(db, schedule.company_id, schedule.report_type, history.filters)
			content, content_type, file_name = (_csv_bytes(history, rows), "text/csv", "report.csv") if schedule.export_format == "csv" else (_pdf_bytes(history, rows), "application/pdf", "report.pdf")
			_deliver_schedule(schedule, history, content, content_type, file_name)
		except Exception as exception:
			error = str(exception)[:1000]
			history.status = "failed"
			history.error_message = error
		schedule.last_run_at = now
		schedule.last_status = "success" if error is None else "failed"
		schedule.last_error = error
		schedule.last_history_id = history.id
		schedule.next_run_at = _next_run(schedule.frequency, schedule.execution_time, now)
		db.commit()