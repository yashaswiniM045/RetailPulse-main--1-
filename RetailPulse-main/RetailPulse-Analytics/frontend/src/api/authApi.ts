import { apiClient } from "./axios";
import { AuthResponse, LoginPayload, RegisterPayload } from "../types/auth";

function normalizeUser(user: Record<string, unknown>) {
	const company = user.company as Record<string, unknown>;
	return {
		id: user.id as number,
		name: user.name as string,
		email: user.email as string,
		role: user.role as AuthResponse["user"]["role"],
		status: user.status as string,
		lastLogin: (user.lastLogin as string | null | undefined) ?? (user.last_login as string | null | undefined) ?? null,
		company: {
			id: company.id as number,
			name: company.name as string,
			industry: company.industry as string,
			email: company.email as string,
		},
	};
}

function normalizeAuthResponse(data: Record<string, unknown>): AuthResponse {
	return {
		accessToken: (data.accessToken as string | undefined) ?? (data.access_token as string),
		refreshToken: (data.refreshToken as string | undefined) ?? (data.refresh_token as string),
		user: normalizeUser(data.user as Record<string, unknown>),
	};
}

export async function registerCompany(payload: RegisterPayload) {
	const response = await apiClient.post<Record<string, unknown>>("/auth/register-company", {
		company_name: payload.companyName,
		industry: payload.industry,
		company_email: payload.companyEmail,
		company_address: payload.companyAddress,
		company_phone_number: payload.companyPhoneNumber,
		owner_name: payload.ownerName,
		owner_email: payload.ownerEmail,
		password: payload.password,
		confirm_password: payload.confirmPassword,
	});
	return normalizeAuthResponse(response.data);
}

export async function login(payload: LoginPayload) {
	const response = await apiClient.post<Record<string, unknown>>("/auth/login", payload);
	return normalizeAuthResponse(response.data);
}

export async function refreshSession(refreshToken: string) {
	const response = await apiClient.post<{ accessToken: string; refreshToken: string }>("/auth/refresh", {
		refreshToken,
	});
	return response.data;
}

export async function logout(refreshToken: string) {
	await apiClient.post("/auth/logout", { refreshToken });
}

export async function getProfile() {
	const response = await apiClient.get<Record<string, unknown>>("/users/me");
	return normalizeUser(response.data);
}
