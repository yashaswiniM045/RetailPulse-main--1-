import { Alert, Stack, Typography } from "@mui/material";

export default function ForgotPassword() {
	return (
		<Stack spacing={2}>
			<Typography variant="h4" fontWeight={800}>
				Forgot Password
			</Typography>
			<Alert severity="info">
				Password reset flow is not part of this foundation task. The backend includes password change auditing for authenticated users.
			</Alert>
		</Stack>
	);
}
