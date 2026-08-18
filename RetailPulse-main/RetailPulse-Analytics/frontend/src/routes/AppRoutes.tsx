import { Navigate, Route, Routes } from "react-router-dom";
import AuthLayout from "../layouts/AuthLayout";
import DashboardLayout from "../layouts/DashboardLayout";
import Login from "../pages/auth/Login";
import Register from "../pages/auth/Register";
import ForgotPassword from "../pages/auth/ForgotPassword";
import DashboardHome from "../pages/dashboard/DashboardHome";
import SalesAnalyticsPage from "../pages/analytics/SalesAnalyticsPage";
import ProfilePage from "../pages/profile/ProfilePage";
import CategoriesPage from "../pages/categories/CategoriesPage";
import ProductsPage from "../pages/products/ProductsPage";
import SalesPage from "../pages/sales/SalesPage";
import InventoryPage from "../pages/inventory/InventoryPage";
import CustomersPage from "../pages/customers/CustomersPage";
import ForecastingPage from "../pages/forecasting/ForecastingPage";
import ProtectedRoute from "./ProtectedRoute";
import RoleRoute from "./RoleRoute";

export default function AppRoutes() {
	return (
		<Routes>
			<Route element={<AuthLayout />}>
				<Route path="/" element={<Navigate to="/login" replace />} />
				<Route path="/login" element={<Login />} />
				<Route path="/register" element={<Register />} />
				<Route path="/forgot-password" element={<ForgotPassword />} />
			</Route>

			<Route element={<ProtectedRoute />}>
				<Route element={<DashboardLayout />}>
					<Route path="/profile" element={<ProfilePage />} />
					<Route element={<RoleRoute allowedRoles={["Company Admin", "Super Admin", "Analyst"]} />}>
						<Route path="/dashboard" element={<DashboardHome />} />
						<Route path="/analytics/sales" element={<SalesAnalyticsPage />} />
					</Route>
					<Route element={<RoleRoute allowedRoles={["Company Admin", "Super Admin", "Analyst"]} />}>
						<Route path="/sales" element={<SalesPage />} />
						<Route path="/inventory" element={<InventoryPage />} />
						<Route path="/customers" element={<CustomersPage />} />
						<Route path="/forecasting" element={<ForecastingPage />} />
					</Route>
					<Route element={<RoleRoute allowedRoles={["Company Admin", "Super Admin"]} />}>
						<Route path="/categories" element={<CategoriesPage />} />
						<Route path="/products" element={<ProductsPage />} />
					</Route>
				</Route>
			</Route>
		</Routes>
	);
}
