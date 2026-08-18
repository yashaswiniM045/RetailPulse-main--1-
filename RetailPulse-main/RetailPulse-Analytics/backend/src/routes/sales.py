from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from src.dependencies.auth import require_roles
from src.dependencies.database import get_db
from src.models.sale import PaymentMethod, PaymentStatus, SalesChannel
from src.models.user import User, UserRole
from src.schemas.sale import SaleListPageRead, SaleRead, SaleUpsert
from src.services.audit_service import AuditAction, create_audit_log
from src.services.sale_service import (
    create_sale,
    delete_sale,
    export_sale_invoice_csv,
    export_sale_invoice_pdf,
    get_sale,
    list_sales,
    update_sale,
)

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("", response_model=SaleListPageRead)
def list_sales_route(
    search: str | None = None,
    start_date: datetime | None = Query(default=None, alias="startDate"),
    end_date: datetime | None = Query(default=None, alias="endDate"),
    category_id: int | None = Query(default=None, alias="categoryId"),
    sales_channel: SalesChannel | None = Query(default=None, alias="salesChannel"),
    payment_method: PaymentMethod | None = Query(default=None, alias="paymentMethod"),
    payment_status: PaymentStatus | None = Query(default=None, alias="paymentStatus"),
    sort_by: Literal["date", "invoiceNumber", "totalAmount", "customerName"] = Query(default="date", alias="sortBy"),
    sort_direction: Literal["asc", "desc"] = Query(default="desc", alias="sortDirection"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return list_sales(
        db,
        current_user.company_id,
        search=search,
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
        sales_channel=sales_channel,
        payment_method=payment_method,
        payment_status=payment_status,
        sort_by=sort_by,
        sort_direction=sort_direction,
        page=page,
        page_size=page_size,
    )


@router.get("/{sale_id}", response_model=SaleRead)
def get_sale_route(
    sale_id: int,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return get_sale(db, current_user.company_id, sale_id)


@router.post("", response_model=SaleRead, status_code=status.HTTP_201_CREATED)
def create_sale_route(
    payload: SaleUpsert,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return create_sale(db, current_user, payload, request)


@router.put("/{sale_id}", response_model=SaleRead)
def update_sale_route(
    sale_id: int,
    payload: SaleUpsert,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    return update_sale(db, current_user, sale_id, payload, request)


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sale_route(
    sale_id: int,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    delete_sale(db, current_user, sale_id, request)


@router.get("/{sale_id}/invoice/csv")
def export_sale_invoice_csv_route(
    sale_id: int,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Sale",
        entity_name=f"Invoice {sale_id}",
        action=AuditAction.SALE_EXPORTED,
        request=request,
        export_type="csv",
    )
    db.commit()
    return Response(
        content=export_sale_invoice_csv(db, current_user.company_id, sale_id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="invoice-{sale_id}.csv"'},
    )


@router.get("/{sale_id}/invoice/pdf")
def export_sale_invoice_pdf_route(
    sale_id: int,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST)),
    db: Session = Depends(get_db),
):
    create_audit_log(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        performed_by=current_user.name,
        entity_type="Sale",
        entity_name=f"Invoice {sale_id}",
        action=AuditAction.SALE_EXPORTED,
        request=request,
        export_type="pdf",
    )
    db.commit()
    return Response(
        content=export_sale_invoice_pdf(db, current_user.company_id, sale_id),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="invoice-{sale_id}.pdf"'},
    )
