import Inventory2Icon from "@mui/icons-material/Inventory2";
import { Alert, Paper, Stack, Typography } from "@mui/material";
import { InventoryNotificationItem } from "../../../types/catalog";

type Props = {
	notifications: InventoryNotificationItem[];
};

export default function InventoryNotificationsPanel({ notifications }: Props) {
	return (
		<Paper sx={{ p: 2 }}>
			<Stack spacing={1.5}>
				<Stack direction="row" spacing={1} alignItems="center">
					<Inventory2Icon />
					<Typography variant="h6" fontWeight={700}>Inventory Notifications</Typography>
				</Stack>
				{notifications.length === 0 ? (
					<Typography color="text.secondary">No recent inventory notifications.</Typography>
				) : (
					notifications.map((item) => (
						<Alert key={item.id} severity={item.notificationType === "out-of-stock" ? "error" : item.notificationType === "low-stock" ? "warning" : "info"}>
							{item.message} ({new Date(item.createdAt).toLocaleString()})
						</Alert>
					))
				)}
			</Stack>
		</Paper>
	);
}
