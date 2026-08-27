from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from math import ceil

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from src.models.category import Category
from src.models.inventory import Inventory
from src.models.product import Product, ProductStatus
from src.models.sale import Sale, SaleItem


HISTORICAL_WINDOW_DAYS = 90
FORECAST_HORIZON_DAYS = 30
LEAD_TIME_DAYS = 7
SAFETY_STOCK_DAYS = 7


def _forecast_row(product: Product, inventory: Inventory | None, daily_sales: list[float], today: date) -> dict:
    current_stock = max(int(inventory.available_stock if inventory else product.stock_quantity), 0)
    average_daily_sales = sum(daily_sales) / HISTORICAL_WINDOW_DAYS
    forecasted_demand = average_daily_sales * FORECAST_HORIZON_DAYS
    safety_stock = ceil(average_daily_sales * SAFETY_STOCK_DAYS)
    reorder_point = ceil(average_daily_sales * LEAD_TIME_DAYS) + safety_stock
    days_remaining = round(current_stock / average_daily_sales, 1) if average_daily_sales > 0 else None
    target_stock = ceil(forecasted_demand + safety_stock)
    recommended_quantity = max(target_stock - current_stock, 0)

    if current_stock == 0:
        stock_risk, recommendation = "out-of-stock", "Reorder immediately"
    elif average_daily_sales > 0 and days_remaining <= LEAD_TIME_DAYS:
        stock_risk, recommendation = "stockout-risk", "Reorder immediately"
    elif current_stock <= reorder_point:
        stock_risk, recommendation = "low-stock", "Reorder soon"
    elif average_daily_sales > 0 and (days_remaining >= 90 or current_stock > max(target_stock * 2, reorder_point * 2)):
        stock_risk, recommendation = "overstock", "Review excess inventory"
    else:
        stock_risk, recommendation = "healthy", "No action required"

    start = today - timedelta(days=HISTORICAL_WINDOW_DAYS - 1)
    return {
        "productId": product.id,
        "productName": product.name,
        "sku": product.sku,
        "categoryId": product.category_id,
        "categoryName": product.category.name,
        "supplier": product.brand,
        "currentStock": current_stock,
        "averageDailySales": round(average_daily_sales, 2),
        "forecastedDemand": round(forecasted_demand, 2),
        "daysOfStockRemaining": days_remaining,
        "leadTimeDays": LEAD_TIME_DAYS,
        "safetyStock": safety_stock,
        "reorderPoint": reorder_point,
        "recommendedReorderQuantity": recommended_quantity,
        "stockRisk": stock_risk,
        "recommendation": recommendation,
        "reorderRequired": recommended_quantity > 0,
        "historicalDemand": [
            {"date": start + timedelta(days=index), "demand": round(value, 2)}
            for index, value in enumerate(daily_sales)
        ],
        "forecastStartDate": today + timedelta(days=1),
        "forecastEndDate": today + timedelta(days=FORECAST_HORIZON_DAYS),
    }


def list_inventory_forecasts(
    db: Session,
    company_id: int,
    *,
    product_id: int | None = None,
    category_id: int | None = None,
    supplier: str | None = None,
    search: str | None = None,
    stock_risk: str | None = None,
    reorder_required: bool | None = None,
    sort_by: str = "risk",
    sort_direction: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> dict:
    statement = (
        select(Product, Category, Inventory)
        .join(Category, Category.id == Product.category_id)
        .outerjoin(Inventory, and_(Inventory.product_id == Product.id, Inventory.company_id == company_id))
        .where(Product.company_id == company_id, Product.status == ProductStatus.ACTIVE)
    )
    if product_id:
        statement = statement.where(Product.id == product_id)
    if category_id:
        statement = statement.where(Product.category_id == category_id)
    if supplier:
        statement = statement.where(Product.brand.ilike(f"%{supplier.strip()}%"))
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(or_(Product.name.ilike(term), Product.sku.ilike(term)))

    rows = db.execute(statement).all()
    product_ids = [product.id for product, _, _ in rows]
    today = date.today()
    start = today - timedelta(days=HISTORICAL_WINDOW_DAYS - 1)
    sales_rows = db.execute(
        select(SaleItem.product_id, func.date(Sale.sale_date), func.sum(SaleItem.quantity))
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(
            Sale.company_id == company_id,
            SaleItem.product_id.in_(product_ids) if product_ids else False,
            func.date(Sale.sale_date) >= start,
            func.date(Sale.sale_date) <= today,
        )
        .group_by(SaleItem.product_id, func.date(Sale.sale_date))
    ).all()
    grouped: dict[int, dict[date, float]] = defaultdict(dict)
    for product_key, sale_day, quantity in sales_rows:
        if isinstance(sale_day, str):
            sale_day = date.fromisoformat(sale_day)
        grouped[int(product_key)][sale_day] = float(quantity or 0)

    forecast_rows = []
    for product, _, inventory in rows:
        daily_sales = [grouped[product.id].get(start + timedelta(days=index), 0.0) for index in range(HISTORICAL_WINDOW_DAYS)]
        forecast_rows.append(_forecast_row(product, inventory, daily_sales, today))

    risk_order = {"out-of-stock": 5, "stockout-risk": 4, "low-stock": 3, "overstock": 2, "healthy": 1}
    if stock_risk:
        forecast_rows = [row for row in forecast_rows if row["stockRisk"] == stock_risk]
    if reorder_required is not None:
        forecast_rows = [row for row in forecast_rows if row["reorderRequired"] == reorder_required]
    sort_keys = {
        "currentStock": lambda row: row["currentStock"],
        "forecastedDemand": lambda row: row["forecastedDemand"],
        "daysRemaining": lambda row: row["daysOfStockRemaining"] if row["daysOfStockRemaining"] is not None else float("inf"),
        "recommendedQuantity": lambda row: row["recommendedReorderQuantity"],
        "risk": lambda row: risk_order[row["stockRisk"]],
    }
    forecast_rows.sort(key=sort_keys.get(sort_by, sort_keys["risk"]), reverse=sort_direction == "desc")
    summary = {
        "productsRequiringReorder": sum(row["reorderRequired"] for row in forecast_rows),
        "productsAtStockoutRisk": sum(row["stockRisk"] in {"out-of-stock", "stockout-risk"} for row in forecast_rows),
        "overstockedProducts": sum(row["stockRisk"] == "overstock" for row in forecast_rows),
        "healthyProducts": sum(row["stockRisk"] == "healthy" for row in forecast_rows),
    }
    total = len(forecast_rows)
    offset = (page - 1) * page_size
    return {
        "items": forecast_rows[offset:offset + page_size],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": ceil(total / page_size) if total else 0,
        "summary": summary,
        "generatedAt": today,
        "historicalWindowDays": HISTORICAL_WINDOW_DAYS,
        "forecastHorizonDays": FORECAST_HORIZON_DAYS,
    }


def get_inventory_forecast(db: Session, company_id: int, product_id: int) -> dict:
    result = list_inventory_forecasts(db, company_id, product_id=product_id, page_size=1)
    if not result["items"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return result["items"][0]
