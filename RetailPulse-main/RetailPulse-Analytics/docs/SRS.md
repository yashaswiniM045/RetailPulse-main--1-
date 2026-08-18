# Task 1 SRS Snapshot

## Functional Scope

- Register a new company and its first Company Admin.
- Authenticate existing users with email and password.
- Issue JWT access tokens and persisted refresh tokens.
- Restrict private screens and APIs to authenticated users.
- Enforce company-level isolation for returned data.
- Expose the logged-in user's profile.
- Record audit log entries for registration, login, logout, and password changes.

## Non-Functional Notes

- Passwords are hashed with bcrypt.
- Email uniqueness is enforced for both users and companies.
- Refresh tokens are revocable and expire.
- PostgreSQL is the primary deployment database.
