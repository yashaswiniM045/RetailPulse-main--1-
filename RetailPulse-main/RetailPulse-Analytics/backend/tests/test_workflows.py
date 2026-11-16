import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.models.base import Base
from src.models.category import Category, CategoryStatus
from src.models.company import Company
from src.models.inventory import Inventory, InventoryMovement
from src.models.product import Product
from src.models.user import User, UserRole, UserStatus
from src.models.workflow import ApprovalHistory, ApprovalRequest, WorkflowConfiguration
from src.schemas.workflow import ApprovalRequestCreate
from src.services.workflow_service import (
    approve_workflow_request,
    create_workflow_request,
    get_pending_approval_count,
    list_workflow_requests,
    reject_workflow_request,
)


class WorkflowServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.company = Company(name="North Shop", industry="Retail", email="north@example.com", address="N", phone="1")
        self.other_company = Company(name="South Shop", industry="Retail", email="south@example.com", address="S", phone="2")
        self.db.add_all([self.company, self.other_company])
        self.db.flush()
        self.requester = User(
            company_id=self.company.id,
            name="Analyst",
            email="analyst@north.example",
            password="not-used",
            role=UserRole.ANALYST,
            status=UserStatus.ACTIVE,
        )
        self.approver = User(
            company_id=self.company.id,
            name="Approver",
            email="admin@north.example",
            password="not-used",
            role=UserRole.COMPANY_ADMIN,
            status=UserStatus.ACTIVE,
        )
        self.other_approver = User(
            company_id=self.other_company.id,
            name="Other Admin",
            email="admin@south.example",
            password="not-used",
            role=UserRole.COMPANY_ADMIN,
            status=UserStatus.ACTIVE,
        )
        self.db.add_all([self.requester, self.approver, self.other_approver])
        self.db.flush()
        self.category = Category(company_id=self.company.id, name="Hardware", status=CategoryStatus.ACTIVE)
        self.db.add(self.category)
        self.db.flush()
        self.product = Product(
            company_id=self.company.id,
            category_id=self.category.id,
            name="Bolt",
            sku="BOLT-1",
            unit_price=10,
            cost_price=4,
            stock_quantity=10,
            is_out_of_stock=False,
            unit_of_measure="each",
        )
        self.db.add(self.product)
        self.db.flush()
        self.inventory = Inventory(
            company_id=self.company.id,
            product_id=self.product.id,
            current_stock=10,
            reserved_stock=0,
            available_stock=10,
            reorder_level=2,
            stock_status="in-stock",
        )
        self.db.add(self.inventory)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create_stock_request(self, requester=None):
        return create_workflow_request(
            self.db,
            requester or self.requester,
            ApprovalRequestCreate(
                requestType="stock-adjustment",
                relatedRecordId=self.product.id,
                requestedChanges={"targetQuantity": 15},
                reason="Physical count reconciliation",
                priority="high",
            ),
        )

    def test_stock_is_unchanged_until_approval_then_applied_once(self):
        pending = self.create_stock_request()
        self.assertEqual(pending["status"], "pending-approval")
        self.assertEqual(self.inventory.current_stock, 10)

        approved = approve_workflow_request(self.db, self.approver, pending["id"], "Count verified", None)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(self.inventory.current_stock, 15)
        self.assertEqual(self.product.stock_quantity, 15)
        self.assertEqual(self.db.scalar(select(InventoryMovement).where(InventoryMovement.inventory_id == self.inventory.id)).quantity_changed, 5)
        self.assertEqual(
            [item.action for item in self.db.scalars(select(ApprovalHistory).where(ApprovalHistory.request_id == pending["id"]).order_by(ApprovalHistory.id))],
            ["created", "submitted", "pending-approval", "approved", "change-applied"],
        )
        with self.assertRaises(HTTPException) as raised:
            approve_workflow_request(self.db, self.approver, pending["id"], None, None)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(self.inventory.current_stock, 15)

    def test_rejection_preserves_business_data_and_cannot_be_approved(self):
        pending = self.create_stock_request()
        rejected = reject_workflow_request(self.db, self.approver, pending["id"], "Count sheet was not signed", None)
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(self.inventory.current_stock, 10)
        with self.assertRaises(HTTPException) as raised:
            approve_workflow_request(self.db, self.approver, pending["id"], None, None)
        self.assertEqual(raised.exception.status_code, 409)

    def test_product_price_is_unchanged_until_approval(self):
        request = create_workflow_request(
            self.db,
            self.requester,
            ApprovalRequestCreate(
                requestType="product-price-change",
                relatedRecordId=self.product.id,
                requestedChanges={"unitPrice": 12.5},
                reason="Seasonal price adjustment",
            ),
        )
        self.assertEqual(float(self.product.unit_price), 10)
        approve_workflow_request(self.db, self.approver, request["id"], None, None)
        self.assertEqual(float(self.product.unit_price), 12.5)

    def test_only_one_open_request_per_record_and_workflow(self):
        self.create_stock_request()
        with self.assertRaises(HTTPException) as raised:
            self.create_stock_request()
        self.assertEqual(raised.exception.status_code, 409)

    def test_company_scoped_queue_mine_and_pending_counts(self):
        created = self.create_stock_request()
        queue = list_workflow_requests(self.db, self.approver, scope="queue")
        mine = list_workflow_requests(self.db, self.requester, scope="mine")
        self.assertEqual([item["id"] for item in queue["items"]], [created["id"]])
        self.assertEqual([item["id"] for item in mine["items"]], [created["id"]])
        self.assertEqual(get_pending_approval_count(self.db, self.approver)["pendingApprovalCount"], 1)
        other_queue = list_workflow_requests(self.db, self.other_approver, scope="queue")
        self.assertEqual(other_queue["total"], 0)

    def test_other_company_cannot_read_or_approve_request(self):
        pending = self.create_stock_request()
        with self.assertRaises(HTTPException) as raised:
            approve_workflow_request(self.db, self.other_approver, pending["id"], None, None)
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(self.inventory.current_stock, 10)

    def test_requester_cannot_approve_without_explicit_self_approval(self):
        own_request = self.create_stock_request(self.approver)
        with self.assertRaises(HTTPException) as raised:
            approve_workflow_request(self.db, self.approver, own_request["id"], None, None)
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(self.inventory.current_stock, 10)

    def test_configured_self_approval_can_be_enabled_explicitly(self):
        config = WorkflowConfiguration(
            company_id=self.company.id,
            request_type="product-price-change",
            approver_role=UserRole.COMPANY_ADMIN.value,
            approval_required=True,
            allow_self_approval=True,
            is_active=True,
        )
        self.db.add(config)
        self.db.commit()
        own_request = create_workflow_request(
            self.db,
            self.approver,
            ApprovalRequestCreate(
                requestType="product-price-change",
                relatedRecordId=self.product.id,
                requestedChanges={"unitPrice": 12.5},
                reason="Approved seasonal price update",
            ),
        )
        approved = approve_workflow_request(self.db, self.approver, own_request["id"], None, None)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(float(self.product.unit_price), 12.5)

    def test_import_type_is_company_scoped_and_validates_requested_changes(self):
        with self.assertRaises(HTTPException) as raised:
            create_workflow_request(
                self.db,
                self.requester,
                ApprovalRequestCreate(
                    requestType="inventory-import-approval",
                    relatedRecordId=999,
                    requestedChanges={"action": "start-import"},
                    reason="Import approved",
                ),
            )
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(self.db.scalar(select(ApprovalRequest.id)), None)


if __name__ == "__main__":
    unittest.main()
