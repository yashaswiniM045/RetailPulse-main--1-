# API Overview

## Authentication

- `POST /api/auth/register-company`: creates a company, creates the first Company Admin, returns access and refresh tokens.
- `POST /api/auth/login`: authenticates a user and records the login audit event.
- `POST /api/auth/refresh`: rotates the refresh token and returns a new authenticated session.
- `POST /api/auth/logout`: revokes the submitted refresh token and writes a logout audit event.
- `POST /api/auth/change-password`: updates the authenticated user's password and records a password change audit event.

## Protected Resources

- `GET /api/users/me`: returns the authenticated user's profile.
- `GET /api/users`: returns users filtered to the authenticated user's company.
- `GET /api/companies/me`: returns the authenticated user's company only.

## Security Notes

- Private APIs require a JWT access token in the `Authorization: Bearer <token>` header.
- Refresh tokens are persisted in the `refresh_tokens` table and rotated on refresh.
- Company isolation is enforced at the query layer using `company_id` filters.

## Reporting

All report endpoints require an authenticated Company Admin, Super Admin, or Analyst. Schedule creation, updates, status changes, and deletion are restricted to Company Admin and Super Admin roles. Every report, history entry, filter option, and schedule is scoped to the authenticated user's company.

- `GET /api/reports/filters`: lists company-owned products, categories, brands, customers, and users for filter controls.
- `POST /api/reports/generate`: generates one of `sales`, `inventory`, `customers`, `product-performance`, or `stock-movement` reports. The JSON body contains `reportType` and a `filters` object.
- `GET /api/reports/history?page=1&pageSize=25`: lists generated report metadata and applied filters.
- `GET /api/reports/history/{id}?page=1&pageSize=25&sortBy=total&sortDirection=desc`: re-runs the saved filters against current business data and returns a sorted/paginated result page.
- `GET /api/reports/history/{id}/export?format=csv|pdf`: re-runs a successful report and downloads the export, including period and filter context.
- `GET /api/reports/schedules`: lists company schedules and their last/next execution status.
- `POST /api/reports/schedules`: creates a recurring report schedule.
- `PUT /api/reports/schedules/{id}`: updates a schedule.
- `PATCH /api/reports/schedules/{id}/status?isActive=true|false`: enables or disables a schedule.
- `DELETE /api/reports/schedules/{id}`: deletes a schedule.

Supported filter keys are `startDate`, `endDate`, `productId`, `categoryId`, `brand`, `customerId`, `salesStatus`, `stockStatus`, and `userId`. Filters are combined. A start date later than the end date, unknown status, malformed schedule time, or invalid recipient is rejected with HTTP 422. A report-generation failure is retained in history with `status: failed` and an `errorMessage`; failed reports cannot be exported.

Report history stores the report type, company/user ownership, filters, status, format, timestamp, and row count only. Report rows are generated from the existing Sales, Inventory, Customer, Product, and Stock Movement tables on view/export, rather than copied into reporting tables.

Scheduled execution runs in the API process every 30 seconds. Schedule times are UTC; weekly reports run on Monday and monthly reports run on the first day of the month. Configure `REPORT_SMTP_HOST` and `REPORT_SMTP_FROM` to deliver scheduled attachments. Optional settings are `REPORT_SMTP_PORT` (default `587`), `REPORT_SMTP_STARTTLS` (default `true`), `REPORT_SMTP_USERNAME`, and `REPORT_SMTP_PASSWORD`. If delivery is not configured or fails, the schedule and report history retain a failed status and reason. In multi-instance deployments, run only one scheduler-enabled API instance to prevent duplicate delivery.

## Data Quality & Reconciliation

All Data Quality APIs require an authenticated Company Admin, Super Admin, or Analyst. Queries and issue-detail joins are restricted to the authenticated user's `company_id`; a foreign-company issue ID returns 404. Reconciliation and issue status updates are available to those same roles.

- `GET /api/data-quality/overview`: latest run metrics, unresolved issue count, and last run status/time.
- `GET /api/data-quality/issues/options`: issue type, severity, module, and status filter choices for the current company.
- `GET /api/data-quality/issues`: paginated issue search. Supported combined query parameters: `search`, `issueType`, `severity`, `module`, `status`, `startDate`, `endDate`, `page`, `pageSize`, `sortBy`, and `sortDirection`.
- `GET /api/data-quality/issues/{id}`: issue details, safe same-company product/customer/sale context, recent stock movements and sales, plus status event history.
- `PATCH /api/data-quality/issues/{id}/status`: body `{ "status": "Investigating" }`, `{ "status": "Ignored" }`, `{ "status": "Open" }`, or `{ "status": "Resolved", "resolutionNote": "..." }`. Resolving requires a non-empty note. Each change stores actor, timestamp, previous/new status, note, and an Audit Log entry.
- `POST /api/data-quality/reconcile`: runs the configured checks and returns execution metrics plus new/updated issue counts. The running record stores check-by-check progress and errors.
- `GET /api/data-quality/history?page=1&pageSize=25`: company reconciliation execution history, including trigger, timing, counts, status, and check results.

Checks cover sale quantities and matching stock movements, inventory/product quantities and movement chains, sale product/customer references, inactive references, duplicate/required product data, required customer data, and sale totals versus line-item totals. Findings are stored by a company-scoped fingerprint; repeated checks update the existing issue. A finding is auto-resolved only after its check succeeds and no longer detects it. Failed checks do not resolve their previous findings. Existing sales, inventory, products, customers, movements, and report history remain the source data.

Incremental checks run after sale create/update, product create/update/status change, customer create/update/status change/soft delete, manual stock adjustments, and successful product/customer/sales imports. These checks are limited to affected record IDs; they do not launch a full-company scan.

## Data Imports

Import endpoints require an authenticated Company Admin or Super Admin. Every import and its uploaded row data are scoped to the authenticated user's company; uploaded row data is removed when processing completes, fails, or is cancelled. CSV uploads are limited to 5 MB.

- `GET /api/imports/templates/{type}` downloads the CSV template for `products`, `inventory`, `customers`, or `sales`.
- `POST /api/imports/upload` accepts multipart fields `import_type` and `file`. It parses and validates the CSV, creates an `Uploaded` import-history record, and returns the preview, row counts, missing columns, and validation issues. Product SKUs, customer email/phone, and sale invoice references that already exist are rejected. Inventory rows are keyed by SKU and update the matching product's stock.
- `POST /api/imports/validate` accepts `{ "importType": "products", "rows": [...] }` for validating up to 10,000 rows without creating an import.
- `POST /api/imports/{id}/start` creates a pending inventory-import-approval request. The staged rows remain unchanged until approval; after approval a background worker validates and processes records in batches. The response includes `approvalRequestId` and `approvalStatus`.
- `GET /api/imports/{id}/status` returns status, processed/total counts, percent complete, successes, failures, duplicates, skipped rows, and duration.
- `GET /api/imports/{id}` returns the same summary and row-level errors, including original row values.
- `GET /api/imports/{id}/errors` returns failed row details as JSON.
- `GET /api/imports/{id}/errors.csv` downloads the failed rows and validation/processing reasons.
- `GET /api/imports/history` lists imports for the current company.
- `POST /api/imports/{id}/cancel` cancels an uploaded or active import. Cancel any associated pending workflow request first. Already committed rows remain recorded as successful; unprocessed rows are not processed.

Statuses are `Uploaded`, `Validating`, `Processing`, `Completed`, `Completed with Errors`, `Failed`, and `Cancelled`. Import start/completion/failure notifications use import-specific event keys to avoid duplicate event notifications. Upload, start, completion, failure, and cancellation are written to Audit Logs. Successful product, inventory, customer, and sales changes trigger targeted Data Quality checks.

The API process runs one import worker that resumes persisted `Validating`/`Processing` jobs after restart. Deploy one worker-enabled API process per database unless a distributed job-claim mechanism is configured; multiple independent worker processes are not currently supported.
# Workflow & Approval Management

All workflow APIs are under `/api/workflows` and require a bearer access token. Request listing and details are restricted to the authenticated company. Requesters can access their own requests; company admins can access all requests in their company; approvers can access requests assigned to their configured role. The backend checks the same permissions again for every approval action.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/workflows` | Create a request (submitted for approval by default). |
| `POST` | `/api/workflows/{id}/submit` | Submit a draft request. |
| `GET` | `/api/workflows` | Filter and paginate requests with `scope=all\|mine\|queue`, `requestType`, `status`, `search`, `sortDirection`, `page`, and `pageSize`. |
| `GET` | `/api/workflows/{id}` | View request details and timeline. |
| `GET` | `/api/workflows/{id}/history` | Retrieve the append-only approval timeline. |
| `POST` | `/api/workflows/{id}/approve` | Approve and apply a pending change; optional JSON `comment`. |
| `POST` | `/api/workflows/{id}/reject` | Reject a pending change; JSON `comment` is mandatory. |
| `POST` | `/api/workflows/{id}/cancel` | Cancel a draft or pending request (requester or company admin). |
| `GET` | `/api/workflows/pending-count` | Return pending approver and own open-request counts. |
| `GET` | `/api/workflows/config` | List company workflow configuration (company admin only). |
| `PUT` | `/api/workflows/config/{requestType}` | Update an approval role/policy (company admin only). |

Supported `requestType` values are `stock-adjustment`, `product-deactivation`, `product-price-change`, `customer-information-change`, and `inventory-import-approval`. The request body uses `relatedRecordId`, `requestedChanges`, and a required `reason`. Allowed changes are type-specific: `targetQuantity`; `status: "inactive"`; `unitPrice` and/or `costPrice`; customer contact/address fields; or `action: "start-import"`.

The request lifecycle is `draft` → `submitted` → `pending-approval` → `approved`, `rejected`, or `cancelled`; `submitted` is recorded as a timeline event before the persisted status becomes `pending-approval`. Configurations can disable approval, in which case submitted requests are applied and marked approved in one transaction. Approval updates the business record, request state, audit entry, history, and notifications transactionally. Import requests leave staged source data untouched until an approver authorizes the existing import worker. Product price/stock/deactivation updates and customer information updates through their existing APIs are rejected when the corresponding workflow requires approval.

Example:

```json
{
  "requestType": "stock-adjustment",
  "relatedRecordId": 42,
  "requestedChanges": { "targetQuantity": 150 },
  "reason": "Reconciled the physical stock count",
  "priority": "high"
}
```

The import start endpoint `POST /api/imports/{id}/start` now creates an inventory-import-approval request; it does not process any import rows before approval.
