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

The issue tables contain reconciliation metadata and issue context only; they do not copy source business rows. The application initializes schema with SQLAlchemy `create_all`, consistent with the existing repository. Every issue and event is company-scoped and filtered by the authenticated user's company.

## Isolation

Each user belongs to exactly one company through `users.company_id`. Company-scoped queries must always include that company identifier.
