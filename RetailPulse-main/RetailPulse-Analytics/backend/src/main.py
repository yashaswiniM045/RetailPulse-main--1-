from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.config.database import engine
from src.config.env import get_settings
from src.models.base import Base
from src.models import audit_log, category, company, customer, forecast, inventory, product, refresh_token, sale, user
from src.routes.categories import router as categories_router
from src.routes.customers import router as customers_router
from src.routes.dashboard import router as dashboard_router
from src.routes.forecasts import router as forecasts_router
from src.routes.auth import router as auth_router
from src.routes.companies import router as company_router
from src.routes.inventory import router as inventory_router
from src.routes.products import router as products_router
from src.routes.sales import router as sales_router
from src.routes.users import router as user_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE IF EXISTS audit_logs ADD COLUMN IF NOT EXISTS performed_by VARCHAR(255)"))
        connection.execute(text("ALTER TABLE IF EXISTS audit_logs ADD COLUMN IF NOT EXISTS entity_type VARCHAR(50)"))
        connection.execute(text("ALTER TABLE IF EXISTS audit_logs ADD COLUMN IF NOT EXISTS entity_name VARCHAR(255)"))
        connection.execute(text("ALTER TABLE IF EXISTS audit_logs ADD COLUMN IF NOT EXISTS export_type VARCHAR(20)"))
        connection.execute(
            text("ALTER TABLE IF EXISTS products ADD COLUMN IF NOT EXISTS is_out_of_stock BOOLEAN NOT NULL DEFAULT FALSE")
        )
        connection.execute(text("ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS customer_id INTEGER"))
        connection.execute(text("ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) NOT NULL DEFAULT 'paid'"))
        connection.execute(text("ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS discount_total NUMERIC(12,2) NOT NULL DEFAULT 0"))
        connection.execute(text("ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS tax_total NUMERIC(12,2) NOT NULL DEFAULT 0"))
        connection.execute(text("ALTER TABLE IF EXISTS sales ADD COLUMN IF NOT EXISTS notes VARCHAR(1000)"))
        connection.execute(text("ALTER TABLE IF EXISTS demand_forecasts ADD COLUMN IF NOT EXISTS growth_rate NUMERIC(7,4) NOT NULL DEFAULT 0"))
        connection.execute(
            text(
                "ALTER TABLE IF EXISTS demand_forecasts ADD COLUMN IF NOT EXISTS recommendation_type VARCHAR(50) NOT NULL DEFAULT 'stock-level-healthy'"
            )
        )
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api")
app.include_router(company_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(categories_router, prefix="/api")
app.include_router(products_router, prefix="/api")
app.include_router(sales_router, prefix="/api")
app.include_router(inventory_router, prefix="/api")
app.include_router(customers_router, prefix="/api")
app.include_router(forecasts_router, prefix="/api")
app.include_router(user_router, prefix="/api")
