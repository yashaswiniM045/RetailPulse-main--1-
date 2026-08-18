import axios from "axios";
import { clearTokens, loadTokens, saveTokens } from "../utils/storage";

const baseURL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

export const apiClient = axios.create({
	baseURL,
});

let refreshInFlight: Promise<string | null> | null = null;

apiClient.interceptors.request.use((config) => {
	const tokens = loadTokens();
	if (tokens?.accessToken) {
		config.headers.Authorization = `Bearer ${tokens.accessToken}`;
	}
	return config;
});

apiClient.interceptors.response.use(
	(response) => response,
	async (error) => {
		const originalRequest = error.config;
		if (error.response?.status !== 401 || originalRequest._retry) {
			return Promise.reject(error);
		}

		if (!refreshInFlight) {
			refreshInFlight = apiClient
				.post("/auth/refresh", {
					refreshToken: loadTokens()?.refreshToken,
				})
				.then((response) => {
					const currentTokens = loadTokens();
					if (!currentTokens) {
						return null;
					}
					const nextTokens = {
						accessToken: response.data.accessToken,
						refreshToken: response.data.refreshToken,
					};
					saveTokens(nextTokens);
					return nextTokens.accessToken;
				})
				.catch(() => {
					clearTokens();
					return null;
				})
				.finally(() => {
					refreshInFlight = null;
				});
		}

		const nextAccessToken = await refreshInFlight;
		if (!nextAccessToken) {
			return Promise.reject(error);
		}

		originalRequest._retry = true;
		originalRequest.headers.Authorization = `Bearer ${nextAccessToken}`;
		return apiClient(originalRequest);
	},
);
