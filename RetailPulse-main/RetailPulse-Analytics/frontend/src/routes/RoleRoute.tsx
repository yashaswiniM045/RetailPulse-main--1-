import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { UserRole } from "../types/auth";

export default function RoleRoute({ allowedRoles }: { allowedRoles: UserRole[] }) {
	const { user } = useAuth();

	if (!user) {
		return <Navigate to="/login" replace />;
	}

	if (!allowedRoles.includes(user.role)) {
		return <Navigate to="/dashboard" replace />;
	}

	return <Outlet />;
}
