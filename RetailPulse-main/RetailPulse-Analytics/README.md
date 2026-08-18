# RetailPulse Analytics

RetailPulse Analytics now includes the Task 1 foundation for multi-company onboarding and authentication:

- React + TypeScript frontend with React Router, Material UI, Axios, TanStack Query, and React Hook Form.
- FastAPI backend with SQLAlchemy, PostgreSQL-ready configuration, JWT access tokens, refresh tokens, bcrypt hashing, and audit logging.
- Company-scoped profile and user APIs so authenticated users only see data tied to their own company.

## Frontend

Key flows:

- Company registration with owner bootstrap
- Email/password login
- Protected dashboard routes
- Profile page showing name, email, role, company, last login, and status

Run locally:

```bash
cd frontend
npm install
npm run dev
```

Create a `.env` from `frontend/.env.example` when you need to override the backend URL.

## Backend

Key APIs:

- `POST /api/auth/register-company`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `POST /api/auth/change-password`
- `GET /api/users/me`
- `GET /api/users`
- `GET /api/companies/me`

Run locally:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn src.main:app --reload
```

## Docker

The project includes `docker-compose.yml` plus Dockerfiles for the frontend and backend.

```bash
docker compose up --build
```

This starts PostgreSQL on port `5432`, FastAPI on `8000`, and the React frontend on `5173`.
