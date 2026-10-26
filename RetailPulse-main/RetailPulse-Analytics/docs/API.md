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
