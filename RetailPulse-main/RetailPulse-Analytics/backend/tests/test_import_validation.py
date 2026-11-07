import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.models.base import Base
from src.models.category import Category, CategoryStatus
from src.models.company import Company
from src.models.import_history import ImportHistory, ImportJob, ImportStatus
from src.models.inventory import Inventory, InventoryMovement, StockStatus
from src.models.product import Product
from src.models.user import User
from src.models.user import UserRole, UserStatus
from src.services.import_service import (
    create_staged_import,
    run_staged_import,
    start_staged_import,
    validate_csv_rows,
)


class ImportValidationTests(unittest.TestCase):
    def test_valid_product_rows_pass(self):
        rows = [
            {"Product Name": "Laptop", "SKU": "LP001", "Category": "Electronics", "Unit Price": "80000", "Stock Quantity": "20"},
            {"Product Name": "Monitor", "SKU": "MN001", "Category": "Electronics", "Unit Price": "25000", "Stock Quantity": "15"},
        ]
        result = validate_csv_rows("products", rows, category_names={"Electronics"})
        self.assertEqual(result["valid_count"], 2)
        self.assertEqual(result["invalid_count"], 0)
        self.assertEqual(result["duplicate_count"], 0)

    def test_missing_product_name_is_invalid(self):
        rows = [{"Product Name": "", "SKU": "LP001", "Category": "Electronics", "Unit Price": "80000", "Stock Quantity": "20"}]
        result = validate_csv_rows("products", rows, category_names={"Electronics"})
        self.assertEqual(result["valid_count"], 0)
        self.assertEqual(result["invalid_count"], 1)
        self.assertTrue(result["issues"][0]["message"].startswith("Product Name"))

    def test_inventory_rows_are_validated_and_duplicate_skus_rejected(self):
        rows = [
            {"SKU": "SKU-1", "Quantity": "8", "Reorder Level": "3"},
            {"SKU": "sku-1", "Quantity": "9", "Reorder Level": "3"},
        ]
        result = validate_csv_rows("inventory", rows)
        self.assertEqual(result["valid_count"], 1)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["issues"][0]["errorType"], "duplicate")

    def test_staged_product_import_runs_and_creates_inventory(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = Session(engine)
        company = Company(
            name="Import Test",
            industry="Retail",
            email="import@example.com",
            address="Main Street",
            phone="5550100",
        )
        db.add(company)
        db.flush()
        user = User(
            company_id=company.id,
            name="Import Admin",
            email="admin-import@example.com",
            password="test-password",
            role=UserRole.COMPANY_ADMIN,
            status=UserStatus.ACTIVE,
        )
        category = Category(company_id=company.id, name="Electronics", status=CategoryStatus.ACTIVE)
        db.add_all([user, category])
        db.commit()
        rows = [{
            "Product Name": "Laptop",
            "SKU": "LP001",
            "Category": "Electronics",
            "Unit Price": "80000",
            "Stock Quantity": "20",
        }]
        record, summary = create_staged_import(db, user, "products", "products.csv", rows)
        self.assertEqual(summary["valid_count"], 1)
        start_staged_import(db, user, record.id)
        with patch("src.services.import_service.SessionLocal", side_effect=lambda: Session(engine)):
            run_staged_import(record.id)
        db.expire_all()
        completed = db.get(ImportHistory, record.id)
        product = db.scalar(select(Product).where(Product.sku == "LP001"))
        inventory = db.scalar(select(Inventory).where(Inventory.product_id == product.id))
        job = db.get(ImportJob, record.id)
        self.assertEqual(completed.status, ImportStatus.COMPLETED.value)
        self.assertEqual(completed.successful_records, 1)
        self.assertEqual(inventory.current_stock, 20)
        self.assertEqual(job.source_data, "[]")
        db.close()
        engine.dispose()

    def test_inventory_import_updates_existing_stock_and_records_movement(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = Session(engine)
        company = Company(
            name="Inventory Import Test",
            industry="Retail",
            email="inventory-import@example.com",
            address="Main Street",
            phone="5550103",
        )
        db.add(company)
        db.flush()
        user = User(
            company_id=company.id,
            name="Inventory Admin",
            email="inventory-admin@example.com",
            password="test-password",
            role=UserRole.COMPANY_ADMIN,
            status=UserStatus.ACTIVE,
        )
        category = Category(company_id=company.id, name="Home", status=CategoryStatus.ACTIVE)
        db.add_all([user, category])
        db.flush()
        product = Product(
            company_id=company.id,
            category_id=category.id,
            name="Desk",
            sku="DSK-1",
            unit_price=100,
            cost_price=50,
            stock_quantity=3,
            is_out_of_stock=False,
            unit_of_measure="each",
        )
        db.add(product)
        db.flush()
        inventory = Inventory(
            company_id=company.id,
            product_id=product.id,
            current_stock=3,
            reserved_stock=0,
            available_stock=3,
            reorder_level=1,
            stock_status=StockStatus.IN_STOCK,
        )
        db.add(inventory)
        db.commit()
        rows = [{"SKU": "DSK-1", "Quantity": "12", "Reorder Level": "4"}]
        record, _ = create_staged_import(db, user, "inventory", "inventory.csv", rows)
        start_staged_import(db, user, record.id)
        with patch("src.services.import_service.SessionLocal", side_effect=lambda: Session(engine)):
            run_staged_import(record.id)
        db.expire_all()
        self.assertEqual(db.get(Product, product.id).stock_quantity, 12)
        self.assertEqual(db.get(Inventory, inventory.id).current_stock, 12)
        movement = db.scalar(
            select(InventoryMovement).where(InventoryMovement.inventory_id == inventory.id)
        )
        self.assertEqual(movement.previous_quantity, 3)
        self.assertEqual(movement.updated_quantity, 12)
        self.assertEqual(db.get(ImportHistory, record.id).successful_records, 1)
        db.close()
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
