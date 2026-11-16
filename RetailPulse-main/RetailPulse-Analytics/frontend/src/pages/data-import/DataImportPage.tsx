import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import DownloadIcon from "@mui/icons-material/Download";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import {
	Alert,
	Box,
	Button,
	Chip,
	CircularProgress,
	LinearProgress,
	MenuItem,
	Paper,
	Stack,
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableRow,
	TextField,
	Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { ChangeEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
	cancelImport,
	downloadImportErrorReport,
	downloadImportTemplate,
	getImportById,
	getImportHistory,
	getImportStatus,
	ImportType,
	ImportValidationSummary,
	startImport,
	uploadImportFile,
} from "../../api/importApi";
import { useNotification } from "../../context/NotificationContext";

const importTypeLabels: Record<ImportType, string> = {
	products: "Products",
	inventory: "Inventory",
	customers: "Customers",
	sales: "Sales",
};

const activeStatuses = ["Validating", "Processing"];
const terminalStatuses = ["Completed", "Completed with Errors", "Failed", "Cancelled"];

function messageFromError(error: unknown, fallback: string) {
	if (isAxiosError(error)) {
		const detail = error.response?.data?.detail;
		if (typeof detail === "string") return detail;
	}
	return fallback;
}

function saveBlob(blob: Blob, filename: string) {
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.href = url;
	link.download = filename;
	link.click();
	window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function statusColor(status: string): "default" | "success" | "warning" | "error" {
	if (status === "Completed") return "success";
	if (status === "Completed with Errors" || status === "Processing" || status === "Validating") return "warning";
	if (status === "Failed") return "error";
	return "default";
}

export default function DataImportPage() {
	const { notify } = useNotification();
	const navigate = useNavigate();
	const [importType, setImportType] = useState<ImportType>("products");
	const [validation, setValidation] = useState<ImportValidationSummary | null>(null);
	const [selectedImportId, setSelectedImportId] = useState<number | null>(null);
	const [errorMessage, setErrorMessage] = useState<string | null>(null);
	const [busyAction, setBusyAction] = useState<"upload" | "start" | "cancel" | "template" | "report" | null>(null);

	const historyQuery = useQuery({
		queryKey: ["import-history"],
		queryFn: getImportHistory,
		refetchInterval: 5000,
	});
	const statusQuery = useQuery({
		queryKey: ["import-status", selectedImportId],
		queryFn: () => getImportStatus(selectedImportId as number),
		enabled: selectedImportId !== null,
		refetchInterval: (query) => {
			const status = query.state.data?.status;
			return status && activeStatuses.includes(status) ? 1500 : false;
		},
	});
	const detailQuery = useQuery({
		queryKey: ["import-detail", selectedImportId],
		queryFn: () => getImportById(selectedImportId as number),
		enabled: selectedImportId !== null,
	});
	const detail = detailQuery.data;
	const statusInfo = statusQuery.data ?? detail;
	const busy = busyAction !== null;
	const refreshDetails = detailQuery.refetch;
	const selectedTypeLabel = detail?.importType && detail.importType in importTypeLabels
		? importTypeLabels[detail.importType as ImportType]
		: importTypeLabels[importType];

	useEffect(() => {
		const status = statusQuery.data?.status;
		if (
			status &&
			terminalStatuses.includes(status) &&
			detailQuery.data?.status !== status
		) {
			void refreshDetails();
		}
	}, [detailQuery.data?.status, refreshDetails, statusQuery.data?.status]);

	useEffect(() => {
		if (
			detail &&
			detail.importId === selectedImportId &&
			detail.status === "Uploaded" &&
			detail.validationSummary &&
			!validation
		) {
			setValidation(detail.validationSummary);
		}
	}, [detail, selectedImportId, validation]);

	const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
		const file = event.target.files?.[0];
		event.target.value = "";
		setValidation(null);
		setErrorMessage(null);
		if (!file) return;
		if (!file.name.toLowerCase().endsWith(".csv")) {
			setErrorMessage("Only CSV files are supported.");
			return;
		}
		if (file.size > 5 * 1024 * 1024) {
			setErrorMessage("The file is larger than the 5 MB limit.");
			return;
		}
		setBusyAction("upload");
		try {
			const uploaded = await uploadImportFile(importType, file);
			setValidation(uploaded.summary);
			setSelectedImportId(uploaded.importId);
			await historyQuery.refetch();
			notify("File uploaded and validated. Review the preview before starting the import.", "success");
		} catch (error) {
			setErrorMessage(messageFromError(error, "Unable to upload or validate this CSV file."));
		} finally {
			setBusyAction(null);
		}
	};

	const handleStart = async () => {
		if (!selectedImportId || !validation || validation.validCount === 0 || validation.missingColumns.length > 0) return;
		setBusyAction("start");
		setErrorMessage(null);
		try {
			const approval = await startImport(selectedImportId);
			await historyQuery.refetch();
			notify(
				approval.approvalStatus === "approved"
					? "Import was automatically approved and processing has started."
					: "Import submitted for approval. No business records have been changed.",
				"success",
			);
			navigate(`/workflows?scope=mine&requestId=${approval.approvalRequestId}`);
		} catch (error) {
			setErrorMessage(messageFromError(error, "Unable to start this import."));
		} finally {
			setBusyAction(null);
		}
	};

	const handleCancel = async () => {
		if (!selectedImportId) return;
		setBusyAction("cancel");
		try {
			await cancelImport(selectedImportId);
			await Promise.all([statusQuery.refetch(), detailQuery.refetch(), historyQuery.refetch()]);
			notify("Import cancelled.", "info");
		} catch (error) {
			setErrorMessage(messageFromError(error, "Unable to cancel this import."));
		} finally {
			setBusyAction(null);
		}
	};

	const handleTemplateDownload = async () => {
		setBusyAction("template");
		try {
			saveBlob(await downloadImportTemplate(importType), `${importType}-import-template.csv`);
		} catch (error) {
			setErrorMessage(messageFromError(error, "Unable to download the import template."));
		} finally {
			setBusyAction(null);
		}
	};

	const handleErrorDownload = async (importId: number) => {
		setBusyAction("report");
		try {
			saveBlob(await downloadImportErrorReport(importId), `import-${importId}-errors.csv`);
		} catch (error) {
			setErrorMessage(messageFromError(error, "Unable to download the error report."));
		} finally {
			setBusyAction(null);
		}
	};

	const isActive = Boolean(statusInfo && activeStatuses.includes(statusInfo.status));

	return (
		<Stack spacing={3}>
			<Box>
				<Typography variant="h4" fontWeight={800}>Data Imports</Typography>
				<Typography color="text.secondary">
					Upload and validate CSV data, review records, and track secure company-scoped bulk imports.
				</Typography>
			</Box>

			<Paper sx={{ p: 3 }}>
				<Typography variant="h6" fontWeight={700}>Create an import</Typography>
				<Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }} sx={{ mt: 2 }}>
					<TextField
						select
						label="Import type"
						value={importType}
						onChange={(event) => {
							setImportType(event.target.value as ImportType);
							setValidation(null);
							setSelectedImportId(null);
							setErrorMessage(null);
						}}
						sx={{ minWidth: 220 }}
						disabled={busy}
					>
						{Object.entries(importTypeLabels).map(([value, label]) => (
							<MenuItem key={value} value={value}>{label}</MenuItem>
						))}
					</TextField>
					<Button
						variant="outlined"
						startIcon={<DownloadIcon />}
						onClick={() => void handleTemplateDownload()}
						disabled={busy}
					>
						Download template
					</Button>
					<Button component="label" variant="contained" startIcon={<UploadFileIcon />} disabled={busy}>
						{busyAction === "upload" ? "Uploading..." : "Select CSV file"}
						<input type="file" hidden accept=".csv,text/csv" onChange={(event) => void handleUpload(event)} />
					</Button>
					{busy && <CircularProgress size={22} aria-label="Import action in progress" />}
				</Stack>
				<Alert severity="info" sx={{ mt: 2 }}>
					CSV only; maximum file size 5 MB. Products with an existing SKU, customers with an existing email or phone,
					and sales with an existing invoice are rejected. Inventory rows update the matching product stock.
				</Alert>
				{errorMessage && <Alert severity="error" sx={{ mt: 2 }}>{errorMessage}</Alert>}
				{historyQuery.isError && <Alert severity="error" sx={{ mt: 2 }}>Import history could not be loaded.</Alert>}
			</Paper>

			{validation && (
				<>
					<Paper sx={{ p: 3 }}>
						<Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={2}>
							<Box>
								<Typography variant="h6" fontWeight={700}>Review before import</Typography>
								<Typography color="text.secondary">
									{selectedTypeLabel} CSV uploaded. Nothing is written to business records until you start processing.
								</Typography>
							</Box>
							<Stack direction="row" spacing={1} alignItems="center">
								{selectedImportId && <Chip label={`Import #${selectedImportId}`} variant="outlined" />}
								<Chip label={statusInfo?.status ?? "Uploaded"} color={statusColor(statusInfo?.status ?? "Uploaded")} />
							</Stack>
						</Stack>
						<Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 2 }}>
							<Chip label={`Total: ${validation.totalRecords}`} />
							<Chip color="success" icon={<CheckCircleOutlineIcon />} label={`Valid: ${validation.validCount}`} />
							<Chip color="error" icon={<ErrorOutlineIcon />} label={`Invalid: ${validation.invalidCount}`} />
							<Chip color="warning" label={`Duplicates: ${validation.duplicateCount}`} />
						</Stack>
						{validation.missingColumns.length > 0 && (
							<Alert severity="error" sx={{ mt: 2 }}>
								Missing required columns: {validation.missingColumns.join(", ")}
							</Alert>
						)}
						{validation.issues.length > 0 && (
							<Box sx={{ mt: 2 }}>
								<Typography variant="subtitle2" sx={{ mb: 1 }}>Validation errors</Typography>
								{validation.issues.slice(0, 20).map((issue, index) => (
									<Alert
										key={`${issue.rowNumber}-${issue.message}-${index}`}
										severity={issue.errorType === "duplicate" ? "warning" : "error"}
										sx={{ mb: 1 }}
									>
										Row {issue.rowNumber ?? "-"}: {issue.message}
									</Alert>
								))}
								{validation.issues.length > 20 && (
									<Typography variant="caption" color="text.secondary">
										Showing the first 20 of {validation.issues.length} validation messages.
									</Typography>
								)}
							</Box>
						)}
						<Stack direction="row" spacing={1} sx={{ mt: 2 }}>
							<Button
								variant="contained"
								onClick={() => void handleStart()}
								disabled={busy || !selectedImportId || validation.validCount === 0 || validation.missingColumns.length > 0}
							>
								Start import
							</Button>
							{detail?.status === "Uploaded" && (
								<Button color="inherit" onClick={() => void handleCancel()} disabled={busy}>
									Discard upload
								</Button>
							)}
						</Stack>
					</Paper>

					<Paper sx={{ p: 3 }}>
						<Typography variant="h6" fontWeight={700}>Sample records</Typography>
						<Box sx={{ overflowX: "auto", mt: 1 }}>
							<Table size="small">
								<TableHead>
									<TableRow>{Object.keys(validation.preview[0] ?? {}).map((column) => <TableCell key={column}>{column}</TableCell>)}</TableRow>
								</TableHead>
								<TableBody>
									{validation.preview.length === 0 ? (
										<TableRow><TableCell colSpan={8}>No data rows were found in this CSV.</TableCell></TableRow>
									) : validation.preview.map((row, index) => (
										<TableRow key={index}>
											{Object.keys(validation.preview[0] ?? {}).map((column) => <TableCell key={`${index}-${column}`}>{row[column]}</TableCell>)}
										</TableRow>
									))}
								</TableBody>
							</Table>
						</Box>
					</Paper>
				</>
			)}

			{statusInfo && statusInfo.status !== "Uploaded" && (
				<Paper sx={{ p: 3 }}>
					<Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={2}>
						<Box>
							<Typography variant="h6" fontWeight={700}>Import #{statusInfo.importId} processing status</Typography>
							<Typography color="text.secondary">{statusInfo.filename} · {statusInfo.importType}</Typography>
						</Box>
						<Chip label={statusInfo.status} color={statusColor(statusInfo.status)} />
					</Stack>
					{isActive && (
						<Box sx={{ mt: 2 }}>
							<LinearProgress variant={statusInfo.totalRecords ? "determinate" : "indeterminate"} value={statusInfo.progressPercent} />
							<Typography variant="body2" sx={{ mt: 1 }}>
								{statusInfo.status === "Validating"
									? "Validating records..."
									: `Processed ${statusInfo.processedRecords} of ${statusInfo.totalRecords} records (${statusInfo.progressPercent}%).`}
							</Typography>
							<Button sx={{ mt: 1 }} color="inherit" onClick={() => void handleCancel()} disabled={busy}>
								Cancel import
							</Button>
						</Box>
					)}
					<Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 2 }}>
						<Chip label={`Total: ${statusInfo.totalRecords}`} />
						<Chip color="success" label={`Successful: ${statusInfo.successfulRecords}`} />
						<Chip color="error" label={`Failed: ${statusInfo.failedRecords}`} />
						<Chip color="warning" label={`Duplicates: ${statusInfo.duplicateRecords}`} />
						<Chip label={`Skipped: ${statusInfo.skippedRecords}`} />
						<Chip label={`Duration: ${statusInfo.durationSeconds ?? 0}s`} />
					</Stack>
					{statusQuery.isError && <Alert severity="error" sx={{ mt: 2 }}>Import status could not be refreshed.</Alert>}
					{detailQuery.isError && <Alert severity="error" sx={{ mt: 2 }}>Import status could not be refreshed.</Alert>}
					{statusInfo.status === "Failed" && <Alert severity="error" sx={{ mt: 2 }}>Import failed. Internal system details are not shown.</Alert>}
					{(detail?.errors.length ?? 0) > 0 && (
						<>
							<Typography variant="subtitle1" fontWeight={700} sx={{ mt: 2 }}>Failed records</Typography>
							<Box sx={{ overflowX: "auto" }}>
								<Table size="small">
									<TableHead><TableRow><TableCell>Row</TableCell><TableCell>Error type</TableCell><TableCell>Reason</TableCell><TableCell>Record</TableCell></TableRow></TableHead>
									<TableBody>
										{detail?.errors.slice(0, 50).map((issue, index) => (
											<TableRow key={`${issue.rowNumber}-${index}`}>
												<TableCell>{issue.rowNumber ?? "-"}</TableCell>
												<TableCell>{issue.errorType}</TableCell>
												<TableCell>{issue.message}</TableCell>
												<TableCell>{JSON.stringify(issue.row)}</TableCell>
											</TableRow>
										))}
									</TableBody>
								</Table>
							</Box>
							<Button
								variant="outlined"
								startIcon={<DownloadIcon />}
								onClick={() => void handleErrorDownload(statusInfo.importId)}
								disabled={busy}
								sx={{ mt: 2 }}
							>
								Download error CSV
							</Button>
						</>
					)}
				</Paper>
			)}

			<Paper sx={{ p: 3 }}>
				<Typography variant="h6" fontWeight={700}>Import history</Typography>
				{historyQuery.isLoading ? (
					<Box sx={{ display: "flex", justifyContent: "center", p: 3 }}><CircularProgress size={28} /></Box>
				) : (
					<Box sx={{ overflowX: "auto", mt: 1 }}>
						<Table size="small">
							<TableHead>
								<TableRow>
									<TableCell>ID</TableCell><TableCell>Type</TableCell><TableCell>File</TableCell><TableCell>Uploaded by</TableCell>
									<TableCell>Uploaded</TableCell><TableCell>Total</TableCell><TableCell>Success</TableCell><TableCell>Failed</TableCell><TableCell>Duration</TableCell><TableCell>Status</TableCell>
								</TableRow>
							</TableHead>
							<TableBody>
								{(historyQuery.data ?? []).length === 0 ? (
									<TableRow><TableCell colSpan={10}><Typography color="text.secondary">No imports yet. Select an import type and upload a CSV to begin.</Typography></TableCell></TableRow>
								) : (historyQuery.data ?? []).map((item) => (
									<TableRow
										key={item.id}
										hover
										selected={item.id === selectedImportId}
										onClick={() => {
											setSelectedImportId(item.id);
											setValidation(null);
											setErrorMessage(null);
										}}
										sx={{ cursor: "pointer" }}
									>
										<TableCell>#{item.id}</TableCell>
										<TableCell>{item.importType}</TableCell>
										<TableCell>{item.filename}</TableCell>
										<TableCell>{item.uploadedBy}</TableCell>
										<TableCell>{new Date(item.createdAt).toLocaleString()}</TableCell>
										<TableCell>{item.totalRecords}</TableCell>
										<TableCell>{item.successfulRecords}</TableCell>
										<TableCell>{item.failedRecords}</TableCell>
										<TableCell>{item.durationSeconds == null ? "-" : `${item.durationSeconds}s`}</TableCell>
										<TableCell><Chip size="small" label={item.status} color={statusColor(item.status)} /></TableCell>
									</TableRow>
								))}
							</TableBody>
						</Table>
					</Box>
				)}
				{selectedImportId && detailQuery.isLoading && <Typography sx={{ mt: 1 }} color="text.secondary">Loading import details...</Typography>}
			</Paper>
		</Stack>
	);
}
