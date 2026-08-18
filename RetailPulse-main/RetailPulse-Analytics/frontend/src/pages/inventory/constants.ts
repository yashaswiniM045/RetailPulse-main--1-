import { InventoryMovementType, InventoryStockStatus } from "../../types/catalog";

export const stockStatusColor: Record<InventoryStockStatus, "success" | "warning" | "error"> = {
	"in-stock": "success",
	"low-stock": "warning",
	"out-of-stock": "error",
};

export const stockStatusLabel: Record<InventoryStockStatus, string> = {
	"in-stock": "In Stock",
	"low-stock": "Low Stock",
	"out-of-stock": "Out of Stock",
};

export const movementTypeLabel: Record<InventoryMovementType, string> = {
	sale: "Sale",
	"manual-adjustment": "Manual Adjustment",
	"stock-addition": "Stock Addition",
	"stock-removal": "Stock Removal",
};
