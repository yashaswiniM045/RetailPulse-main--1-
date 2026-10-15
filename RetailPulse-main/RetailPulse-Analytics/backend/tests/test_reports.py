import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.models.base import Base
from src.models.category import Category, CategoryStatus
from src.models.company import Company
from src.models.customer import Customer, CustomerStatus, CustomerType
from src.models.inventory import Inventory, InventoryMovement, InventoryMovementType, StockStatus
from src.models.product import Product, ProductStatus
from src.models.sale import PaymentMethod, PaymentStatus, Sale, SaleItem, SalesChannel
from src.models.user import User, UserRole, UserStatus
from src.schemas.reporting import ReportFilters, ScheduleCreate
from src.services.reporting_service import (
	create_scheduled_report,
	delete_scheduled_report,
	export_history,
	generate_report,
	get_report_history,
	get_report_result,
	list_scheduled_reports,
	run_due_schedules,
	set_schedule_active,
)


class ReportingServiceTests(unittest.TestCase):
	def setUp(self):
		self.engine = create_engine("sqlite:///:memory:")
		Base.metadata.create_all(self.engine)
		self.db = Session(self.engine)
		self.company_a = Company(name="North Reports", industry="Retail", email="reports-north@example.com", address="N", phone="1")
		self.company_b = Company(name="South Reports", industry="Retail", email="reports-south@example.com", address="S", phone="2")
		self.db.add_all([self.company_a, self.company_b])
		self.db.flush()
		self.user = User(company_id=self.company_a.id, name="Analyst", email="reports-analyst@example.com", password="hash", role=UserRole.ANALYST, status=UserStatus.ACTIVE)
		self.other_user = User(company_id=self.company_b.id, name="Other Admin", email="reports-admin@example.com", password="hash", role=UserRole.COMPANY_ADMIN, status=UserStatus.ACTIVE)
		self.db.add_all([self.user, self.other_user])
		self.db.flush()
		self.category = Category(company_id=self.company_a.id, name="Home", status=CategoryStatus.ACTIVE)
		other_category = Category(company_id=self.company_b.id, name="Other", status=CategoryStatus.ACTIVE)
		self.db.add_all([self.category, other_category])
		self.db.flush()
		self.product = Product(company_id=self.company_a.id, category_id=self.category.id, name="Mug", sku="MUG-1", unit_price=12, cost_price=4, stock_quantity=5, is_out_of_stock=False, unit_of_measure="each", status=ProductStatus.ACTIVE)
		other_product = Product(company_id=self.company_b.id, category_id=other_category.id, name="Other item", sku="OTHER-1", unit_price=8, cost_price=3, stock_quantity=4, is_out_of_stock=False, unit_of_measure="each", status=ProductStatus.ACTIVE)
		self.db.add_all([self.product, other_product])
		self.db.flush()
		self.customer = Customer(company_id=self.company_a.id, customer_code="C-1", full_name="North Customer", email="customer@north.example", phone_number="555-0100", customer_type=CustomerType.RETAIL, status=CustomerStatus.ACTIVE)
		self.db.add(self.customer)
		self.db.flush()
		inventory = Inventory(company_id=self.company_a.id, product_id=self.product.id, current_stock=5, reserved_stock=1, available_stock=4, reorder_level=2, stock_status=StockStatus.IN_STOCK)
		self.db.add(inventory)
		self.db.flush()
		self.db.add(InventoryMovement(inventory_id=inventory.id, movement_type=InventoryMovementType.STOCK_ADDITION, quantity_changed=5, previous_quantity=0, updated_quantity=5, reason="Initial stock", performed_by=self.user.id))
		for company, product, invoice in [(self.company_a, self.product, "N-1"), (self.company_b, other_product, "S-1")]:
			sale = Sale(company_id=company.id, customer_id=self.customer.id if company == self.company_a else None, invoice_number=invoice, customer_name="North Customer" if company == self.company_a else "Walk-in", sale_date=datetime(2026, 10, 1, tzinfo=timezone.utc), sales_channel=SalesChannel.IN_STORE, payment_method=PaymentMethod.CASH, payment_status=PaymentStatus.PAID, total_amount=12, created_by=self.user.id)
			self.db.add(sale)
			self.db.flush()
			self.db.add(SaleItem(sale_id=sale.id, product_id=product.id, category_id=product.category_id, quantity=2, unit_price=6, discount=0, tax=0, total=12))
		self.db.commit()

	def tearDown(self):
		self.db.close()
		self.engine.dispose()

	def test_combined_report_filters_and_history_are_company_scoped(self):
		result = generate_report(
			self.db,
			self.user,
			"sales",
			ReportFilters(productId=self.product.id, categoryId=self.category.id, startDate="2026-10-01T00:00:00Z", endDate="2026-10-02T00:00:00Z", salesStatus="paid"),
		)
		self.assertEqual(result["page"]["total"], 1)
		self.assertEqual(result["page"]["items"][0]["invoice"], "N-1")
		self.assertIsInstance(result["history"].filters["startDate"], str)
		self.assertEqual(result["history"].total_rows, 1)
		self.assertFalse(hasattr(result["history"], "rows"))
		reloaded = get_report_result(self.db, self.company_a.id, result["history"].id)
		self.assertEqual(reloaded["page"]["items"][0]["invoice"], "N-1")
		csv_content, _, _ = export_history(self.db, self.company_a.id, result["history"].id, "csv")
		self.assertIn(b"Applied filters", csv_content)
		self.assertIn(b"N-1", csv_content)
		pdf_content, _, _ = export_history(self.db, self.company_a.id, result["history"].id, "pdf")
		self.assertTrue(pdf_content.startswith(b"%PDF-1.4"))
		with self.assertRaises(HTTPException) as raised:
			get_report_history(self.db, self.company_b.id, result["history"].id)
		self.assertEqual(raised.exception.status_code, 404)

	def test_scheduled_report_lifecycle_is_company_scoped(self):
		payload = ScheduleCreate(
			name="Weekly sales",
			reportType="sales",
			filters=ReportFilters(productId=self.product.id),
			frequency="weekly",
			executionTime="09:15",
			recipients=["ops@example.com"],
			exportFormat="csv",
		)
		schedule = create_scheduled_report(self.db, self.user, payload)
		self.assertTrue(schedule.is_active)
		self.assertEqual(schedule.filters["productId"], self.product.id)
		self.assertEqual(len(list_scheduled_reports(self.db, self.company_a.id)), 1)
		self.assertEqual(list_scheduled_reports(self.db, self.company_b.id), [])
		with self.assertRaises(HTTPException) as raised:
			set_schedule_active(self.db, self.other_user, schedule.id, False)
		self.assertEqual(raised.exception.status_code, 404)
		schedule = set_schedule_active(self.db, self.user, schedule.id, False)
		self.assertFalse(schedule.is_active)
		delete_scheduled_report(self.db, self.user, schedule.id)
		self.assertEqual(list_scheduled_reports(self.db, self.company_a.id), [])

	def test_every_report_type_reads_company_source_data(self):
		for report_type in ("sales", "inventory", "customers", "product-performance", "stock-movement"):
			with self.subTest(report_type=report_type):
				result = generate_report(self.db, self.user, report_type, ReportFilters())
				self.assertEqual(result["history"].status, "success")
				self.assertEqual(result["page"]["total"], 1)

	def test_due_schedule_records_delivery_failure_and_history(self):
		payload = ScheduleCreate(
			name="Due report",
			reportType="sales",
			filters=ReportFilters(),
			frequency="daily",
			executionTime="09:00",
			recipients=["ops@example.com"],
			exportFormat="csv",
		)
		schedule = create_scheduled_report(self.db, self.user, payload)
		schedule.next_run_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
		self.db.commit()
		with patch.dict("os.environ", {"REPORT_SMTP_HOST": "", "REPORT_SMTP_FROM": ""}):
			run_due_schedules(self.db)
		self.db.refresh(schedule)
		self.assertEqual(schedule.last_status, "failed")
		self.assertIn("REPORT_SMTP_HOST", schedule.last_error or "")
		history = get_report_history(self.db, self.company_a.id, schedule.last_history_id or 0)
		self.assertEqual(history.status, "failed")
		self.assertIsNotNone(history.error_message)


if __name__ == "__main__":
	unittest.main()