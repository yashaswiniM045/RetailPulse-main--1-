import { apiClient } from "./axios";

export async function getMyCompany() {
	const response = await apiClient.get("/companies/me");
	return response.data;
}
