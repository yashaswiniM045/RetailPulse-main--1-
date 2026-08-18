import { Chip, Paper, Stack, Typography } from "@mui/material";
import { useAuth } from "../../context/AuthContext";

export default function ProfilePage() {
  const { user } = useAuth();

  if (!user) {
    return null;
  }

  return (
    <Paper sx={{ p: 4, borderRadius: 3 }}>
      <Stack spacing={2}>
        <Typography variant="h4" fontWeight={700}>
          My Profile
        </Typography>
        <Typography><strong>Name:</strong> {user.name}</Typography>
        <Typography><strong>Email:</strong> {user.email}</Typography>
        <Typography><strong>Role:</strong> {user.role}</Typography>
        <Typography><strong>Company:</strong> {user.company.name}</Typography>
        <Typography><strong>Last Login:</strong> {user.lastLogin ?? "First login pending"}</Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography><strong>Status:</strong></Typography>
          <Chip label={user.status} color={user.status === "active" ? "success" : "default"} />
        </Stack>
      </Stack>
    </Paper>
  );
}
