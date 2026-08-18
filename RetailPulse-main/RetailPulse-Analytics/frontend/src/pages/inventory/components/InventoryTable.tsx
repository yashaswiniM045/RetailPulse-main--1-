import EditIcon from "@mui/icons-material/Edit";
import { Box, Button, Chip, IconButton, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { InventoryItem } from "../../../types/catalog";
import { stockStatusColor, stockStatusLabel } from "../constants";

type Props = {
	items: InventoryItem[];
	isAdmin: boolean;
	onAdjust: (item: InventoryItem) => void;
	onReorder: (item: InventoryItem) => void;
	total: number;
	page: number;
	pageSize: number;
	totalPages: number;
	onPageChange: (page: number) => void;
	onPageSizeChange: (size: number) => void;
};

export default function InventoryTable({
	items,
	isAdmin,
	onAdjust,
	onReorder,
	total,
	page,
	pageSize,
	totalPages,
	onPageChange,
	onPageSizeChange,
}: Props) {
	return (
		<Stack spacing={2}>
			<Box sx={{ overflowX: "auto" }}>
				<table style={{ width: "100%", borderCollapse: "collapse" }}>
					<thead>
						<tr>
							{["Product", "SKU", "Category", "Brand", "Current", "Reserved", "Available", "Reorder", "Status", "Actions"].map((heading) => (
								<th key={heading} style={{ textAlign: "left", padding: "12px 8px", borderBottom: "1px solid #e5ddd0" }}>{heading}</th>
							))}
						</tr>
					</thead>
					<tbody>
						{items.map((item) => (
							<tr key={item.id}>
								<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de", fontWeight: 600 }}>{item.productName}</td>
								<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{item.sku}</td>
								<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{item.category}</td>
								<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{item.brand ?? "-"}</td>
								<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{item.currentStock}</td>
								<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{item.reservedStock}</td>
								<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{item.availableStock}</td>
								<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>{item.reorderLevel}</td>
								<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>
									<Chip size="small" color={stockStatusColor[item.stockStatus]} label={stockStatusLabel[item.stockStatus]} />
								</td>
								<td style={{ padding: "14px 8px", borderBottom: "1px solid #f0e9de" }}>
									{isAdmin ? (
										<Stack direction="row" spacing={1}>
											<Button size="small" variant="outlined" onClick={() => onAdjust(item)}>Adjust</Button>
											<IconButton size="small" onClick={() => onReorder(item)}><EditIcon fontSize="small" /></IconButton>
										</Stack>
									) : (
										<Typography color="text.secondary" fontSize={12}>Read only</Typography>
									)}
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</Box>

			<Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between" alignItems={{ md: "center" }}>
				<Typography color="text.secondary">Showing {total === 0 ? 0 : (page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)} of {total}</Typography>
				<Stack direction="row" spacing={1} alignItems="center">
					<TextField select size="small" label="Rows" value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))} sx={{ minWidth: 110 }}>
						{[10, 25, 50].map((size) => <MenuItem key={size} value={size}>{size}</MenuItem>)}
					</TextField>
					<Button variant="outlined" disabled={page <= 1} onClick={() => onPageChange(Math.max(page - 1, 1))}>Previous</Button>
					<Button variant="outlined" disabled={totalPages === 0 || page >= totalPages} onClick={() => onPageChange(page + 1)}>Next</Button>
				</Stack>
			</Stack>
		</Stack>
	);
}
