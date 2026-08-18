import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { getProfile, login, logout, registerCompany } from "../api/authApi";
import { AuthResponse, AuthUser, LoginPayload, RegisterPayload } from "../types/auth";
import { clearTokens, loadTokens, saveTokens } from "../utils/storage";

type AuthContextValue = {
	user: AuthUser | null;
	isAuthenticated: boolean;
	isLoading: boolean;
	loginUser: (payload: LoginPayload) => Promise<void>;
	registerUser: (payload: RegisterPayload) => Promise<void>;
	logoutUser: () => Promise<void>;
	refreshProfile: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function applySession(response: AuthResponse, setUser: (user: AuthUser | null) => void) {
	saveTokens({ accessToken: response.accessToken, refreshToken: response.refreshToken });
	setUser(response.user);
}

export function AuthProvider({ children }: { children: ReactNode }) {
	const [user, setUser] = useState<AuthUser | null>(null);
	const [isLoading, setIsLoading] = useState(true);

	useEffect(() => {
		async function bootstrap() {
			const tokens = loadTokens();
			if (!tokens) {
				setIsLoading(false);
				return;
			}

			try {
				const profile = await getProfile();
				setUser(profile);
			} catch {
				clearTokens();
			} finally {
				setIsLoading(false);
			}
		}

		void bootstrap();
	}, []);

	const value = useMemo<AuthContextValue>(
		() => ({
			user,
			isAuthenticated: Boolean(user),
			isLoading,
			loginUser: async (payload) => {
				const response = await login(payload);
				applySession(response, setUser);
			},
			registerUser: async (payload) => {
				const response = await registerCompany(payload);
				applySession(response, setUser);
			},
			logoutUser: async () => {
				const refreshToken = loadTokens()?.refreshToken;
				try {
					if (refreshToken) {
						await logout(refreshToken);
					}
				} finally {
					clearTokens();
					setUser(null);
				}
			},
			refreshProfile: async () => {
				const profile = await getProfile();
				setUser(profile);
			},
		}),
		[isLoading, user],
	);

	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
	const context = useContext(AuthContext);
	if (!context) {
		throw new Error("useAuth must be used within AuthProvider");
	}

	return context;
}
