from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.dependencies.auth import get_current_user
from src.dependencies.database import get_db
from src.models.user import User
from src.schemas.notification import NotificationPage, NotificationRead, UnreadCountRead
from src.services.audit_service import create_audit_log
from src.services.notification_service import (
    get_unread_count,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPage)
def list_notifications_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    read: str | None = Query(None, pattern="^(read|unread)$"),
    notification_type: str | None = Query(None, alias="type"),
    priority: str | None = Query(None, pattern="^(low|medium|high|critical)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_notifications(
        db,
        user=current_user,
        page=page,
        page_size=page_size,
        read_filter=read,
        notification_type=notification_type,
        priority=priority,
    )


@router.get("/unread-count", response_model=UnreadCountRead)
def unread_notification_count_route(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"unreadCount": get_unread_count(db, current_user)}


@router.patch("/read-all")
def mark_all_notifications_read_route(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changed = mark_all_notifications_read(db, current_user)
    if changed:
        create_audit_log(
            db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            performed_by=current_user.name,
            entity_type="Notification",
            action="Notifications Read",
            request=request,
            description=f"Marked {changed} notifications as read",
            after_values={"updatedCount": changed},
        )
    db.commit()
    return {"updatedCount": changed, "unreadCount": get_unread_count(db, current_user)}


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read_route(
    notification_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item, changed = mark_notification_read(db, current_user, notification_id)
    if changed:
        create_audit_log(
            db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            performed_by=current_user.name,
            entity_type="Notification",
            resource_id=item.id,
            entity_name=item.title,
            action="Notification Read",
            request=request,
            description=f"Read notification: {item.title}",
        )
    db.commit()
    db.refresh(item)
    return item
