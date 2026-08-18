import { MenuItem, Stack, TextField } from "@mui/material";
import { CategoryItem, InventoryStockStatus } from "../../../types/catalog";

type Props = {
	search: string;
	onSearchChange: (value: string) => void;
	categoryFilter: number | "all";
	onCategoryChange: (value: number | "all") => void;
	brandFilter: string;
	onBrandChange: (value: string) => void;
	brands: string[];
	stockStatusFilter: InventoryStockStatus | "all";
	onStockStatusChange: (value: InventoryStockStatus | "all") => void;
	sortBy: "name" | "currentStock" | "recentlyUpdated";
	onSortByChange: (value: "name" | "currentStock" | "recentlyUpdated") => void;
	sortDirection: "asc" | "desc";
	onSortDirectionChange: (value: "asc" | "desc") => void;
	categories: CategoryItem[];
};

export default function InventoryFiltersBar({
	search,
	onSearchChange,
	categoryFilter,
	onCategoryChange,
	brandFilter,
	onBrandChange,
	brands,
	stockStatusFilter,
	onStockStatusChange,
	sortBy,
	onSortByChange,
	sortDirection,
	onSortDirectionChange,
	categories,
}: Props) {
	return (
		<Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems={{ lg: "center" }} justifyContent="space-between">
			<TextField fullWidth label="Search by product name or SKU" value={search} onChange={(event) => onSearchChange(event.target.value)} />
			<TextField select label="Category" value={categoryFilter} onChange={(event) => onCategoryChange(event.target.value === "all" ? "all" : Number(event.target.value))} sx={{ minWidth: 170 }}>
				<MenuItem value="all">All Categories</MenuItem>
				{categories.map((category) => <MenuItem key={category.id} value={category.id}>{category.name}</MenuItem>)}
			</TextField>
			<TextField select label="Brand" value={brandFilter || "all"} onChange={(event) => onBrandChange(event.target.value === "all" ? "" : event.target.value)} sx={{ minWidth: 170 }}>
				<MenuItem value="all">All Brands</MenuItem>
				{brands.map((brand) => <MenuItem key={brand} value={brand}>{brand}</MenuItem>)}
			</TextField>
			<TextField select label="Status" value={stockStatusFilter} onChange={(event) => onStockStatusChange(event.target.value as InventoryStockStatus | "all")} sx={{ minWidth: 150 }}>
				<MenuItem value="all">All Status</MenuItem>
				<MenuItem value="in-stock">In Stock</MenuItem>
				<MenuItem value="low-stock">Low Stock</MenuItem>
				<MenuItem value="out-of-stock">Out of Stock</MenuItem>
			</TextField>
			<TextField select label="Sort" value={sortBy} onChange={(event) => onSortByChange(event.target.value as "name" | "currentStock" | "recentlyUpdated")} sx={{ minWidth: 150 }}>
				<MenuItem value="recentlyUpdated">Recently Updated</MenuItem>
				<MenuItem value="name">Product Name</MenuItem>
				<MenuItem value="currentStock">Current Stock</MenuItem>
			</TextField>
			<TextField select label="Direction" value={sortDirection} onChange={(event) => onSortDirectionChange(event.target.value as "asc" | "desc")} sx={{ minWidth: 130 }}>
				<MenuItem value="desc">Desc</MenuItem>
				<MenuItem value="asc">Asc</MenuItem>
			</TextField>
		</Stack>
	);
}
