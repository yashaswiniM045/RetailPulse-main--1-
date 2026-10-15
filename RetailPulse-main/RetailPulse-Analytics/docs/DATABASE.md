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

## Isolation

Each user belongs to exactly one company through `users.company_id`. Company-scoped queries must always include that company identifier.
