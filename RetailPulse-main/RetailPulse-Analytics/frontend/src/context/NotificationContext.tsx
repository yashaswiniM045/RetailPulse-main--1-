import { Alert, Snackbar } from "@mui/material";
import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from "react";

type Notification = {
	message: string;
	severity: "success" | "error" | "info" | "warning";
};

type NotificationContextValue = {
	notify: (message: string, severity?: Notification["severity"]) => void;
};

const NotificationContext = createContext<NotificationContextValue | undefined>(undefined);

export function NotificationProvider({ children }: { children: ReactNode }) {
	const [notification, setNotification] = useState<Notification | null>(null);

	const notify = useCallback((message: string, severity: Notification["severity"] = "info") => {
		setNotification({ message, severity });
	}, []);

	const value = useMemo(() => ({ notify }), [notify]);

	return (
		<NotificationContext.Provider value={value}>
			{children}
			<Snackbar
				open={Boolean(notification)}
				autoHideDuration={4000}
				onClose={() => setNotification(null)}
				anchorOrigin={{ vertical: "top", horizontal: "right" }}
			>
				<Alert severity={notification?.severity ?? "info"} onClose={() => setNotification(null)}>
					{notification?.message}
				</Alert>
			</Snackbar>
		</NotificationContext.Provider>
	);
}

export function useNotification() {
	const context = useContext(NotificationContext);
	if (!context) {
		throw new Error("useNotification must be used within NotificationProvider");
	}

	return context;
}
