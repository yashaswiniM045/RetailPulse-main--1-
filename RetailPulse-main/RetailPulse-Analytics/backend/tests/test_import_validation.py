import unittest

from src.services.import_service import validate_csv_rows


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


if __name__ == "__main__":
    unittest.main()
