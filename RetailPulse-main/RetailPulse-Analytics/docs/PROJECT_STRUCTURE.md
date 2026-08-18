# Project Structure

- `frontend/`: React + TypeScript client application.
- `backend/`: FastAPI application, SQLAlchemy models, and authentication services.
- `docs/`: API, database, structure, and requirements notes.

## Frontend Highlights

- `src/context`: auth, theme, and notification providers.
- `src/pages/auth`: company registration and login pages.
- `src/routes`: protected routing.
- `src/theme`: Material UI theme definition.

## Backend Highlights

- `src/main.py`: FastAPI app bootstrap.
- `src/config`: environment, database, and JWT configuration.
- `src/models`: SQLAlchemy entities.
- `src/services`: onboarding, login, refresh, logout, password change, and audit services.
- `src/routes`: auth, company, and user API routers.
