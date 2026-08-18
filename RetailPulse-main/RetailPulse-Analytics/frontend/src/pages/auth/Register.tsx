import { Button, Grid, Stack, TextField, Typography } from "@mui/material";
import { useForm } from "react-hook-form";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useNotification } from "../../context/NotificationContext";
import { RegisterPayload } from "../../types/auth";

export default function Register() {
	const {
		register,
		handleSubmit,
		watch,
		formState: { errors, isSubmitting },
	} = useForm<RegisterPayload>();
	const { registerUser } = useAuth();
	const { notify } = useNotification();
	const navigate = useNavigate();
	const passwordValue = watch("password");

	const onSubmit = handleSubmit(async (values) => {
		try {
			await registerUser(values);
			notify("Company registered successfully", "success");
			navigate("/dashboard");
		} catch {
			notify("Unable to register company. Check for duplicate email entries.", "error");
		}
	});

	return (
		<form onSubmit={onSubmit}>
			<Stack spacing={3}>
				<div>
					<Typography variant="h4" fontWeight={800}>
						Register your company
					</Typography>
					<Typography color="text.secondary">
						Create the company record and the first company admin in one step.
					</Typography>
				</div>
				<Grid container spacing={2}>
					<Grid size={{ xs: 12, md: 6 }}>
						<TextField fullWidth label="Company Name" {...register("companyName", { required: "Company name is required" })} error={Boolean(errors.companyName)} helperText={errors.companyName?.message} />
					</Grid>
					<Grid size={{ xs: 12, md: 6 }}>
						<TextField fullWidth label="Industry" {...register("industry", { required: "Industry is required" })} error={Boolean(errors.industry)} helperText={errors.industry?.message} />
					</Grid>
					<Grid size={{ xs: 12, md: 6 }}>
						<TextField fullWidth label="Company Email" type="email" {...register("companyEmail", { required: "Company email is required" })} error={Boolean(errors.companyEmail)} helperText={errors.companyEmail?.message} />
					</Grid>
					<Grid size={{ xs: 12, md: 6 }}>
						<TextField fullWidth label="Company Phone Number" {...register("companyPhoneNumber", { required: "Phone number is required" })} error={Boolean(errors.companyPhoneNumber)} helperText={errors.companyPhoneNumber?.message} />
					</Grid>
					<Grid size={{ xs: 12 }}>
						<TextField fullWidth label="Company Address" {...register("companyAddress", { required: "Address is required" })} error={Boolean(errors.companyAddress)} helperText={errors.companyAddress?.message} />
					</Grid>
					<Grid size={{ xs: 12, md: 6 }}>
						<TextField fullWidth label="Owner Name" {...register("ownerName", { required: "Owner name is required" })} error={Boolean(errors.ownerName)} helperText={errors.ownerName?.message} />
					</Grid>
					<Grid size={{ xs: 12, md: 6 }}>
						<TextField fullWidth label="Owner Email" type="email" {...register("ownerEmail", { required: "Owner email is required" })} error={Boolean(errors.ownerEmail)} helperText={errors.ownerEmail?.message} />
					</Grid>
					<Grid size={{ xs: 12, md: 6 }}>
						<TextField fullWidth label="Password" type="password" {...register("password", { required: "Password is required", minLength: { value: 8, message: "Password must be at least 8 characters" } })} error={Boolean(errors.password)} helperText={errors.password?.message} />
					</Grid>
					<Grid size={{ xs: 12, md: 6 }}>
						<TextField fullWidth label="Confirm Password" type="password" {...register("confirmPassword", { required: "Confirm your password", validate: (value) => value === passwordValue || "Passwords must match" })} error={Boolean(errors.confirmPassword)} helperText={errors.confirmPassword?.message} />
					</Grid>
				</Grid>
				<Button type="submit" variant="contained" size="large" disabled={isSubmitting}>
					{isSubmitting ? "Creating company..." : "Register Company"}
				</Button>
				<Typography color="text.secondary">
					Already have an account? <RouterLink to="/login">Sign in</RouterLink>
				</Typography>
			</Stack>
		</form>
	);
}
