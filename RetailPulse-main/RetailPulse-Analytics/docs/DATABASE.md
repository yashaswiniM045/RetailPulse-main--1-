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

## Isolation

Each user belongs to exactly one company through `users.company_id`. Company-scoped queries must always include that company identifier.
