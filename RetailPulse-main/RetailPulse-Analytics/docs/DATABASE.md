# Database Design

## Tables

### companies

- `id`
- `name` unique
- `industry`
- `email` unique
- `address`
- `phone`
- `created_at`

### users

- `id`
- `company_id` foreign key to `companies.id`
- `name`
- `email` unique
- `password` bcrypt hash
- `role`
- `status`
- `last_login`
- `created_at`

### refresh_tokens

- `id`
- `user_id` foreign key to `users.id`
- `token` unique
- `expires_at`
- `created_at`

### audit_logs

- `id`
- `company_id`
- `user_id`
- `action`
- `ip_address`
- `browser`
- `created_at`

### report_history

- `id`
- `company_id` foreign key to `companies.id`
- `generated_by_id` foreign key to `users.id` (nullable for future system-generated runs)
- `generated_by_name`
- `schedule_id` foreign key to `scheduled_reports.id` (nullable)
- `report_type`
- `filters` JSON
- `total_rows`
- `export_format`
- `status`
- `error_message`
- `created_at`

History retains execution metadata and applied filters only. Table rows are regenerated from the source tables when a report is viewed or exported.

### scheduled_reports

- `id`
- `company_id` foreign key to `companies.id`
- `created_by_id` foreign key to `users.id`
- `name`, `report_type`, `filters` JSON
- `frequency`, `execution_time` (UTC)
- `recipients` JSON, `export_format`, `is_active`
- `next_run_at`, `last_run_at`, `last_status`, `last_error`
- `last_history_id` foreign key to `report_history.id` (nullable)
- `created_at`, `updated_at`

### reconciliation_runs

- `id`
- `company_id` foreign key to `companies.id`
- `triggered_by_id` foreign key to `users.id` (nullable for future system runs)
- `triggered_by_name`, `started_at`, `completed_at`
- `records_checked`, `valid_records`, `warning_count`, `error_count`
- `issues_detected`, `issues_resolved`, `failed_checks`
- `status`, `check_results` JSON, `error_message`

### data_quality_issues

- `id`, `company_id` foreign key to `companies.id`
- `fingerprint` unique with `company_id`; `check_key`
- `issue_type`, `severity`, `module`
- `record_type`, `record_id`, `record_name`, `description`, `details` JSON
- `status`, `detected_at`, `last_seen_at`
- `last_seen_run_id` foreign key to `reconciliation_runs.id`
- `resolved_at`, `resolved_by_id`, `resolved_by_name`, `resolution_note`

### data_quality_issue_events

- `id`, `company_id` foreign key to `companies.id`
- `issue_id` foreign key to `data_quality_issues.id`
- `changed_by_id`, `changed_by_name`
- `previous_status`, `new_status`, `note`, `created_at`

### import_history

- `id`, `company_id`, `import_type`, `filename`
- `uploaded_by`, `uploaded_by_id`
- `total_records`, `successful_records`, `failed_records`, `duplicate_records`
- `status`, `created_at`, `completed_at`

### import_jobs

- `import_id` foreign key to `import_history.id`
- `source_data` (temporary JSON-encoded CSV rows, cleared on terminal status)
- `processed_ids` (successful source entity IDs retained for resumable data-quality checks)
- `processed_records`, `skipped_records`
- `started_at`, `duration_seconds`

### import_error_records

- `id`, `import_id` foreign key to `import_history.id`
- `row_number`, `error_type`, `message`, `row_data`

### workflow_configurations

- `id`, `company_id` foreign key to `companies.id`, `request_type`
- `approver_role`, `approval_required`, `allow_self_approval`, `is_active`
- `updated_by_id` foreign key to `users.id`, `created_at`, `updated_at`
- Unique per company and request type. The initial workflow types are stock adjustment, product deactivation, product price change, customer information change, and inventory import approval.

### approval_requests

- `id`, `company_id` foreign key to `companies.id`, `request_type`
- `requested_by_id` foreign key to `users.id`, `approver_role`
- `related_record_type`, `related_record_id`, `current_values` JSON, `requested_changes` JSON
- `reason`, `priority`, `status`, `created_at`, `updated_at`
- Indexed by company/status, company/type, and company/creation time. Company-scoped queries are required for every access.

### approval_history

- `id`, `request_id` foreign key to `approval_requests.id`, `company_id`
- `actor_id` foreign key to `users.id` (nullable for system actions)
- `action`, `comment`, `details` JSON, `created_at`
- Append-only from the workflow API; normal users cannot edit or delete timeline entries.

Import history and error rows are scoped through the owning company's import record. The persisted job payload enables the single in-process background worker to resume after an application restart; completed job payloads are cleared while row-level error data remains available for review and error-report downloads.

The issue tables contain reconciliation metadata and issue context only; they do not copy source business rows. The application initializes schema with SQLAlchemy `create_all`, consistent with the existing repository. Every issue and event is company-scoped and filtered by the authenticated user's company.

The workflow tables are also initialized through SQLAlchemy `create_all`; no separate migration runner is currently used in this application.

## Isolation

Each user belongs to exactly one company through `users.company_id`. Company-scoped queries must always include that company identifier.
