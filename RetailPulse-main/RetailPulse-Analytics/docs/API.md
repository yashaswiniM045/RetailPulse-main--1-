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
