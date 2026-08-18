import { Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { InventoryAdjustmentType, InventoryItem } from "../../../types/catalog";

type Props = {
	open: boolean;
	item: InventoryItem | null;
	adjustmentType: InventoryAdjustmentType;
	onAdjustmentTypeChange: (value: InventoryAdjustmentType) => void;
	adjustmentQuantity: number;
	onAdjustmentQuantityChange: (value: number) => void;
	targetQuantity: number;
	onTargetQuantityChange: (value: number) => void;
	reason: string;
	onReasonChange: (value: string) => void;
	remarks: string;
	onRemarksChange: (value: string) => void;
	onClose: () => void;
	onSubmit: () => void;
	saving: boolean;
};

export default function InventoryAdjustmentDialog({
	open,
	item,
	adjustmentType,
	onAdjustmentTypeChange,
	adjustmentQuantity,
	onAdjustmentQuantityChange,
	targetQuantity,
	onTargetQuantityChange,
	reason,
	onReasonChange,
	remarks,
	onRemarksChange,
	onClose,
	onSubmit,
	saving,
}: Props) {
	return (
		<Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
			<DialogTitle>Adjust Stock</DialogTitle>
			<DialogContent>
				<Stack spacing={2} sx={{ pt: 1 }}>
					<Typography color="text.secondary">{item?.productName} ({item?.sku})</Typography>
					<TextField select label="Adjustment Type" value={adjustmentType} onChange={(event) => onAdjustmentTypeChange(event.target.value as InventoryAdjustmentType)}>
						<MenuItem value="stock-addition">Stock Addition</MenuItem>
						<MenuItem value="stock-removal">Stock Removal</MenuItem>
						<MenuItem value="manual-adjustment">Manual Adjustment</MenuItem>
					</TextField>
					{adjustmentType === "manual-adjustment" ? (
						<TextField type="number" label="Target Quantity" value={targetQuantity} onChange={(event) => onTargetQuantityChange(Number(event.target.value))} inputProps={{ min: 0 }} />
					) : (
						<TextField type="number" label="Quantity" value={adjustmentQuantity} onChange={(event) => onAdjustmentQuantityChange(Number(event.target.value))} inputProps={{ min: 1 }} />
					)}
					<TextField label="Reason" value={reason} onChange={(event) => onReasonChange(event.target.value)} required />
					<TextField label="Remarks" value={remarks} onChange={(event) => onRemarksChange(event.target.value)} multiline minRows={2} />
				</Stack>
			</DialogContent>
			<DialogActions>
				<Button onClick={onClose} color="inherit">Cancel</Button>
				<Button variant="contained" onClick={onSubmit} disabled={saving}>Save</Button>
			</DialogActions>
		</Dialog>
	);
}
