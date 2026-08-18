import { Box, Button, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { InventoryMovementItem, InventoryMovementType } from "../../../types/catalog";
import { movementTypeLabel } from "../constants";

type Props = {
	items: InventoryMovementItem[];
	total: number;
	page: number;
	pageSize: number;
	totalPages: number;
	movementFilterType: InventoryMovementType | "all";
	onMovementFilterTypeChange: (value: InventoryMovementType | "all") => void;
	onPageChange: (value: number) => void;
	onPageSizeChange: (value: number) => void;
};

export default function MovementHistoryTable({
	items,
	total,
	page,
	pageSize,
	totalPages,
	movementFilterType,
	onMovementFilterTypeChange,
	onPageChange,
	onPageSizeChange,
}: Props) {
	return (
		<Stack spacing={2}>
			<Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between" alignItems={{ md: "center" }}>
				<Typography variant="h6" fontWeight={700}>Stock Movement History</Typography>
				<TextField select label="Movement Type" value={movementFilterType} onChange={(event) => onMovementFilterTypeChange(event.target.value as InventoryMovementType | "all")} sx={{ minWidth: 200 }}>
					<MenuItem value="all">All</MenuItem>
					<MenuItem value="sale">Sale</MenuItem>
					<MenuItem value="manual-adjustment">Manual Adjustment</MenuItem>
					<MenuItem value="stock-addition">Stock Addition</MenuItem>
					<MenuItem value="stock-removal">Stock Removal</MenuItem>
				</TextField>
			</Stack>

			<Box sx={{ overflowX: "auto" }}>
				<table style={{ width: "100%", borderCollapse: "collapse" }}>
					<thead>
						<tr>
							{["Product", "Movement", "Previous", "Updated", "Changed", "Reason", "By", "Date"].map((heading) => (
								<th key={heading} style={{ textAlign: "left", padding: "12px 8px", borderBottom: "1px solid #e5ddd0" }}>{heading}</th>
							))}
						</tr>
					</thead>
					<tbody>
						{items.map((movement) => (
							<tr key={movement.id}>
								<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{movement.productName}</td>
								<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{movementTypeLabel[movement.movementType]}</td>
								<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{movement.previousQuantity}</td>
								<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{movement.updatedQuantity}</td>
								<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de", fontWeight: 700 }}>{movement.quantityChanged > 0 ? `+${movement.quantityChanged}` : movement.quantityChanged}</td>
								<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{movement.reason}</td>
								<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{movement.performedBy ?? "System"}</td>
								<td style={{ padding: "12px 8px", borderBottom: "1px solid #f0e9de" }}>{new Date(movement.createdAt).toLocaleString()}</td>
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
