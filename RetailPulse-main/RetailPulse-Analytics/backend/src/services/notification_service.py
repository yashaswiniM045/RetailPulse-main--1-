from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any, Iterable

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.models.notification import Notification
from src.models.user import User, UserRole, UserStatus


# Role matrix: inventory insights go to admins and analysts; imports/system alerts to admins;
# viewers only receive explicitly viewer-safe sales/system notices when those events are added.
ROLE_MATRIX = {
    "stockout": {UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN},
    "low-stock": {UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST},
    "stockout-risk": {UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST},
    "overstock": {UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST},
    "import-completed": {UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN},
    "import-failed": {UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN},
    "sales-alert": {UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ANALYST},
    "system-alert": {UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN},
}


def create_notification(
    db: Session,
    *,
    company_id: int,
    event_key: str,
    notification_type: str,
    title: str,
    message: str,
    priority: str,
    resource_type: str | None = None,
    resource_id: int | str | None = None,
    details: dict[str, Any] | None = None,
    roles: Iterable[UserRole] | None = None,
    user_ids: Iterable[int] | None = None,
) -> int:
    allowed_roles = set(roles or ROLE_MATRIX.get(notification_type, set()))
    query = select(User).where(User.company_id == company_id, User.status == UserStatus.ACTIVE)
    if user_ids is not None:
        recipient_ids = set(user_ids)
        if not recipient_ids:
            return 0
        query = query.where(User.id.in_(recipient_ids))
    elif allowed_roles:
        query = query.where(User.role.in_(allowed_roles))
    else:
        return 0

    now = datetime.now(UTC)
    created = 0
    for recipient in db.scalars(query).all():
        existing = db.scalar(
            select(Notification).where(Notification.user_id == recipient.id, Notification.event_key == event_key)
        )
        if existing is not None and existing.resolved_at is None:
            continue
        if existing is not None:
            existing.type = notification_type
            existing.title = title
            existing.message = message
            existing.priority = priority
            existing.resource_type = resource_type
            existing.resource_id = str(resource_id) if resource_id is not None else None
            existing.details = details
            existing.is_read = False
            existing.read_at = None
            existing.created_at = now
            existing.resolved_at = None
            existing.expires_at = None
        else:
            db.add(
                Notification(
                    company_id=company_id,
                    user_id=recipient.id,
                    event_key=event_key,
                    type=notification_type,
                    title=title,
                    message=message,
                    priority=priority,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id is not None else None,
                    details=details,
                    expires_at=None,
                )
            )
        created += 1
    return created


def resolve_notification(db: Session, *, company_id: int, event_key: str) -> None:
    now = datetime.now(UTC)
    db.execute(
        update(Notification)
        .where(
            Notification.company_id == company_id,
            Notification.event_key == event_key,
            Notification.resolved_at.is_(None),
        )
        .values(resolved_at=now, expires_at=now + timedelta(days=7))
    )


def list_notifications(
    db: Session,
    *,
    user: User,
    page: int = 1,
    page_size: int = 20,
    read_filter: str | None = None,
    notification_type: str | None = None,
    priority: str | None = None,
) -> dict[str, Any]:
    conditions = [
        Notification.company_id == user.company_id,
        Notification.user_id == user.id,
        (Notification.expires_at.is_(None) | (Notification.expires_at > datetime.now(UTC))),
    ]
    if read_filter == "unread":
        conditions.append(Notification.is_read.is_(False))
    elif read_filter == "read":
        conditions.append(Notification.is_read.is_(True))
    if notification_type:
        conditions.append(Notification.type == notification_type)
    if priority:
        conditions.append(Notification.priority == priority)

    total = db.scalar(select(func.count(Notification.id)).where(*conditions)) or 0
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    items = db.scalars(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": ceil(total / page_size) if total else 0,
    }


def get_unread_count(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count(Notification.id)).where(
            Notification.company_id == user.company_id,
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
            (Notification.expires_at.is_(None) | (Notification.expires_at > datetime.now(UTC))),
        )
    ) or 0


def mark_notification_read(db: Session, user: User, notification_id: int) -> tuple[Notification, bool]:
    item = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.company_id == user.company_id,
            Notification.user_id == user.id,
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    changed = not item.is_read
    if changed:
        item.is_read = True
        item.read_at = datetime.now(UTC)
    return item, changed


def mark_all_notifications_read(db: Session, user: User) -> int:
    now = datetime.now(UTC)
    result = db.execute(
        update(Notification)
        .where(
            Notification.company_id == user.company_id,
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now)
    )
    return int(result.rowcount or 0)
