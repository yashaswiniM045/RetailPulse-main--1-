import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.models.audit_log import AuditLog
from src.models.base import Base
from src.models.category import Category, CategoryStatus
from src.models.company import Company
from src.models.customer import Customer, CustomerStatus, CustomerType
from src.models.data_quality import DataQualityIssue, DataQualityIssueEvent
from src.models.inventory import Inventory, InventoryMovement, InventoryMovementType, StockStatus
from src.models.product import Product, ProductStatus
from src.models.sale import PaymentMethod, PaymentStatus, Sale, SaleItem, SalesChannel
from src.models.user import User, UserRole, UserStatus
from src.schemas.data_quality import IssueStatusUpdate
from src.services.data_quality_service import (
	get_issue_detail,
	get_overview,
	list_issues,
	run_reconciliation,
	run_incremental_checks,
	update_issue_status,
)


class DataQualityTests(unittest.TestCase):
	def setUp(self):
		self.engine = create_engine("sqlite:///:memory:")
		Base.metadata.create_all(self.engine)
		self.db = Session(self.engine)
		self.company_a = Company(name="Quality North", industry="Retail", email="quality-north@example.com", address="North", phone="555-1000")
		self.company_b = Company(name="Quality South", industry="Retail", email="quality-south@example.com", address="South", phone="555-2000")
		self.db.add_all([self.company_a, self.company_b])
		self.db.flush()
		self.user = User(company_id=self.company_a.id, name="Quality Admin", email="quality-admin@example.com", password="hash", role=UserRole.COMPANY_ADMIN, status=UserStatus.ACTIVE)
		self.other_user = User(company_id=self.company_b.id, name="Other Admin", email="other-quality-admin@example.com", password="hash", role=UserRole.COMPANY_ADMIN, status=UserStatus.ACTIVE)
		self.db.add_all([self.user, self.other_user])
		self.db.flush()
		self.category = Category(company_id=self.company_a.id, name="Home", status=CategoryStatus.ACTIVE)
		self.db.add(self.category)
		self.db.flush()
		self.product = Product(company_id=self.company_a.id, category_id=self.category.id, name="Travel Cup", sku="CUP-1", brand="Northstar", unit_price=10, cost_price=4, stock_quantity=2, is_out_of_stock=False, unit_of_measure="each", status=ProductStatus.INACTIVE)
		self.db.add(self.product)
		self.db.flush()
		self.customer = Customer(company_id=self.company_a.id, customer_code="C-1", full_name="Taylor Buyer", email="taylor@example.com", phone_number="555-0101", customer_type=CustomerType.RETAIL, status=CustomerStatus.INACTIVE)
		self.db.add(self.customer)
		self.db.flush()
		inventory = Inventory(company_id=self.company_a.id, product_id=self.product.id, current_stock=-3, reserved_stock=0, available_stock=0, reorder_level=5, stock_status=StockStatus.OUT_OF_STOCK)
		self.db.add(inventory)
		self.db.flush()
		sale_date = datetime(2026, 10, 1, tzinfo=timezone.utc)
		sale = Sale(company_id=self.company_a.id, customer_id=self.customer.id, invoice_number="INV-Q-1", customer_name=self.customer.full_name, sale_date=sale_date, sales_channel=SalesChannel.IN_STORE, payment_method=PaymentMethod.CASH, payment_status=PaymentStatus.PAID, total_amount=99, created_by=self.user.id)
		self.db.add(sale)
		self.db.flush()
		self.sale = sale
		self.db.add_all([
			SaleItem(sale_id=sale.id, product_id=self.product.id, category_id=self.category.id, quantity=8, unit_price=10, discount=0, tax=0, total=80),
			InventoryMovement(inventory_id=inventory.id, movement_type=InventoryMovementType.SALE, quantity_changed=-8, previous_quantity=5, updated_quantity=-3, reason=f"Sale {sale.invoice_number}", performed_by=self.user.id),
		])
		self.db.commit()

	def tearDown(self):
		self.db.close()
		self.engine.dispose()

	def test_reconciliation_detects_and_deduplicates_issues(self):
		first = run_reconciliation(self.db, self.user)
		issues_after_first = self.db.scalars(select(DataQualityIssue).where(DataQualityIssue.company_id == self.company_a.id)).all()
		self.assertGreaterEqual(first["newIssues"], 4)
		self.assertTrue(any(issue.issue_type == "sale_exceeds_available_stock" for issue in issues_after_first))
		self.assertTrue(any(issue.issue_type == "product_inventory_quantity_mismatch" for issue in issues_after_first))
		self.assertTrue(any(issue.issue_type == "sale_inactive_product" for issue in issues_after_first))
		self.assertTrue(any(issue.issue_type == "sale_inactive_customer" for issue in issues_after_first))
		self.assertTrue(any(issue.issue_type == "report_total_mismatch" for issue in issues_after_first))
		second = run_reconciliation(self.db, self.user)
		issues_after_second = self.db.scalars(select(DataQualityIssue).where(DataQualityIssue.company_id == self.company_a.id)).all()
		self.assertEqual(second["newIssues"], 0)
		self.assertEqual(len(issues_after_second), len(issues_after_first))
		self.assertEqual(len({issue.fingerprint for issue in issues_after_second}), len(issues_after_second))
		self.assertEqual(get_overview(self.db, self.company_a.id)["unresolvedIssues"], len(issues_after_second))

	def test_issue_filters_details_resolution_audit_and_company_isolation(self):
		run_reconciliation(self.db, self.user)
		page = list_issues(self.db, self.company_a.id, search="Travel Cup", issue_type="sale_exceeds_available_stock", severity="error", module="Sales / Inventory", status_filter="Open")
		self.assertEqual(page["total"], 1)
		issue = page["items"][0]
		detail = get_issue_detail(self.db, self.company_a.id, issue.id)
		self.assertEqual(detail["context"]["sale"]["invoiceNumber"], "INV-Q-1")
		self.assertEqual(detail["context"]["product"]["name"], "Travel Cup")
		self.assertEqual(detail["context"]["inventory"]["currentQuantity"], -3)
		with self.assertRaises(HTTPException) as raised:
			get_issue_detail(self.db, self.company_b.id, issue.id)
		self.assertEqual(raised.exception.status_code, 404)
		resolved = update_issue_status(self.db, self.user, issue.id, IssueStatusUpdate(status="Resolved", resolutionNote="Reviewed source transactions."))
		self.assertEqual(resolved.resolved_by_name, self.user.name)
		self.assertIsNotNone(resolved.resolved_at)
		self.assertEqual(resolved.resolution_note, "Reviewed source transactions.")
		event = self.db.scalar(select(DataQualityIssueEvent).where(DataQualityIssueEvent.issue_id == issue.id))
		self.assertEqual((event.previous_status, event.new_status), ("Open", "Resolved"))
		audit = self.db.scalar(select(AuditLog).where(AuditLog.action == "Data Quality Issue Status Changed"))
		self.assertIsNotNone(audit)
		self.assertEqual(audit.company_id, self.company_a.id)
		with self.assertRaises(HTTPException):
			update_issue_status(self.db, self.other_user, issue.id, IssueStatusUpdate(status="Ignored"))

	def test_targeted_product_recheck_resolves_only_issues_for_that_product(self):
		run_reconciliation(self.db, self.user)
		inventory_issue = self.db.scalar(select(DataQualityIssue).where(DataQualityIssue.issue_type == "product_inventory_quantity_mismatch"))
		sale_issue = self.db.scalar(select(DataQualityIssue).where(DataQualityIssue.issue_type == "sale_inactive_product"))
		self.product.stock_quantity = -3
		self.db.commit()
		resolved = run_incremental_checks(self.db, self.user, product_ids={self.product.id})
		self.assertGreaterEqual(resolved, 1)
		self.db.refresh(inventory_issue)
		self.db.refresh(sale_issue)
		self.assertEqual(inventory_issue.status, "Resolved")
		self.assertEqual(sale_issue.status, "Open")


if __name__ == "__main__":
	unittest.main()