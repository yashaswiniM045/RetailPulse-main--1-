import csv
import io
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from statistics import mean

from fastapi import HTTPException, Request, status
from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.orm import Session

from src.models.category import Category
from src.models.forecast import (
    DemandForecast,
    ForecastHistory,
    ForecastNotification,
    ForecastNotificationType,
    ForecastPeriod,
    InventoryRecommendationType,
)
from src.models.inventory import Inventory
from src.models.product import Product, ProductStatus
from src.models.sale import Sale, SaleItem
from src.models.user import User
from src.schemas.forecast import ForecastSortBy, ForecastSortDirection
from src.services.audit_service import AuditAction, create_audit_log


def _to_float(value: object) -> float:
    return float(value or 0)


def _to_int(value: object) -> int:
    return int(value or 0)


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_simple_pdf(lines: list[str]) -> bytes:
    content_lines = []
    y = 800
    for line in lines:
        content_lines.append(f"BT /F1 10 Tf 50 {y} Td ({_escape_pdf_text(line)}) Tj ET")
        y -= 14
    content_stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objects.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
    )
    objects.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    objects.append(
        f"5 0 obj << /Length {len(content_stream)} >> stream\n".encode("latin-1")
        + content_stream
        + b"\nendstream endobj\n"
    )

    payload = io.BytesIO()
    payload.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(payload.tell())
        payload.write(obj)
    xref_start = payload.tell()
    payload.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    payload.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
    payload.write(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_start}\n"
            "%%EOF"
        ).encode("latin-1")
    )
    return payload.getvalue()


def _resolve_period_window(
    forecast_period: ForecastPeriod,
    custom_start_date: date | None,
    custom_end_date: date | None,
) -> tuple[date, date, int]:
    start = datetime.now(UTC).date() + timedelta(days=1)
    if forecast_period == ForecastPeriod.NEXT_7_DAYS:
        end = start + timedelta(days=6)
    elif forecast_period == ForecastPeriod.NEXT_30_DAYS:
        end = start + timedelta(days=29)
    elif forecast_period == ForecastPeriod.NEXT_90_DAYS:
        end = start + timedelta(days=89)
    else:
        if custom_start_date is None or custom_end_date is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Custom period requires start and end date")
        start = custom_start_date
        end = custom_end_date
    if end < start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Forecast end date cannot be before start date")
    return start, end, (end - start).days + 1


def _moving_average_projection(daily_values: list[float], horizon_days: int) -> tuple[float, float, float]:
    if not daily_values:
        return 0.0, 0.0, 0.0

    lookback = daily_values[-30:] if len(daily_values) > 30 else daily_values
    daily_avg = mean(lookback)

    short_avg = mean(daily_values[-7:]) if len(daily_values) >= 7 else mean(daily_values)
    long_avg = mean(daily_values[-30:]) if len(daily_values) >= 30 else mean(daily_values)
    trend_multiplier = 1.0
    if long_avg > 0:
        trend_multiplier = max(0.6, min(1.6, short_avg / long_avg))

    predicted = daily_avg * horizon_days * trend_multiplier

    if len(lookback) <= 1:
        confidence = 55.0
    else:
        variability = mean([abs(v - daily_avg) for v in lookback])
        normalized_error = (variability / daily_avg) if daily_avg > 0 else 1
        confidence = max(40.0, min(95.0, 92.0 - normalized_error * 55.0))

    growth = ((short_avg - long_avg) / long_avg * 100.0) if long_avg > 0 else 0.0
    return round(predicted, 2), round(confidence, 2), round(growth, 2)


def _compute_recommendation(current_stock: int, reorder_level: int, predicted_demand: float) -> tuple[InventoryRecommendationType, str]:
    demand = max(predicted_demand, 0)
    if current_stock <= 0 or demand >= max(current_stock, 1) * 1.2:
        return (
            InventoryRecommendationType.IMMEDIATE_RESTOCK_REQUIRED,
            "Predicted demand materially exceeds available stock and immediate replenishment is required",
        )
    if current_stock <= reorder_level or demand >= current_stock * 0.9:
        return (
            InventoryRecommendationType.REORDER_SOON,
            "Projected demand is close to available stock or below reorder safety threshold",
        )
    if demand <= max(current_stock * 0.35, 1):
        return (
            InventoryRecommendationType.OVERSTOCK_RISK,
            "Projected demand is significantly lower than current stock, creating overstock risk",
        )
    return (
        InventoryRecommendationType.STOCK_LEVEL_HEALTHY,
        "Current stock levels are aligned with projected demand",
    )


def _existing_period_snapshot(
    db: Session,
    company_id: int,
    forecast_period: ForecastPeriod,
    forecast_start_date: date,
    forecast_end_date: date,
) -> datetime | None:
    return db.scalar(
        select(func.max(DemandForecast.generated_at)).where(
            DemandForecast.company_id == company_id,
            DemandForecast.forecast_period == forecast_period,
            DemandForecast.forecast_start_date == forecast_start_date,
            DemandForecast.forecast_end_date == forecast_end_date,
        )
    )


def _load_products_for_forecast(db: Session, company_id: int, product_id: int | None, category_id: int | None, brand: str | None):
    statement = (
        select(Product, Category, Inventory)
        .join(Category, Category.id == Product.category_id)
        .join(Inventory, and_(Inventory.product_id == Product.id, Inventory.company_id == company_id))
        .where(
            Product.company_id == company_id,
            Product.status == ProductStatus.ACTIVE,
        )
    )
    if product_id:
        statement = statement.where(Product.id == product_id)
    if category_id:
        statement = statement.where(Product.category_id == category_id)
    if brand:
        statement = statement.where(func.lower(Product.brand) == brand.strip().lower())
    return db.execute(statement).all()


def _aggregate_daily_sales(db: Session, company_id: int, product_ids: list[int], start_date: date, end_date: date) -> dict[int, list[float]]:
    if not product_ids:
        return {}

    rows = db.execute(
        select(
            SaleItem.product_id,
            func.date(Sale.sale_date).label("sale_day"),
            func.coalesce(func.sum(SaleItem.quantity), 0).label("qty"),
        )
        .select_from(Sale)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .where(
            Sale.company_id == company_id,
            SaleItem.product_id.in_(product_ids),
            func.date(Sale.sale_date) >= start_date,
            func.date(Sale.sale_date) <= end_date,
        )
        .group_by(SaleItem.product_id, func.date(Sale.sale_date))
        .order_by(func.date(Sale.sale_date).asc())
    ).all()

    grouped: dict[int, dict[date, float]] = defaultdict(dict)
    for pid, sale_day, qty in rows:
        grouped[int(pid)][sale_day] = _to_float(qty)

    by_product: dict[int, list[float]] = {}
    for pid in product_ids:
        day = start_date
        values: list[float] = []
        while day <= end_date:
            values.append(grouped.get(pid, {}).get(day, 0.0))
            day += timedelta(days=1)
        by_product[pid] = values
    return by_product


def _average_accuracy(db: Session, company_id: int) -> float:
    accuracy = db.scalar(
        select(func.avg(ForecastHistory.accuracy))
        .select_from(ForecastHistory)
        .join(DemandForecast, DemandForecast.id == ForecastHistory.forecast_id)
        .where(DemandForecast.company_id == company_id, ForecastHistory.accuracy.is_not(None))
    )
    return round(_to_float(accuracy), 2)


def _build_dashboard_payload(db: Session, company_id: int, forecasts: list[DemandForecast]) -> dict:
    if not forecasts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No forecasts available for selected period")

    forecast_ids = [item.id for item in forecasts]
    history_rows = db.execute(
        select(ForecastHistory.forecast_id, ForecastHistory.historical_sales, ForecastHistory.prediction, ForecastHistory.accuracy)
        .where(ForecastHistory.forecast_id.in_(forecast_ids))
    ).all()
    history_map = {int(forecast_id): (_to_float(hist), _to_float(pred), _to_float(acc) if acc is not None else None) for forecast_id, hist, pred, acc in history_rows}

    products: list[dict] = []
    category_rollup: dict[int, dict] = defaultdict(lambda: {"historical": 0.0, "predicted": 0.0, "name": ""})
    recommendations: list[dict] = []

    for forecast in forecasts:
        historical_sales, prediction_value, accuracy = history_map.get(forecast.id, (0.0, _to_float(forecast.predicted_demand), None))
        product = forecast.product
        category = forecast.category
        inventory = db.scalar(
            select(Inventory).where(Inventory.company_id == company_id, Inventory.product_id == forecast.product_id)
        )
        current_stock = _to_int(inventory.current_stock if inventory else 0)
        reorder_level = _to_int(inventory.reorder_level if inventory else 0)

        growth_percentage = _to_float(forecast.growth_rate) * 100.0 if abs(_to_float(forecast.growth_rate)) <= 1 else _to_float(forecast.growth_rate)
        products.append(
            {
                "forecastId": forecast.id,
                "productId": forecast.product_id,
                "productName": product.name,
                "categoryId": forecast.category_id,
                "categoryName": category.name,
                "brand": product.brand,
                "currentStock": current_stock,
                "historicalSales": historical_sales,
                "predictedDemand": prediction_value,
                "forecastPeriod": forecast.forecast_period.value,
                "forecastStartDate": forecast.forecast_start_date,
                "forecastEndDate": forecast.forecast_end_date,
                "confidenceLevel": _to_float(forecast.confidence_score),
                "accuracy": accuracy,
                "growthPercentage": round(growth_percentage, 2),
                "recommendationType": forecast.recommendation_type.value,
            }
        )

        recommendation_type, recommendation_reason = _compute_recommendation(
            current_stock,
            reorder_level,
            prediction_value,
        )
        recommendations.append(
            {
                "forecastId": forecast.id,
                "productId": forecast.product_id,
                "productName": product.name,
                "recommendationType": recommendation_type.value,
                "reason": recommendation_reason,
                "currentStock": current_stock,
                "reorderLevel": reorder_level,
                "predictedDemand": prediction_value,
            }
        )

        roll = category_rollup[forecast.category_id]
        roll["name"] = category.name
        roll["historical"] += historical_sales
        roll["predicted"] += prediction_value

    categories: list[dict] = []
    for cid, payload in category_rollup.items():
        expected_growth = ((payload["predicted"] - payload["historical"]) / payload["historical"] * 100.0) if payload["historical"] > 0 else 0.0
        categories.append(
            {
                "categoryId": cid,
                "categoryName": payload["name"],
                "totalHistoricalSales": round(payload["historical"], 2),
                "predictedDemand": round(payload["predicted"], 2),
                "expectedGrowthPercentage": round(expected_growth, 2),
            }
        )

    total_predicted_demand = sum(item["predictedDemand"] for item in products)
    products_expected_to_run_out = sum(1 for item in products if item["predictedDemand"] >= item["currentStock"])
    high_growth_products = sum(1 for item in products if item["growthPercentage"] >= 20)
    slow_moving_products = sum(1 for item in products if item["predictedDemand"] <= max(item["currentStock"] * 0.35, 2))

    forecast_accuracy = _average_accuracy(db, company_id)

    historical_vs_forecast = [
        {
            "label": item["productName"],
            "historical": item["historicalSales"],
            "forecast": item["predictedDemand"],
        }
        for item in sorted(products, key=lambda entry: entry["predictedDemand"], reverse=True)[:15]
    ]

    product_demand_trend = [
        {
            "label": item["productName"],
            "predictedDemand": item["predictedDemand"],
            "historicalSales": item["historicalSales"],
            "growthPercentage": item["growthPercentage"],
        }
        for item in sorted(products, key=lambda entry: entry["predictedDemand"], reverse=True)[:20]
    ]

    category_demand_trend = [
        {
            "label": item["categoryName"],
            "predictedDemand": item["predictedDemand"],
            "historicalSales": item["totalHistoricalSales"],
        }
        for item in sorted(categories, key=lambda entry: entry["predictedDemand"], reverse=True)
    ]

    top_predicted_products = [
        {
            "productId": item["productId"],
            "productName": item["productName"],
            "predictedDemand": item["predictedDemand"],
            "confidenceLevel": item["confidenceLevel"],
        }
        for item in sorted(products, key=lambda entry: entry["predictedDemand"], reverse=True)[:10]
    ]

    seasonal_sales_pattern = []
    season_bucket: dict[str, float] = defaultdict(float)
    for item in products:
        start = item["forecastStartDate"]
        month_key = f"{start.year}-{start.month:02d}"
        season_bucket[month_key] += item["predictedDemand"]
    for month_key in sorted(season_bucket.keys()):
        seasonal_sales_pattern.append({"period": month_key, "value": round(season_bucket[month_key], 2)})

    return {
        "generatedAt": max(item.generated_at for item in forecasts),
        "forecastPeriod": forecasts[0].forecast_period.value,
        "forecastStartDate": forecasts[0].forecast_start_date,
        "forecastEndDate": forecasts[0].forecast_end_date,
        "products": products,
        "categories": categories,
        "analytics": {
            "kpis": {
                "totalPredictedDemand": round(total_predicted_demand, 2),
                "productsExpectedToRunOut": products_expected_to_run_out,
                "highGrowthProducts": high_growth_products,
                "slowMovingProducts": slow_moving_products,
                "forecastAccuracy": forecast_accuracy,
            },
            "historicalVsForecast": historical_vs_forecast,
            "productDemandTrend": product_demand_trend,
            "categoryDemandTrend": category_demand_trend,
            "topPredictedProducts": top_predicted_products,
            "seasonalSalesPattern": seasonal_sales_pattern,
        },
        "recommendations": recommendations,
    }


def _create_notifications_for_forecasts(db: Session, company_id: int, forecasts: list[DemandForecast], actor: User | None) -> None:
    for forecast in forecasts:
        product = forecast.product
        inventory = db.scalar(
            select(Inventory).where(Inventory.company_id == company_id, Inventory.product_id == forecast.product_id)
        )
        current_stock = _to_int(inventory.current_stock if inventory else 0)
        predicted = _to_float(forecast.predicted_demand)
        growth_rate = _to_float(forecast.growth_rate)

        messages: list[tuple[ForecastNotificationType, str]] = []
        if current_stock <= 0 or predicted >= current_stock:
            messages.append(
                (
                    ForecastNotificationType.RUN_OUT_RISK,
                    f"Product {product.name} is predicted to run out of stock in the selected forecast period",
                )
            )
        if predicted > current_stock:
            messages.append(
                (
                    ForecastNotificationType.DEMAND_EXCEEDS_STOCK,
                    f"Forecasted demand for {product.name} exceeds available inventory",
                )
            )
        if growth_rate >= 0.2:
            messages.append(
                (
                    ForecastNotificationType.SIGNIFICANT_GROWTH,
                    f"Product {product.name} shows significant growth in predicted demand",
                )
            )

        for notification_type, message in messages:
            existing = db.scalar(
                select(ForecastNotification.id)
                .where(
                    ForecastNotification.company_id == company_id,
                    ForecastNotification.forecast_id == forecast.id,
                    ForecastNotification.notification_type == notification_type,
                )
                .limit(1)
            )
            if existing is None:
                db.add(
                    ForecastNotification(
                        company_id=company_id,
                        forecast_id=forecast.id,
                        product_id=forecast.product_id,
                        notification_type=notification_type,
                        message=message,
                        created_by=actor.id if actor else None,
                    )
                )


def generate_forecasts(
    db: Session,
    current_user: User,
    *,
    forecast_period: ForecastPeriod,
    custom_start_date: date | None,
    custom_end_date: date | None,
    force_refresh: bool,
    request: Request | None,
) -> dict:
    forecast_start, forecast_end, horizon_days = _resolve_period_window(
        forecast_period,
        custom_start_date,
        custom_end_date,
    )

    existing_snapshot = _existing_period_snapshot(
        db,
        current_user.company_id,
        forecast_period,
        forecast_start,
        forecast_end,
    )
    if existing_snapshot and not force_refresh:
        # Duplicate generation prevention for the same period.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Forecast for this period already exists. Use forceRefresh to regenerate.",
        )

    history_end = forecast_start - timedelta(days=1)
    history_start = history_end - timedelta(days=179)

    product_rows = _load_products_for_forecast(
        db,
        current_user.company_id,
        product_id=None,
        category_id=None,
        brand=None,
    )
    if not product_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active products available for forecasting")

    product_ids = [product.id for product, _, _ in product_rows]
    daily_sales = _aggregate_daily_sales(db, current_user.company_id, product_ids, history_start, history_end)

    if not any(sum(values) > 0 for values in daily_sales.values()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forecast generation requires historical sales data",
        )

    if existing_snapshot and force_refresh:
        previous_rows = db.scalars(
            select(DemandForecast).where(
                DemandForecast.company_id == current_user.company_id,
                DemandForecast.forecast_period == forecast_period,
                DemandForecast.forecast_start_date == forecast_start,
                DemandForecast.forecast_end_date == forecast_end,
            )
        ).all()
        for row in previous_rows:
            db.delete(row)
        db.flush()

    created_forecasts: list[DemandForecast] = []
    generation_time = datetime.now(UTC)

    for product, category, inventory in product_rows:
        values = daily_sales.get(product.id, [])
        historical_sales = round(sum(values), 2)
        predicted_demand, confidence, growth_percent = _moving_average_projection(values, horizon_days)
        growth_rate = growth_percent / 100.0

        recommendation_type, _ = _compute_recommendation(
            current_stock=_to_int(inventory.current_stock),
            reorder_level=_to_int(inventory.reorder_level),
            predicted_demand=predicted_demand,
        )

        forecast = DemandForecast(
            company_id=current_user.company_id,
            product_id=product.id,
            category_id=category.id,
            forecast_period=forecast_period,
            forecast_start_date=forecast_start,
            forecast_end_date=forecast_end,
            predicted_demand=predicted_demand,
            confidence_score=confidence,
            growth_rate=round(growth_rate, 4),
            recommendation_type=recommendation_type,
            generated_at=generation_time,
        )
        db.add(forecast)
        db.flush()

        # Accuracy proxy from previous forecast for same product and period window size.
        previous_prediction = db.scalar(
            select(DemandForecast.predicted_demand)
            .where(
                DemandForecast.company_id == current_user.company_id,
                DemandForecast.product_id == product.id,
                DemandForecast.id != forecast.id,
                DemandForecast.forecast_period == forecast_period,
            )
            .order_by(desc(DemandForecast.generated_at))
            .limit(1)
        )
        accuracy = None
        if previous_prediction is not None and historical_sales > 0:
            error_pct = abs(_to_float(previous_prediction) - historical_sales) / historical_sales * 100.0
            accuracy = max(0.0, min(100.0, 100.0 - error_pct))

        db.add(
            ForecastHistory(
                forecast_id=forecast.id,
                historical_sales=historical_sales,
                prediction=predicted_demand,
                accuracy=round(accuracy, 2) if accuracy is not None else None,
            )
        )
        created_forecasts.append(forecast)

    _create_notifications_for_forecasts(db, current_user.company_id, created_forecasts, current_user)

    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Forecast",
        entity_name=f"{forecast_period.value} ({forecast_start} to {forecast_end})",
        action=AuditAction.FORECAST_REFRESHED if force_refresh else AuditAction.FORECAST_GENERATED,
        request=request,
    )
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Forecast",
        entity_name="Inventory Recommendations",
        action=AuditAction.INVENTORY_RECOMMENDATION_GENERATED,
        request=request,
    )

    db.commit()
    return _build_dashboard_payload(db, current_user.company_id, created_forecasts)


def _fetch_latest_forecasts(
    db: Session,
    company_id: int,
    *,
    forecast_period: ForecastPeriod,
    custom_start_date: date | None,
    custom_end_date: date | None,
) -> list[DemandForecast]:
    forecast_start, forecast_end, _ = _resolve_period_window(forecast_period, custom_start_date, custom_end_date)
    snapshot = _existing_period_snapshot(db, company_id, forecast_period, forecast_start, forecast_end)
    if snapshot is None:
        return []
    return db.scalars(
        select(DemandForecast)
        .where(
            DemandForecast.company_id == company_id,
            DemandForecast.forecast_period == forecast_period,
            DemandForecast.forecast_start_date == forecast_start,
            DemandForecast.forecast_end_date == forecast_end,
            DemandForecast.generated_at == snapshot,
        )
        .order_by(DemandForecast.predicted_demand.desc())
    ).all()


def get_forecast_dashboard(
    db: Session,
    company_id: int,
    *,
    forecast_period: ForecastPeriod,
    custom_start_date: date | None,
    custom_end_date: date | None,
) -> dict:
    forecasts = _fetch_latest_forecasts(
        db,
        company_id,
        forecast_period=forecast_period,
        custom_start_date=custom_start_date,
        custom_end_date=custom_end_date,
    )
    if not forecasts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No forecasts generated for selected period")
    return _build_dashboard_payload(db, company_id, forecasts)


def list_forecasts(
    db: Session,
    company_id: int,
    *,
    forecast_period: ForecastPeriod,
    custom_start_date: date | None,
    custom_end_date: date | None,
    product_id: int | None,
    category_id: int | None,
    brand: str | None,
    search: str | None,
    sort_by: ForecastSortBy,
    sort_direction: ForecastSortDirection,
    page: int,
    page_size: int,
) -> dict:
    payload = get_forecast_dashboard(
        db,
        company_id,
        forecast_period=forecast_period,
        custom_start_date=custom_start_date,
        custom_end_date=custom_end_date,
    )

    rows = payload["products"]
    if product_id:
        rows = [item for item in rows if item["productId"] == product_id]
    if category_id:
        rows = [item for item in rows if item["categoryId"] == category_id]
    if brand:
        rows = [item for item in rows if (item.get("brand") or "").lower() == brand.strip().lower()]
    if search:
        term = search.strip().lower()
        rows = [item for item in rows if term in item["productName"].lower() or term in item["categoryName"].lower()]

    reverse = sort_direction == "desc"
    if sort_by == "lowestStock":
        rows.sort(key=lambda item: item["currentStock"], reverse=reverse)
    elif sort_by == "highestGrowth":
        rows.sort(key=lambda item: item["growthPercentage"], reverse=reverse)
    elif sort_by == "forecastAccuracy":
        rows.sort(key=lambda item: item["accuracy"] if item["accuracy"] is not None else -1, reverse=reverse)
    else:
        rows.sort(key=lambda item: item["predictedDemand"], reverse=reverse)

    total = len(rows)
    total_pages = (total + page_size - 1) // page_size if total else 0
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "items": rows[start:end],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def list_forecast_notifications(db: Session, company_id: int, limit: int = 20) -> list[dict]:
    rows = db.execute(
        select(ForecastNotification, Product.name)
        .outerjoin(Product, Product.id == ForecastNotification.product_id)
        .where(ForecastNotification.company_id == company_id)
        .order_by(ForecastNotification.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": notification.id,
            "forecastId": notification.forecast_id,
            "productId": notification.product_id,
            "productName": product_name,
            "notificationType": notification.notification_type.value,
            "message": notification.message,
            "createdAt": notification.created_at,
        }
        for notification, product_name in rows
    ]


def list_forecast_filters(db: Session, company_id: int) -> dict:
    products = db.execute(
        select(Product.id, Product.name)
        .where(Product.company_id == company_id, Product.status == ProductStatus.ACTIVE)
        .order_by(Product.name.asc())
    ).all()
    categories = db.execute(
        select(Category.id, Category.name)
        .where(Category.company_id == company_id)
        .order_by(Category.name.asc())
    ).all()
    brands = db.scalars(
        select(Product.brand)
        .where(Product.company_id == company_id, Product.brand.is_not(None))
        .distinct()
        .order_by(Product.brand.asc())
    ).all()

    return {
        "products": [{"id": pid, "name": name} for pid, name in products],
        "categories": [{"id": cid, "name": name} for cid, name in categories],
        "brands": [brand for brand in brands if brand],
    }


def export_forecast_report_csv(payload: dict) -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Demand Forecast Report"])
    writer.writerow(["Forecast Period", payload["forecastPeriod"]])
    writer.writerow(["Forecast Start", payload["forecastStartDate"]])
    writer.writerow(["Forecast End", payload["forecastEndDate"]])
    writer.writerow([])
    writer.writerow(["Product", "Category", "Current Stock", "Historical Sales", "Predicted Demand", "Confidence", "Growth %", "Recommendation"])
    for item in payload["products"]:
        writer.writerow(
            [
                item["productName"],
                item["categoryName"],
                item["currentStock"],
                item["historicalSales"],
                item["predictedDemand"],
                item["confidenceLevel"],
                item["growthPercentage"],
                item["recommendationType"],
            ]
        )
    return stream.getvalue().encode("utf-8")


def export_product_forecast_pdf(payload: dict) -> bytes:
    lines = [
        "Product Forecast Report",
        f"Period: {payload['forecastPeriod']}",
        f"Range: {payload['forecastStartDate']} to {payload['forecastEndDate']}",
        "",
    ]
    for item in payload["products"][:120]:
        lines.append(
            f"{item['productName']} | Stock {item['currentStock']} | Hist {item['historicalSales']:.2f} | Pred {item['predictedDemand']:.2f} | Conf {item['confidenceLevel']:.1f}%"
        )
    return _build_simple_pdf(lines)


def export_category_forecast_csv(payload: dict) -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Category Forecast Report"])
    writer.writerow(["Forecast Period", payload["forecastPeriod"]])
    writer.writerow([])
    writer.writerow(["Category", "Historical Sales", "Predicted Demand", "Expected Growth %"])
    for item in payload["categories"]:
        writer.writerow(
            [
                item["categoryName"],
                item["totalHistoricalSales"],
                item["predictedDemand"],
                item["expectedGrowthPercentage"],
            ]
        )
    return stream.getvalue().encode("utf-8")


def refresh_forecasts_for_company(
    db: Session,
    *,
    company_id: int,
    actor: User | None,
    request: Request | None,
) -> None:
    # Refresh common forecast windows when new sales arrive.
    # Failures are intentionally non-blocking for primary sale flow.
    pseudo_user = actor
    if pseudo_user is None:
        pseudo_user = db.scalar(select(User).where(User.company_id == company_id).order_by(User.id.asc()).limit(1))
        if pseudo_user is None:
            return

    for period in [ForecastPeriod.NEXT_7_DAYS, ForecastPeriod.NEXT_30_DAYS, ForecastPeriod.NEXT_90_DAYS]:
        try:
            generate_forecasts(
                db,
                pseudo_user,
                forecast_period=period,
                custom_start_date=None,
                custom_end_date=None,
                force_refresh=True,
                request=request,
            )
        except Exception:
            db.rollback()
            continue
