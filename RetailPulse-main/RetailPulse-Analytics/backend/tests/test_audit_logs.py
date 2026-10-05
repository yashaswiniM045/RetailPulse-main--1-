import unittest
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.models import AuditLog, Company, User
from src.models.base import Base
from src.models.inventory import Inventory, InventoryMovement, InventoryNotification
from src.models.user import UserRole, UserStatus
from src.routes.audit_logs import _minimal_pdf, router
from src.services.audit_log_service import get_audit_filter_options, get_audit_log, list_audit_logs


class AuditLogTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.company_a = Company(name="Company A", industry="Retail", email="a@example.com", address="A", phone="1")
        self.company_b = Company(name="Company B", industry="Retail", email="b@example.com", address="B", phone="2")
        self.db.add_all([self.company_a, self.company_b])
        self.db.flush()
        self.admin = User(company_id=self.company_a.id, name="Admin A", email="admin-a@example.com", password="hash", role=UserRole.COMPANY_ADMIN, status=UserStatus.ACTIVE)
        self.db.add(self.admin)
        self.db.flush()
        now = datetime.now(UTC)
        self.own_log = AuditLog(company_id=self.company_a.id, user_id=self.admin.id, performed_by=self.admin.name, action="Product Updated", entity_type="Product", resource_id="1024", entity_name="Coffee", description="Price changed", status="success", before_values={"price": 5}, after_values={"price": 6}, created_at=now)
        self.other_log = AuditLog(company_id=self.company_b.id, action="Product Deleted", entity_type="Product", resource_id="9000", description="Other tenant record", status="success", created_at=now + timedelta(seconds=1))
        self.db.add_all([self.own_log, self.other_log])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_list_is_company_scoped_and_filters_paginate_server_side(self):
        result = list_audit_logs(self.db, self.company_a.id, search="1024", resource_type="Product", page=1, page_size=1)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["pageSize"], 1)
        self.assertEqual(result["items"][0]["resourceId"], "1024")
        self.assertEqual(result["items"][0]["beforeValues"], {"price": 5})

    def test_detail_cannot_read_another_company_record(self):
        with self.assertRaises(HTTPException) as raised:
            get_audit_log(self.db, self.company_a.id, self.other_log.id)
        self.assertEqual(raised.exception.status_code, 404)

    def test_filter_options_are_company_scoped(self):
        options = get_audit_filter_options(self.db, self.company_a.id)
        self.assertEqual(options["actions"], ["Product Updated"])
        self.assertEqual(options["resourceTypes"], ["Product"])

    def test_audit_router_exposes_no_mutating_http_methods(self):
        methods = {method for route in router.routes for method in route.methods or set()}
        self.assertEqual(methods, {"GET"})

    def test_pdf_export_creates_multiple_pages_for_long_filtered_results(self):
        pdf = _minimal_pdf("\n".join(f"Audit row {index}: event description" for index in range(120)))
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"/Count 3", pdf)
        self.assertIn(b"Audit row 119", pdf)


if __name__ == "__main__":
    unittest.main()
