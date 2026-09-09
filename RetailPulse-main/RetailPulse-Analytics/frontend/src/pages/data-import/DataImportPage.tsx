import UploadFileIcon from "@mui/icons-material/UploadFile";
import DownloadIcon from "@mui/icons-material/Download";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import { Alert, Box, Button, Chip, CircularProgress, Divider, MenuItem, Paper, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { useNotification } from "../../context/NotificationContext";
import { getImportHistory, ImportType, ImportValidationSummary, processImportRows, uploadImportFile, validateImportRows } from "../../api/importApi";
import { useQuery } from "@tanstack/react-query";

const importTypeLabels: Record<ImportType, string> = {
	products: "Products",
	customers: "Customers",
	sales: "Sales Transactions",
};

const requiredColumns: Record<ImportType, string[]> = {
	products: ["Product Name", "SKU", "Category", "Unit Price", "Stock Quantity"],
	customers: ["Name", "Email", "Phone"],
	sales: ["Customer", "Product", "Quantity", "Unit Price", "Sale Date"],
};

function parseCsvText(text: string) {
	const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
	if (lines.length === 0) {
		return { headers: [], rows: [] as Record<string, string>[] };
	}
	const headers = lines[0].split(",").map((value) => value.trim());
	const rows = lines.slice(1).map((line) => {
		const values = line.split(",").map((value) => value.trim());
		const record: Record<string, string> = {};
		headers.forEach((header, index) => {
			record[header] = values[index] ?? "";
		});
		return record;
	});
	return { headers, rows };
}

export default function DataImportPage() {
	const { notify } = useNotification();
	const [importType, setImportType] = useState<ImportType>("products");
	const [selectedFile, setSelectedFile] = useState<File | null>(null);
	const [rows, setRows] = useState<Record<string, string>[]>([]);
	const [columns, setColumns] = useState<string[]>([]);
	const [validation, setValidation] = useState<ImportValidationSummary | null>(null);
	const [processing, setProcessing] = useState(false);
	const [processingState, setProcessingState] = useState<"idle" | "uploading" | "validating" | "processing" | "completed">("idle");
	const [result, setResult] = useState<{ importId: number; totalRecords: number; successfullyAdded: number; failedRecords: number; duplicateRecords: number; validationFailures: number; status: string; errors: any[] } | null>(null);
	const [errorMessage, setErrorMessage] = useState<string | null>(null);

	const { data: history = [], refetch: refetchHistory } = useQuery({
		queryKey: ["import-history"],
		queryFn: getImportHistory,
	});

	useEffect(() => {
		if (selectedFile && selectedFile.name.toLowerCase().endsWith(".csv")) {
			void selectedFile.text().then((text) => {
				const parsed = parseCsvText(text);
				setColumns(parsed.headers);
				setRows(parsed.rows);
			});
		}
	}, [selectedFile]);

	const requiredSet = useMemo(() => new Set(requiredColumns[importType]), [importType]);
	const missingColumns = useMemo(() => Array.from(requiredSet).filter((column) => !columns.some((value) => value.trim().toLowerCase() === column.trim().toLowerCase())), [columns, requiredSet]);

	const validateCurrentFile = async () => {
		if (!selectedFile) {
			setErrorMessage("Please choose a CSV file first.");
			return;
		}
		if (!selectedFile.name.toLowerCase().endsWith(".csv")) {
			setErrorMessage("Only .csv files are accepted.");
			return;
		}
		if (selectedFile.size > 5 * 1024 * 1024) {
			setErrorMessage("The file is too large. Keep it under 5MB.");
			return;
		}
		if (missingColumns.length > 0) {
			setErrorMessage(`Missing required columns: ${missingColumns.join(", ")}`);
			setValidation(null);
			return;
		}
		setProcessingState("validating");
		setErrorMessage(null);
		try {
			const summary = await validateImportRows(importType, rows);
			setValidation(summary);
			if (summary.invalidCount > 0 || summary.duplicateCount > 0) {
				notify("Validation found rows to review before import.", "warning");
			} else {
				notify("CSV validated successfully.", "success");
			}
		} catch (error: any) {
			setErrorMessage(error?.response?.data?.detail ?? "Unable to validate the CSV file.");
		} finally {
			setProcessingState("idle");
		}
	};

	const importData = async () => {
		if (!selectedFile) {
			setErrorMessage("Please choose a valid file before starting the import.");
			return;
		}
		if (!validation) {
			await validateCurrentFile();
		}
		if (!validation || validation.validCount === 0) {
			setErrorMessage("No valid rows are available to import.");
			return;
		}
		setProcessing(true);
		setProcessingState("processing");
		try {
			const response = await processImportRows(importType, validation.validCount > 0 ? rows.filter((_, index) => !validation.issues.some((issue) => issue.rowNumber === index + 2)) : rows, selectedFile.name);
			setResult(response);
			setProcessingState("completed");
			notify("Import completed successfully.", "success");
			await refetchHistory();
		} catch (error: any) {
			setErrorMessage(error?.response?.data?.detail ?? "Import failed.");
			notify("Import failed. No partial records were committed.", "error");
			setProcessingState("idle");
		} finally {
			setProcessing(false);
		}
	};

	const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
		const file = event.target.files?.[0] ?? null;
		if (!file) {
			setSelectedFile(null);
			setRows([]);
			setColumns([]);
			setValidation(null);
			setResult(null);
			return;
		}
		if (!file.name.toLowerCase().endsWith(".csv")) {
			setErrorMessage("Unsupported file type. Please pick a .csv file.");
			setSelectedFile(null);
			return;
		}
		setSelectedFile(file);
		setErrorMessage(null);
		setValidation(null);
		setResult(null);
	};

	const handleRemoveFile = () => {
		setSelectedFile(null);
		setColumns([]);
		setRows([]);
		setValidation(null);
		setResult(null);
		setErrorMessage(null);
	};

	const downloadFailedRows = () => {
		if (!result || result.errors.length === 0) {
			return;
		}
		const csv = ["rowNumber,errorType,message"].concat(
			result.errors.map((issue) => `${issue.rowNumber ?? ""},${issue.errorType},${String(issue.message).replace(/,/g, " ")}`),
		).join("\n");
		const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
		const url = URL.createObjectURL(blob);
		const link = document.createElement("a");
		link.href = url;
		link.download = `import-errors-${result.importId}.csv`;
		link.click();
		URL.revokeObjectURL(url);
	};

	return (
		<Stack spacing={3}>
			<Box>
				<Typography variant="h4" fontWeight={800}>Data Import</Typography>
				<Typography color="text.secondary">Import products, customers, and sales records using CSV files while keeping tenant boundaries enforced.</Typography>
			</Box>

			<Paper sx={{ p: 3 }}>
				<Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
					<TextField select label="Import Type" value={importType} onChange={(event) => setImportType(event.target.value as ImportType)} sx={{ minWidth: 220 }}>
						{Object.entries(importTypeLabels).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}
					</TextField>
					<Button component="label" variant="contained" startIcon={<UploadFileIcon />} disabled={processing}>
						Select CSV file
						<input type="file" hidden accept=".csv" onChange={handleFileChange} />
					</Button>
					{selectedFile && <Chip label={selectedFile.name} onDelete={handleRemoveFile} color="primary" variant="outlined" />}
				</Stack>
				{errorMessage && <Alert severity="error" sx={{ mt: 2 }}>{errorMessage}</Alert>}
				{processingState !== "idle" && (
					<Box sx={{ mt: 2, display: "flex", alignItems: "center", gap: 1 }}>
						<CircularProgress size={18} />
						<Typography variant="body2">{processingState === "uploading" ? "Uploading" : processingState === "validating" ? "Validating" : "Processing"}...</Typography>
					</Box>
				)}
				<Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ mt: 2 }}>
					<Button variant="outlined" onClick={() => void validateCurrentFile()} disabled={!selectedFile || processing}>Validate File</Button>
					<Button variant="contained" onClick={() => void importData()} disabled={!selectedFile || processing || !validation || validation.validCount === 0}>Import Data</Button>
				</Stack>
			</Paper>

			{columns.length > 0 && (
				<Paper sx={{ p: 3 }}>
					<Typography variant="h6" fontWeight={700}>CSV Preview</Typography>
					<Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Detected columns: {columns.join(", ")}</Typography>
					<Table size="small">
						<TableHead>
							<TableRow>
								{columns.map((column) => <TableCell key={column}>{column}</TableCell>)}
							</TableRow>
						</TableHead>
						<TableBody>
							{rows.slice(0, 6).map((row, index) => (
								<TableRow key={`${index}-${row[columns[0] ?? ""]}`}>
									{columns.map((column) => <TableCell key={`${column}-${index}`}>{row[column] ?? ""}</TableCell>)}
								</TableRow>
							))}
						</TableBody>
					</Table>
					<Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>Total records: {rows.length}</Typography>
				</Paper>
			)}

			{validation && (
				<Paper sx={{ p: 3 }}>
					<Typography variant="h6" fontWeight={700}>Validation Summary</Typography>
					<Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mt: 2 }}>
						<Chip label={`Total Records: ${validation.totalRecords}`} />
						<Chip color="success" label={`Valid Records: ${validation.validCount}`} />
						<Chip color="error" label={`Invalid Records: ${validation.invalidCount}`} />
						<Chip color="warning" label={`Duplicate Records: ${validation.duplicateCount}`} />
					</Stack>
					{validation.missingColumns.length > 0 && <Alert severity="error" sx={{ mt: 2 }}>Missing required columns: {validation.missingColumns.join(", ")}</Alert>}
					{validation.issues.length > 0 && (
						<Box sx={{ mt: 2 }}>
							<Typography variant="subtitle2" sx={{ mb: 1 }}>Issues</Typography>
							{validation.issues.slice(0, 10).map((issue, index) => (
								<Alert key={`${issue.message}-${index}`} severity={issue.errorType === "duplicate" ? "warning" : "error"} sx={{ mb: 1 }}>
									Row {issue.rowNumber ?? "-"}: {issue.message}
								</Alert>
							))}
						</Box>
					)}
				</Paper>
			)}

			{result && (
				<Paper sx={{ p: 3 }}>
					<Typography variant="h6" fontWeight={700}>Import Result</Typography>
					<Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mt: 2 }}>
						<Chip label={`Total: ${result.totalRecords}`} />
						<Chip color="success" label={`Successfully Added: ${result.successfullyAdded}`} />
						<Chip color="warning" label={`Duplicates: ${result.duplicateRecords}`} />
						<Chip color="error" label={`Failed: ${result.failedRecords}`} />
					</Stack>
					{result.errors.length > 0 && (
						<Button variant="outlined" startIcon={<DownloadIcon />} onClick={downloadFailedRows} sx={{ mt: 2 }}>
							Download failed records
						</Button>
					)}
				</Paper>
			)}

			<Paper sx={{ p: 3 }}>
				<Typography variant="h6" fontWeight={700}>Import History</Typography>
				<Table size="small">
					<TableHead>
						<TableRow>
							<TableCell>Import ID</TableCell>
							<TableCell>Type</TableCell>
							<TableCell>Filename</TableCell>
							<TableCell>Uploaded By</TableCell>
							<TableCell>Upload Date</TableCell>
							<TableCell>Total</TableCell>
							<TableCell>Successful</TableCell>
							<TableCell>Failed</TableCell>
							<TableCell>Status</TableCell>
						</TableRow>
					</TableHead>
					<TableBody>
						{history.length === 0 ? (
							<TableRow><TableCell colSpan={9}><Typography color="text.secondary">No import history yet.</Typography></TableCell></TableRow>
						) : history.map((item) => (
							<TableRow key={item.id}>
								<TableCell>{item.id}</TableCell>
								<TableCell>{item.importType}</TableCell>
								<TableCell>{item.filename}</TableCell>
								<TableCell>{item.uploadedBy}</TableCell>
								<TableCell>{new Date(item.createdAt).toLocaleString()}</TableCell>
								<TableCell>{item.totalRecords}</TableCell>
								<TableCell>{item.successfulRecords}</TableCell>
								<TableCell>{item.failedRecords}</TableCell>
								<TableCell><Chip label={item.status} color={item.status.includes("Completed") ? "success" : item.status === "Failed" ? "error" : item.status === "Processing" ? "warning" : "default"} /></TableCell>
							</TableRow>
						))}
					</TableBody>
				</Table>
			</Paper>
		</Stack>
	);
}
