import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField, Typography } from "@mui/material";
import { InventoryItem } from "../../../types/catalog";

type Props = {
	open: boolean;
	item: InventoryItem | null;
	reorderLevel: number;
	onReorderLevelChange: (value: number) => void;
	reason: string;
	onReasonChange: (value: string) => void;
	onClose: () => void;
	onSubmit: () => void;
	saving: boolean;
};

export default function InventoryReorderDialog({
	open,
	item,
	reorderLevel,
	onReorderLevelChange,
	reason,
	onReasonChange,
	onClose,
	onSubmit,
	saving,
}: Props) {
	return (
		<Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
			<DialogTitle>Update Reorder Level</DialogTitle>
			<DialogContent>
				<Stack spacing={2} sx={{ pt: 1 }}>
					<Typography color="text.secondary">{item?.productName} ({item?.sku})</Typography>
					<TextField type="number" label="Reorder Level" value={reorderLevel} onChange={(event) => onReorderLevelChange(Number(event.target.value))} inputProps={{ min: 0 }} />
					<TextField label="Reason" value={reason} onChange={(event) => onReasonChange(event.target.value)} required />
				</Stack>
			</DialogContent>
			<DialogActions>
				<Button onClick={onClose} color="inherit">Cancel</Button>
				<Button variant="contained" onClick={onSubmit} disabled={saving}>Update</Button>
			</DialogActions>
		</Dialog>
	);
}
