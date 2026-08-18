import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { AppThemeProvider } from "./context/ThemeContext";
import { NotificationProvider } from "./context/NotificationContext";
import { AuthProvider } from "./context/AuthContext";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
	<React.StrictMode>
		<QueryClientProvider client={queryClient}>
			<AppThemeProvider>
				<NotificationProvider>
					<BrowserRouter>
						<AuthProvider>
							<App />
						</AuthProvider>
					</BrowserRouter>
				</NotificationProvider>
			</AppThemeProvider>
		</QueryClientProvider>
	</React.StrictMode>,
);
