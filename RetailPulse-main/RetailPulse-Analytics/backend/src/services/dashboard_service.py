import csv
import io
from datetime import datetime
from typing import Literal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.models.category import Category
from src.models.customer import Customer
from src.models.inventory import Inventory, StockStatus
from src.models.product import Product, ProductStatus
from src.models.sale import PaymentMethod, Sale, SaleItem, SalesChannel


def _to_float(value: object) -> float:
    return float(value or 0)


def _to_int(value: object) -> int:
    return int(value or 0)


def _build_sales_filters(
    company_id: int,
    start_date: datetime | None,
    end_date: datetime | None,
    sales_channel: SalesChannel | None,
    payment_method: PaymentMethod | None,
) -> list:
    filters = [Sale.company_id == company_id]
    if start_date:
        filters.append(Sale.sale_date >= start_date)
    if end_date:
        filters.append(Sale.sale_date <= end_date)
    if sales_channel:
        filters.append(Sale.sales_channel == sales_channel)
    if payment_method:
        filters.append(Sale.payment_method == payment_method)
    return filters


def _build_product_filters(product_id: int | None, category_id: int | None, brand: str | None) -> list:
    filters = []
    if product_id:
        filters.append(Product.id == product_id)
    if category_id:
        filters.append(Product.category_id == category_id)
    if brand:
        filters.append(func.lower(Product.brand) == brand.strip().lower())
    return filters


def _period_label(period: datetime | None) -> str:
    if period is None:
        return ""
    return period.strftime("%Y-%m-%d")


def get_dashboard_summary(db: Session, company_id: int) -> dict:
    total_products = db.scalar(select(func.count(Product.id)).where(Product.company_id == company_id)) or 0
    active_products = (
        db.scalar(
            select(func.count(Product.id)).where(
                Product.company_id == company_id,
                Product.status == ProductStatus.ACTIVE,
            )
        )
        or 0
    )
    inactive_products = (
        db.scalar(
            select(func.count(Product.id)).where(
                Product.company_id == company_id,
                Product.status == ProductStatus.INACTIVE,
            )
        )
        or 0
    )
    total_categories = db.scalar(select(func.count(Category.id)).where(Category.company_id == company_id)) or 0
    total_sales = (
        db.scalar(
            select(func.coalesce(func.sum(SaleItem.quantity), 0))
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(Sale.company_id == company_id)
        )
        or 0
    )
    total_revenue = db.scalar(select(func.coalesce(func.sum(Sale.total_amount), 0)).where(Sale.company_id == company_id)) or 0
    total_orders = db.scalar(select(func.count(Sale.id)).where(Sale.company_id == company_id)) or 0
    average_order_value = float(total_revenue) / int(total_orders) if int(total_orders) > 0 else 0

    return {
        "totalProducts": int(total_products),
        "activeProducts": int(active_products),
        "inactiveProducts": int(inactive_products),
        "totalCategories": int(total_categories),
        "totalSales": int(total_sales),
        "totalRevenue": float(total_revenue),
        "totalOrders": int(total_orders),
        "averageOrderValue": float(average_order_value),
    }


def get_dashboard_filters(db: Session, company_id: int) -> dict:
    products = db.execute(
        select(Product.id, Product.name)
        .where(Product.company_id == company_id)
        .order_by(Product.name.asc())
    ).all()
    categories = db.execute(
        select(Category.id, Category.name)
        .where(Category.company_id == company_id)
        .order_by(Category.name.asc())
    ).all()
    brands = db.scalars(
        select(Product.brand)
        .where(and_(Product.company_id == company_id, Product.brand.is_not(None), Product.brand != ""))
        .distinct()
        .order_by(Product.brand.asc())
    ).all()

    return {
        "products": [{"id": int(product_id), "name": product_name} for product_id, product_name in products],
        "categories": [{"id": int(category_id), "name": category_name} for category_id, category_name in categories],
        "brands": [brand for brand in brands if brand],
        "salesChannels": list(SalesChannel),
        "paymentMethods": list(PaymentMethod),
    }


def get_dashboard_analytics(
    db: Session,
    company_id: int,
    *,
    date_grain: Literal["daily", "weekly", "monthly"] = "daily",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
    brand: str | None = None,
    sales_channel: SalesChannel | None = None,
    payment_method: PaymentMethod | None = None,
) -> dict:
    sales_filters = _build_sales_filters(company_id, start_date, end_date, sales_channel, payment_method)
    product_filters = _build_product_filters(product_id, category_id, brand)

    matching_sale_ids = (
        select(Sale.id)
        .select_from(Sale)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .join(Product, Product.id == SaleItem.product_id)
        .where(*sales_filters, *product_filters)
        .distinct()
        .subquery()
        if product_filters
        else None
    )
    sale_scope = select(Sale).where(*sales_filters)
    if matching_sale_ids is not None:
        sale_scope = sale_scope.where(Sale.id.in_(select(matching_sale_ids.c.id)))
    sale_scope = sale_scope.subquery()

    sales_summary = db.execute(
        select(
            func.coalesce(func.sum(sale_scope.c.total_amount), 0).label("revenue"),
            func.count(sale_scope.c.id).label("orders"),
            func.coalesce(func.sum(sale_scope.c.discount_total), 0).label("discount"),
            func.coalesce(func.sum(sale_scope.c.tax_total), 0).label("tax"),
        )
    ).one()

    total_revenue = _to_float(sales_summary.revenue)
    total_orders = _to_int(sales_summary.orders)
    total_discount = _to_float(sales_summary.discount)
    total_tax = _to_float(sales_summary.tax)
    total_products_sold = _to_int(
        db.scalar(
            select(func.coalesce(func.sum(SaleItem.quantity), 0))
            .select_from(SaleItem)
            .join(Product, Product.id == SaleItem.product_id)
            .where(SaleItem.sale_id.in_(select(sale_scope.c.id)), *product_filters)
        )
        or 0
    )
    average_order_value = total_revenue / total_orders if total_orders > 0 else 0

    sales_driven_filter_applied = any((start_date, end_date, sales_channel, payment_method))
    matching_product_subquery = None
    if sales_driven_filter_applied:
        matching_product_subquery = (
            select(SaleItem.product_id)
            .select_from(Sale)
            .join(SaleItem, SaleItem.sale_id == Sale.id)
            .join(Product, Product.id == SaleItem.product_id)
            .where(*sales_filters, *product_filters)
            .distinct()
            .subquery()
        )

    inventory_statement = (
        select(Inventory, Product, Category)
        .join(Product, Product.id == Inventory.product_id)
        .join(Category, Category.id == Product.category_id)
        .where(Inventory.company_id == company_id, *product_filters)
    )
    if matching_product_subquery is not None:
        inventory_statement = inventory_statement.where(
            Product.id.in_(select(matching_product_subquery.c.product_id))
        )
    inventory_rows = db.execute(inventory_statement).all()

    total_inventory_value = 0.0
    low_stock_rows = []
    out_of_stock_rows = []
    category_distribution: dict[tuple[int, str], dict] = {}
    inventory_value_by_category: dict[tuple[int, str], float] = {}
    stock_status_summary: dict[str, int] = {status.value: 0 for status in StockStatus}

    for inventory, product, category in inventory_rows:
        current_stock = _to_int(inventory.current_stock)
        row_value = current_stock * _to_float(product.cost_price)
        total_inventory_value += row_value
        key = (int(category.id), category.name)
        if key not in category_distribution:
            category_distribution[key] = {
                "categoryId": int(category.id),
                "categoryName": category.name,
                "quantity": 0,
                "productCount": 0,
            }
        category_distribution[key]["quantity"] += current_stock
        category_distribution[key]["productCount"] += 1
        inventory_value_by_category[key] = inventory_value_by_category.get(key, 0.0) + row_value

        status_value = inventory.stock_status.value if hasattr(inventory.stock_status, "value") else inventory.stock_status
        stock_status_summary[status_value] = stock_status_summary.get(status_value, 0) + 1

        inventory_item = {
            "productId": int(product.id),
            "productName": product.name,
            "sku": product.sku,
            "categoryName": category.name,
            "brand": product.brand,
            "currentStock": current_stock,
            "reorderLevel": _to_int(inventory.reorder_level),
            "stockStatus": inventory.stock_status,
        }
        if inventory.stock_status == StockStatus.LOW_STOCK:
            low_stock_rows.append(inventory_item)
        if inventory.stock_status == StockStatus.OUT_OF_STOCK:
            out_of_stock_rows.append(inventory_item)

    low_stock_rows.sort(key=lambda item: (item["currentStock"], item["productName"]))
    out_of_stock_rows.sort(key=lambda item: item["productName"])

    category_count_statement = (
        select(func.count(func.distinct(Category.id)))
        .select_from(Product)
        .join(Category, Category.id == Product.category_id)
        .where(Product.company_id == company_id, *product_filters)
    )
    if matching_product_subquery is not None:
        category_count_statement = category_count_statement.where(
            Product.id.in_(select(matching_product_subquery.c.product_id))
        )
    total_categories = _to_int(db.scalar(category_count_statement) or 0)

    grain_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    trunc_period = func.date_trunc(grain_map[date_grain], sale_scope.c.sale_date).label("period")
    sale_trend_rows = db.execute(
        select(
            trunc_period,
            func.coalesce(func.sum(sale_scope.c.total_amount), 0).label("revenue"),
            func.count(sale_scope.c.id).label("orders"),
        )
        .select_from(sale_scope)
        .group_by(trunc_period)
        .order_by(trunc_period.asc())
    ).all()
    item_trend_period = func.date_trunc(grain_map[date_grain], sale_scope.c.sale_date).label("period")
    item_trend_rows = db.execute(
        select(item_trend_period, func.coalesce(func.sum(SaleItem.quantity), 0).label("products_sold"))
        .select_from(sale_scope)
        .join(SaleItem, SaleItem.sale_id == sale_scope.c.id)
        .join(Product, Product.id == SaleItem.product_id)
        .where(*product_filters)
        .group_by(item_trend_period)
    ).all()
    item_trend_by_period = {period: products_sold for period, products_sold in item_trend_rows}

    trend_data = [
        {
            "period": _period_label(period),
            "revenue": _to_float(revenue),
            "orders": _to_int(orders),
            "productsSold": _to_int(item_trend_by_period.get(period, 0)),
        }
        for period, revenue, orders in sale_trend_rows
    ]

    top_products_rows = db.execute(
        select(
            Product.id,
            Product.name,
            func.coalesce(func.sum(SaleItem.quantity), 0).label("quantity_sold"),
            func.coalesce(func.sum(SaleItem.total), 0).label("revenue"),
        )
        .select_from(Sale)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .join(Product, Product.id == SaleItem.product_id)
        .where(*sales_filters, *product_filters)
        .group_by(Product.id, Product.name)
        .order_by(func.sum(SaleItem.quantity).desc(), Product.name.asc())
        .limit(10)
    ).all()

    top_categories_rows = db.execute(
        select(
            Category.id,
            Category.name,
            func.count(func.distinct(Sale.id)).label("orders"),
            func.coalesce(func.sum(SaleItem.quantity), 0).label("products_sold"),
            func.coalesce(func.sum(SaleItem.total), 0).label("revenue"),
        )
        .select_from(Sale)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .join(Product, Product.id == SaleItem.product_id)
        .join(Category, Category.id == Product.category_id)
        .where(*sales_filters, *product_filters)
        .group_by(Category.id, Category.name)
        .order_by(func.sum(SaleItem.total).desc(), Category.name.asc())
    ).all()

    payment_rows = db.execute(
        select(
            sale_scope.c.payment_method,
            func.coalesce(func.sum(sale_scope.c.total_amount), 0).label("value"),
            func.count(sale_scope.c.id).label("transactions"),
        )
        .select_from(sale_scope)
        .group_by(sale_scope.c.payment_method)
    ).all()

    channel_rows = db.execute(
        select(
            sale_scope.c.sales_channel,
            func.coalesce(func.sum(sale_scope.c.total_amount), 0).label("value"),
        )
        .select_from(sale_scope)
        .group_by(sale_scope.c.sales_channel)
    ).all()

    last_sale_updated = db.scalar(select(func.max(Sale.updated_at)).where(Sale.company_id == company_id))
    last_inventory_updated = db.scalar(select(func.max(Inventory.updated_at)).where(Inventory.company_id == company_id))
    top_customers_rows = db.execute(
        select(
            sale_scope.c.customer_id,
            sale_scope.c.customer_name,
            func.coalesce(func.sum(sale_scope.c.total_amount), 0).label("revenue"),
            func.count(sale_scope.c.id).label("orders"),
        )
        .select_from(sale_scope)
        .where(sale_scope.c.customer_id.is_not(None))
        .group_by(sale_scope.c.customer_id, sale_scope.c.customer_name)
        .order_by(func.sum(sale_scope.c.total_amount).desc(), sale_scope.c.customer_name.asc())
        .limit(10)
    ).all()
    recent_customers_rows = db.execute(
        select(Customer.id, Customer.customer_code, Customer.full_name, Customer.created_at)
        .where(Customer.company_id == company_id, Customer.is_deleted.is_(False))
        .order_by(Customer.created_at.desc())
        .limit(10)
    ).all()
    customer_growth_rows = db.execute(
        select(func.date(Customer.created_at), func.count(Customer.id))
        .where(Customer.company_id == company_id, Customer.is_deleted.is_(False))
        .group_by(func.date(Customer.created_at))
        .order_by(func.date(Customer.created_at).asc())
        .limit(30)
    ).all()
    total_customer_revenue = _to_float(
        db.scalar(
            select(func.coalesce(func.sum(Sale.total_amount), 0)).where(Sale.company_id == company_id, Sale.customer_id.is_not(None))
        )
        or 0
    )
    last_updated_at = None
    if last_sale_updated and last_inventory_updated:
        last_updated_at = max(last_sale_updated, last_inventory_updated)
    elif last_sale_updated:
        last_updated_at = last_sale_updated
    elif last_inventory_updated:
        last_updated_at = last_inventory_updated

    return {
        "kpis": {
            "totalRevenue": total_revenue,
            "totalOrders": total_orders,
            "totalProductsSold": total_products_sold,
            "averageOrderValue": average_order_value,
            "totalDiscount": total_discount,
            "totalTax": total_tax,
            "totalInventoryValue": total_inventory_value,
            "lowStockProducts": len(low_stock_rows),
            "outOfStockProducts": len(out_of_stock_rows),
            "totalCategories": total_categories,
        },
        "revenueTrend": trend_data,
        "salesTrend": trend_data,
        "topProducts": [
            {
                "productId": int(product_id_value),
                "productName": product_name,
                "quantitySold": _to_int(quantity_sold),
                "revenue": _to_float(revenue),
            }
            for product_id_value, product_name, quantity_sold, revenue in top_products_rows
        ],
        "topCategories": [
            {
                "categoryId": int(category_id_value),
                "categoryName": category_name,
                "orders": _to_int(orders),
                "productsSold": _to_int(products_sold),
                "revenue": _to_float(revenue),
            }
            for category_id_value, category_name, orders, products_sold, revenue in top_categories_rows
        ],
        "paymentMethodDistribution": [
            {
                "label": payment.value if hasattr(payment, "value") else str(payment),
                "value": _to_float(value),
                "transactions": _to_int(transaction_count),
            }
            for payment, value, transaction_count in payment_rows
        ],
        "salesChannelDistribution": [
            {
                "label": channel.value if hasattr(channel, "value") else str(channel),
                "value": _to_float(value),
            }
            for channel, value in channel_rows
        ],
        "inventoryDistributionByCategory": sorted(
            list(category_distribution.values()),
            key=lambda item: item["categoryName"],
        ),
        "stockStatusSummary": [
            {"label": status, "value": float(count)} for status, count in stock_status_summary.items() if count > 0
        ],
        "topLowStockProducts": low_stock_rows[:10],
        "outOfStockProducts": out_of_stock_rows,
        "inventoryValueByCategory": [
            {
                "categoryId": category_id_value,
                "categoryName": category_name,
                "inventoryValue": value,
            }
            for (category_id_value, category_name), value in sorted(
                inventory_value_by_category.items(), key=lambda item: item[0][1]
            )
        ],
        "topCustomers": [
            {
                "customerId": int(customer_id_value),
                "customerName": customer_name,
                "revenue": _to_float(revenue),
                "orders": _to_int(orders),
                "averageOrderValue": _to_float(revenue) / _to_int(orders) if _to_int(orders) else 0,
            }
            for customer_id_value, customer_name, revenue, orders in top_customers_rows
        ],
        "recentCustomers": [
            {
                "customerId": int(customer_id_value),
                "customerCode": customer_code,
                "customerName": customer_name,
                "customerSince": created_at,
            }
            for customer_id_value, customer_code, customer_name, created_at in recent_customers_rows
        ],
        "customerGrowth": [
            {"period": period.isoformat(), "value": _to_int(value)} for period, value in customer_growth_rows
        ],
        "customerRevenueContribution": [
            {
                "customerId": int(customer_id_value),
                "customerName": customer_name,
                "contributionPercent": (_to_float(revenue) / total_customer_revenue * 100) if total_customer_revenue > 0 else 0,
            }
            for customer_id_value, customer_name, revenue, _ in top_customers_rows[:5]
        ],
        "lastUpdatedAt": last_updated_at,
    }


def list_dashboard_kpi_records(
    db: Session,
    company_id: int,
    *,
    kpi_key: str,
    page: int,
    page_size: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
    brand: str | None = None,
    sales_channel: SalesChannel | None = None,
    payment_method: PaymentMethod | None = None,
) -> dict:
    sales_filters = _build_sales_filters(company_id, start_date, end_date, sales_channel, payment_method)
    product_filters = _build_product_filters(product_id, category_id, brand)

    items: list[dict] = []
    total = 0
    offset = (page - 1) * page_size

    if kpi_key in {"totalRevenue", "totalOrders", "averageOrderValue"}:
        base_statement = (
            select(Sale.id, Sale.invoice_number, Sale.customer_name, Sale.total_amount)
            .join(SaleItem, SaleItem.sale_id == Sale.id)
            .join(Product, Product.id == SaleItem.product_id)
            .where(*sales_filters, *product_filters)
            .group_by(Sale.id)
            .order_by(Sale.sale_date.desc())
        )
        rows = db.execute(base_statement.offset(offset).limit(page_size)).all()
        total = _to_int(
            db.scalar(
                select(func.count())
                .select_from(
                    select(Sale.id)
                    .join(SaleItem, SaleItem.sale_id == Sale.id)
                    .join(Product, Product.id == SaleItem.product_id)
                    .where(*sales_filters, *product_filters)
                    .group_by(Sale.id)
                    .subquery()
                )
            )
            or 0
        )
        items = [
            {
                "id": str(sale_id),
                "label": invoice_number,
                "secondary": customer_name,
                "value": _to_float(total_amount),
            }
            for sale_id, invoice_number, customer_name, total_amount in rows
        ]
    elif kpi_key == "totalProductsSold":
        base_statement = (
            select(Product.id, Product.name, func.coalesce(func.sum(SaleItem.quantity), 0).label("quantity_sold"))
            .select_from(Sale)
            .join(SaleItem, SaleItem.sale_id == Sale.id)
            .join(Product, Product.id == SaleItem.product_id)
            .where(*sales_filters, *product_filters)
            .group_by(Product.id, Product.name)
            .order_by(func.sum(SaleItem.quantity).desc(), Product.name.asc())
        )
        rows = db.execute(base_statement.offset(offset).limit(page_size)).all()
        total = _to_int(
            db.scalar(
                select(func.count())
                .select_from(
                    select(Product.id)
                    .select_from(Sale)
                    .join(SaleItem, SaleItem.sale_id == Sale.id)
                    .join(Product, Product.id == SaleItem.product_id)
                    .where(*sales_filters, *product_filters)
                    .group_by(Product.id)
                    .subquery()
                )
            )
            or 0
        )
        items = [
            {
                "id": str(product_id_value),
                "label": product_name,
                "secondary": "Quantity sold",
                "value": float(quantity_sold),
            }
            for product_id_value, product_name, quantity_sold in rows
        ]
    elif kpi_key in {"totalInventoryValue", "lowStockProducts", "outOfStockProducts"}:
        base_statement = (
            select(Inventory.id, Product.name, Product.sku, Inventory.current_stock, Product.cost_price, Inventory.stock_status)
            .join(Product, Product.id == Inventory.product_id)
            .where(Inventory.company_id == company_id, *product_filters)
            .order_by(Product.name.asc())
        )
        if kpi_key == "lowStockProducts":
            base_statement = base_statement.where(Inventory.stock_status == StockStatus.LOW_STOCK)
        if kpi_key == "outOfStockProducts":
            base_statement = base_statement.where(Inventory.stock_status == StockStatus.OUT_OF_STOCK)

        total = _to_int(
            db.scalar(select(func.count()).select_from(base_statement.subquery()))
            or 0
        )
        rows = db.execute(base_statement.offset(offset).limit(page_size)).all()
        items = [
            {
                "id": str(inventory_id),
                "label": product_name,
                "secondary": sku,
                "value": _to_float(current_stock) * _to_float(cost_price),
            }
            for inventory_id, product_name, sku, current_stock, cost_price, _ in rows
        ]
    elif kpi_key == "totalCategories":
        base_statement = (
            select(Category.id, Category.name, func.count(Product.id).label("product_count"))
            .select_from(Category)
            .join(Product, Product.category_id == Category.id)
            .where(Category.company_id == company_id, *product_filters)
            .group_by(Category.id, Category.name)
            .order_by(Category.name.asc())
        )
        total = _to_int(
            db.scalar(select(func.count()).select_from(base_statement.subquery()))
            or 0
        )
        rows = db.execute(base_statement.offset(offset).limit(page_size)).all()
        items = [
            {
                "id": str(category_id_value),
                "label": category_name,
                "secondary": "Products in category",
                "value": float(product_count),
            }
            for category_id_value, category_name, product_count in rows
        ]

    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def list_dashboard_category_products(
    db: Session,
    company_id: int,
    *,
    category_id: int,
    page: int,
    page_size: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    brand: str | None = None,
    sales_channel: SalesChannel | None = None,
    payment_method: PaymentMethod | None = None,
) -> dict:
    sales_filters = _build_sales_filters(company_id, start_date, end_date, sales_channel, payment_method)
    product_filters = _build_product_filters(None, category_id, brand)

    quantity_subquery = (
        select(
            SaleItem.product_id.label("product_id"),
            func.coalesce(func.sum(SaleItem.quantity), 0).label("quantity_sold"),
            func.coalesce(func.sum(SaleItem.total), 0).label("revenue"),
        )
        .select_from(Sale)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .join(Product, Product.id == SaleItem.product_id)
        .where(*sales_filters, *product_filters)
        .group_by(SaleItem.product_id)
        .subquery()
    )

    statement = (
        select(
            Product.id,
            Product.name,
            Product.sku,
            Product.brand,
            Inventory.current_stock,
            Inventory.stock_status,
            func.coalesce(quantity_subquery.c.quantity_sold, 0),
            func.coalesce(quantity_subquery.c.revenue, 0),
        )
        .join(Inventory, and_(Inventory.product_id == Product.id, Inventory.company_id == company_id))
        .outerjoin(quantity_subquery, quantity_subquery.c.product_id == Product.id)
        .where(Product.company_id == company_id, *product_filters)
        .order_by(Product.name.asc())
    )

    total = _to_int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = db.execute(statement.offset((page - 1) * page_size).limit(page_size)).all()
    total_pages = (total + page_size - 1) // page_size if total else 0

    return {
        "items": [
            {
                "productId": int(product_id_value),
                "productName": product_name,
                "sku": sku,
                "brand": product_brand,
                "currentStock": _to_int(current_stock),
                "stockStatus": stock_status,
                "quantitySold": _to_int(quantity_sold),
                "revenue": _to_float(revenue),
            }
            for product_id_value, product_name, sku, product_brand, current_stock, stock_status, quantity_sold, revenue in rows
        ],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def list_dashboard_product_transactions(
    db: Session,
    company_id: int,
    *,
    product_id: int,
    page: int,
    page_size: int,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    sales_channel: SalesChannel | None = None,
    payment_method: PaymentMethod | None = None,
) -> dict:
    sales_filters = _build_sales_filters(company_id, start_date, end_date, sales_channel, payment_method)
    statement = (
        select(
            Sale.id,
            Sale.invoice_number,
            Sale.sale_date,
            Sale.customer_name,
            Sale.sales_channel,
            Sale.payment_method,
            SaleItem.quantity,
            SaleItem.total,
        )
        .select_from(Sale)
        .join(SaleItem, SaleItem.sale_id == Sale.id)
        .where(*sales_filters, SaleItem.product_id == product_id)
        .order_by(Sale.sale_date.desc())
    )

    total = _to_int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = db.execute(statement.offset((page - 1) * page_size).limit(page_size)).all()
    total_pages = (total + page_size - 1) // page_size if total else 0

    return {
        "items": [
            {
                "saleId": int(sale_id),
                "invoiceNumber": invoice_number,
                "saleDate": sale_date,
                "customerName": customer_name,
                "salesChannel": sales_channel_value,
                "paymentMethod": payment_method_value,
                "quantity": _to_int(quantity),
                "total": _to_float(total_value),
            }
            for sale_id, invoice_number, sale_date, customer_name, sales_channel_value, payment_method_value, quantity, total_value in rows
        ],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def export_dashboard_csv(analytics: dict) -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream)

    writer.writerow(["RetailPulse Dashboard Report"])
    writer.writerow([])
    writer.writerow(["KPI", "Value"])
    for key, value in analytics["kpis"].items():
        writer.writerow([key, value])

    writer.writerow([])
    writer.writerow(["Revenue Trend"])
    writer.writerow(["Period", "Revenue", "Orders", "Products Sold"])
    for row in analytics["revenueTrend"]:
        writer.writerow([row["period"], row["revenue"], row["orders"], row["productsSold"]])

    writer.writerow([])
    writer.writerow(["Top Products"])
    writer.writerow(["Product", "Quantity Sold", "Revenue"])
    for row in analytics["topProducts"]:
        writer.writerow([row["productName"], row["quantitySold"], row["revenue"]])

    writer.writerow([])
    writer.writerow(["Top Categories"])
    writer.writerow(["Category", "Orders", "Products Sold", "Revenue"])
    for row in analytics["topCategories"]:
        writer.writerow([row["categoryName"], row["orders"], row["productsSold"], row["revenue"]])

    writer.writerow([])
    writer.writerow(["Out of Stock Products"])
    writer.writerow(["Product", "SKU", "Category", "Current Stock"])
    for row in analytics["outOfStockProducts"]:
        writer.writerow([row["productName"], row["sku"], row["categoryName"], row["currentStock"]])

    return stream.getvalue().encode("utf-8")


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def export_dashboard_pdf(analytics: dict) -> bytes:
    lines = [
        "RetailPulse Dashboard Report",
        "",
        "KPIs:",
        f"Total Revenue: {analytics['kpis']['totalRevenue']:.2f}",
        f"Total Orders: {analytics['kpis']['totalOrders']}",
        f"Total Products Sold: {analytics['kpis']['totalProductsSold']}",
        f"Average Order Value: {analytics['kpis']['averageOrderValue']:.2f}",
        f"Total Inventory Value: {analytics['kpis']['totalInventoryValue']:.2f}",
        f"Low Stock Products: {analytics['kpis']['lowStockProducts']}",
        f"Out Of Stock Products: {analytics['kpis']['outOfStockProducts']}",
        f"Total Categories: {analytics['kpis']['totalCategories']}",
        "",
        "Top Products:",
    ]
    for row in analytics["topProducts"][:10]:
        lines.append(f"- {row['productName']}: qty={row['quantitySold']} revenue={row['revenue']:.2f}")

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