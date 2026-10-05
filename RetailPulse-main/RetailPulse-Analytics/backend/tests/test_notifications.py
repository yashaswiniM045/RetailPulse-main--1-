import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.models import Category, Company, Notification, Product, User
from src.models.base import Base
from src.models.category import CategoryStatus
from src.models.product import ProductStatus
from src.models.user import UserRole, UserStatus
from src.services.inventory_service import evaluate_inventory_alerts
from src.services.notification_service import (
    create_notification,
    get_unread_count,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    resolve_notification,
)


class NotificationServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.company_a = Company(name="North Shop", industry="Retail", email="north@example.com", address="N", phone="1")
        self.company_b = Company(name="South Shop", industry="Retail", email="south@example.com", address="S", phone="2")
        self.db.add_all([self.company_a, self.company_b])
        self.db.flush()
        self.admin = User(company_id=self.company_a.id, name="Admin", email="admin@north.example", password="hash", role=UserRole.COMPANY_ADMIN, status=UserStatus.ACTIVE)
        self.analyst = User(company_id=self.company_a.id, name="Analyst", email="analyst@north.example", password="hash", role=UserRole.ANALYST, status=UserStatus.ACTIVE)
        self.viewer = User(company_id=self.company_a.id, name="Viewer", email="viewer@north.example", password="hash", role=UserRole.VIEWER, status=UserStatus.ACTIVE)
        self.other_admin = User(company_id=self.company_b.id, name="Other Admin", email="admin@south.example", password="hash", role=UserRole.COMPANY_ADMIN, status=UserStatus.ACTIVE)
        self.db.add_all([self.admin, self.analyst, self.viewer, self.other_admin])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def emit_low_stock(self):
        return create_notification(
            self.db,
            company_id=self.company_a.id,
            event_key="inventory:product-7:low-stock",
            notification_type="low-stock",
            title="Reorder alert",
            message="Product is below reorder point",
            priority="medium",
            resource_type="Product",
            resource_id=7,
            details={"currentStock": 2, "reorderPoint": 5},
        )

    def test_role_targeting_and_deduplication(self):
        self.assertEqual(self.emit_low_stock(), 2)
        self.assertEqual(self.emit_low_stock(), 0)
        self.db.commit()
        self.assertEqual(get_unread_count(self.db, self.admin), 1)
        self.assertEqual(get_unread_count(self.db, self.analyst), 1)
        self.assertEqual(get_unread_count(self.db, self.viewer), 0)
        self.assertEqual(get_unread_count(self.db, self.other_admin), 0)

    def test_mark_read_is_user_scoped_and_read_all_only_updates_unread(self):
        self.emit_low_stock()
        self.db.commit()
        admin_item = self.db.query(Notification).filter_by(user_id=self.admin.id).one()
        with self.assertRaises(HTTPException) as raised:
            mark_notification_read(self.db, self.analyst, admin_item.id)
        self.assertEqual(raised.exception.status_code, 404)
        item, changed = mark_notification_read(self.db, self.admin, admin_item.id)
        self.assertTrue(changed)
        self.assertTrue(item.is_read)
        self.db.commit()
        self.assertEqual(mark_all_notifications_read(self.db, self.admin), 0)
        self.assertEqual(get_unread_count(self.db, self.admin), 0)

    def test_filters_are_combined_and_paginated(self):
        self.emit_low_stock()
        create_notification(
            self.db,
            company_id=self.company_a.id,
            event_key="sale:45:high-value",
            notification_type="sales-alert",
            title="High-value sale",
            message="Sale reached threshold",
            priority="medium",
            resource_type="Sale",
            resource_id=45,
        )
        self.db.commit()
        page = list_notifications(self.db, user=self.admin, page=1, page_size=1, read_filter="unread", notification_type="low-stock", priority="medium")
        self.assertEqual(page["total"], 1)
        self.assertEqual(len(page["items"]), 1)
        self.assertEqual(page["items"][0].resource_type, "Product")

    def test_resolved_condition_expires_after_lifecycle_and_reopens_same_row(self):
        self.emit_low_stock()
        self.db.commit()
        original = self.db.query(Notification).filter_by(user_id=self.admin.id).one()
        resolve_notification(self.db, company_id=self.company_a.id, event_key="inventory:product-7:low-stock")
        self.db.commit()
        self.assertIsNotNone(original.resolved_at)
        self.emit_low_stock()
        self.db.commit()
        notifications = self.db.query(Notification).filter_by(user_id=self.admin.id).all()
        self.assertEqual(len(notifications), 1)
        self.assertIsNone(notifications[0].resolved_at)
        self.assertFalse(notifications[0].is_read)

    def test_inventory_evaluation_emits_critical_and_low_stock_notifications(self):
        category = Category(company_id=self.company_a.id, name="Hardware", status=CategoryStatus.ACTIVE)
        self.db.add(category)
        self.db.flush()
        out_product = Product(company_id=self.company_a.id, category_id=category.id, name="Out Item", sku="OUT-1", unit_price=10, cost_price=5, stock_quantity=0, is_out_of_stock=True, unit_of_measure="units", status=ProductStatus.ACTIVE)
        low_product = Product(company_id=self.company_a.id, category_id=category.id, name="Low Item", sku="LOW-1", unit_price=10, cost_price=5, stock_quantity=3, is_out_of_stock=False, unit_of_measure="units", status=ProductStatus.ACTIVE)
        self.db.add_all([out_product, low_product])
        self.db.flush()
        evaluate_inventory_alerts(self.db, out_product)
        evaluate_inventory_alerts(self.db, low_product)
        self.db.commit()
        stockout = self.db.query(Notification).filter_by(user_id=self.admin.id, event_key=f"inventory:{out_product.id}:stockout").one()
        low_stock = self.db.query(Notification).filter_by(user_id=self.analyst.id, event_key=f"inventory:{low_product.id}:low-stock").one()
        self.assertEqual(stockout.priority, "critical")
        self.assertEqual(stockout.details["currentStock"], 0)
        self.assertEqual(low_stock.priority, "medium")
        self.assertEqual(low_stock.details["reorderPoint"], 5)


if __name__ == "__main__":
    unittest.main()
