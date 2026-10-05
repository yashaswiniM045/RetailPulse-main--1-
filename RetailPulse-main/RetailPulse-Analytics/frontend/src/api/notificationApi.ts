import { apiClient } from "./axios";

export type NotificationPriority = "low" | "medium" | "high" | "critical";
export type NotificationReadFilter = "all" | "read" | "unread";

export interface NotificationItem {
	id: number;
	type: string;
	title: string;
	message: string;
	priority: NotificationPriority;
	resourceType: string | null;
	resourceId: string | null;
	details: Record<string, unknown> | null;
	isRead: boolean;
	createdAt: string;
	readAt: string | null;
	resolvedAt: string | null;
}

export interface NotificationPage {
	items: NotificationItem[];
	total: number;
	page: number;
	pageSize: number;
	totalPages: number;
}

export async function listNotifications(filters: { page?: number; pageSize?: number; read?: NotificationReadFilter; type?: string; priority?: NotificationPriority }) {
	const response = await apiClient.get<NotificationPage>("/notifications", {
		params: {
			page: filters.page,
			page_size: filters.pageSize,
			read: filters.read === "all" ? undefined : filters.read,
			type: filters.type || undefined,
			priority: filters.priority,
		},
	});
	return response.data;
}

export async function getUnreadNotificationCount() {
	const response = await apiClient.get<{ unreadCount: number }>("/notifications/unread-count");
	return response.data.unreadCount;
}

export async function markNotificationRead(id: number) {
	const response = await apiClient.patch<NotificationItem>(`/notifications/${id}/read`);
	return response.data;
}

export async function markAllNotificationsRead() {
	const response = await apiClient.patch<{ updatedCount: number; unreadCount: number }>("/notifications/read-all");
	return response.data;
}
