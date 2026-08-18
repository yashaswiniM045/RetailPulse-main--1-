import { Button, Stack, TextField, Typography } from "@mui/material";
import { useForm } from "react-hook-form";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useNotification } from "../../context/NotificationContext";
import { LoginPayload } from "../../types/auth";

export default function Login() {
	const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginPayload>();
	const { loginUser } = useAuth();
	const { notify } = useNotification();
	const navigate = useNavigate();

	const onSubmit = handleSubmit(async (values) => {
		try {
			await loginUser(values);
			notify("Login successful", "success");
			navigate("/dashboard");
		} catch (error) {
			notify("Unable to login. Check your credentials.", "error");
		}
	});

	return (
		<form onSubmit={onSubmit}>
			<Stack spacing={3}>
				<div>
					<Typography variant="h4" fontWeight={800}>
						Sign in
					</Typography>
					<Typography color="text.secondary">
						Access your company-scoped analytics dashboard.
					</Typography>
				</div>
				<TextField
					label="Email"
					type="email"
					{...register("email", { required: "Email is required" })}
					error={Boolean(errors.email)}
					helperText={errors.email?.message}
				/>
				<TextField
					label="Password"
					type="password"
					{...register("password", { required: "Password is required" })}
					error={Boolean(errors.password)}
					helperText={errors.password?.message}
				/>
				<Button type="submit" variant="contained" size="large" disabled={isSubmitting}>
					{isSubmitting ? "Signing in..." : "Login"}
				</Button>
				<Button component={RouterLink} to="/forgot-password" color="inherit">
					Forgot password?
				</Button>
				<Typography color="text.secondary">
					New company? <RouterLink to="/register">Register here</RouterLink>
				</Typography>
			</Stack>
		</form>
	);
}
