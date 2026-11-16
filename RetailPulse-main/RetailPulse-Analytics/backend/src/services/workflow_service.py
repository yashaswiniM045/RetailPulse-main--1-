from datetime import UTC, datetime
from math import ceil
import re
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import String, exists, func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from src.models.customer import Customer, CustomerTimeline, CustomerTimelineType
from src.models.company import Company
from src.models.import_history import ImportHistory, ImportJob, ImportStatus
from src.models.inventory import InventoryMovementType
from src.models.product import Product, ProductStatus
from src.models.user import User, UserRole, UserStatus
from src.models.workflow import ApprovalHistory, ApprovalRequest, WorkflowConfiguration
from src.schemas.workflow import ApprovalRequestCreate, WorkflowConfigurationUpdate
from src.services.audit_service import AuditAction, create_audit_log
from src.services.import_service import start_staged_import
from src.services.inventory_service import (
    _apply_inventory_change,
    _get_inventory_for_product,
)
from src.services.notification_service import create_notification
from src.services.data_quality_service import run_incremental_checks

WORKFLOW_TYPES = (
    "stock-adjustment",
    "product-deactivation",
    "product-price-change",
    "customer-information-change",
    "inventory-import-approval",
)

TYPE_LABELS = {
    "stock-adjustment": "Stock Adjustment",
    "product-deactivation": "Product Deactivation",
    "product-price-change": "Product Price Change",
    "customer-information-change": "Customer Information Change",
    "inventory-import-approval": "Inventory Import Approval",
}

_CUSTOMER_FIELDS = {
    "fullName": ("full_name", str),
    "email": ("email", str),
    "phoneNumber": ("phone_number", str),
    "addressLine1": ("address_line1", str),
    "addressLine2": ("address_line2", str),
    "city": ("city", str),
    "state": ("state", str),
    "country": ("country", str),
    "postalCode": ("postal_code", str),
}


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow request not found")


def _role_value(role: UserRole | str) -> str:
    return role.value if isinstance(role, UserRole) else str(role)


def _is_admin(user: User) -> bool:
    return user.role in {UserRole.COMPANY_ADMIN, UserRole.SUPER_ADMIN}


def _default_config(company_id: int, request_type: str) -> WorkflowConfiguration:
    return WorkflowConfiguration(
        company_id=company_id,
        request_type=request_type,
        approver_role=UserRole.COMPANY_ADMIN.value,
        approval_required=True,
        allow_self_approval=False,
        is_active=True,
    )


def _get_or_create_config(db: Session, company_id: int, request_type: str) -> WorkflowConfiguration:
    config = db.scalar(
        select(WorkflowConfiguration).where(
            WorkflowConfiguration.company_id == company_id,
            WorkflowConfiguration.request_type == request_type,
        )
    )
    if config is None:
        config = _default_config(company_id, request_type)
        db.add(config)
        db.flush()
    return config


def workflow_requires_approval(db: Session, company_id: int, request_type: str) -> bool:
    config = db.scalar(
        select(WorkflowConfiguration.approval_required).where(
            WorkflowConfiguration.company_id == company_id,
            WorkflowConfiguration.request_type == request_type,
        )
    )
    return config is None or bool(config)


def list_workflow_configurations(db: Session, company_id: int) -> list[dict[str, Any]]:
    configs = {
        config.request_type: config
        for config in db.scalars(
            select(WorkflowConfiguration).where(WorkflowConfiguration.company_id == company_id)
        ).all()
    }
    for request_type in WORKFLOW_TYPES:
        if request_type not in configs:
            config = _default_config(company_id, request_type)
            db.add(config)
            configs[request_type] = config
    db.commit()
    return [_configuration_payload(configs[key]) for key in WORKFLOW_TYPES]


def _configuration_payload(config: WorkflowConfiguration) -> dict[str, Any]:
    return {
        "requestType": config.request_type,
        "label": TYPE_LABELS[config.request_type],
        "approverRole": config.approver_role,
        "approvalRequired": config.approval_required,
        "allowSelfApproval": config.allow_self_approval,
        "isActive": config.is_active,
        "updatedAt": config.updated_at.isoformat() if config.updated_at else None,
    }


def update_workflow_configuration(
    db: Session,
    user: User,
    request_type: str,
    payload: WorkflowConfigurationUpdate,
    request: Request,
) -> dict[str, Any]:
    if request_type not in WORKFLOW_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow type not found")
    config = _get_or_create_config(db, user.company_id, request_type)
    if config.approval_required and not payload.approval_required:
        pending_count = db.scalar(
            select(func.count(ApprovalRequest.id)).where(
                ApprovalRequest.company_id == user.company_id,
                ApprovalRequest.request_type == request_type,
                ApprovalRequest.status == "pending-approval",
            )
        ) or 0
        if pending_count:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resolve pending requests before disabling approval for this workflow",
            )
    before = _configuration_payload(config)
    config.approver_role = payload.approver_role.value
    config.approval_required = payload.approval_required
    config.allow_self_approval = payload.allow_self_approval
    config.is_active = payload.is_active
    config.updated_by_id = user.id
    if config.is_active:
        db.execute(
            update(ApprovalRequest)
            .where(
                ApprovalRequest.company_id == user.company_id,
                ApprovalRequest.request_type == request_type,
                ApprovalRequest.status == "pending-approval",
            )
            .values(approver_role=config.approver_role)
        )
    create_audit_log(
        db,
        company_id=user.company_id,
        user_id=user.id,
        performed_by=user.name,
        entity_type="Workflow Configuration",
        resource_id=request_type,
        entity_name=TYPE_LABELS[request_type],
        action=AuditAction.WORKFLOW_CONFIGURATION_CHANGED,
        request=request,
        description=f"Updated {TYPE_LABELS[request_type]} workflow configuration",
        before_values=before,
        after_values=_configuration_payload(config),
    )
    db.commit()
    db.refresh(config)
    return _configuration_payload(config)


def _serialize_current(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _load_related(
    db: Session,
    company_id: int,
    request_type: str,
    record_id: int,
    *,
    require_uploaded_import: bool = False,
):
    if request_type in {"stock-adjustment", "product-deactivation", "product-price-change"}:
        product = db.scalar(
            select(Product)
            .options(joinedload(Product.category))
            .where(Product.id == record_id, Product.company_id == company_id)
        )
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return product
    if request_type == "customer-information-change":
        customer = db.scalar(
            select(Customer).where(
                Customer.id == record_id,
                Customer.company_id == company_id,
                Customer.is_deleted.is_(False),
            )
        )
        if customer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        return customer
    import_record = db.scalar(
        select(ImportHistory).where(
            ImportHistory.id == record_id,
            ImportHistory.company_id == company_id,
        )
    )
    if import_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")
    if require_uploaded_import and (
        import_record.status != ImportStatus.UPLOADED.value or db.get(ImportJob, import_record.id) is None
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only uploaded imports can be submitted for approval")
    return import_record


def _validated_changes(request_type: str, changes: dict[str, Any]) -> dict[str, Any]:
    if request_type == "stock-adjustment":
        if set(changes) != {"targetQuantity"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide only targetQuantity")
        target = changes.get("targetQuantity")
        if isinstance(target, bool) or not isinstance(target, int) or not 0 <= target <= 2_147_483_647:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="targetQuantity must be a non-negative integer")
        return {"targetQuantity": target}
    if request_type == "product-price-change":
        if not changes or set(changes) - {"unitPrice", "costPrice"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide unitPrice and/or costPrice")
        normalized: dict[str, float] = {}
        for field in ("unitPrice", "costPrice"):
            if field not in changes:
                continue
            try:
                value = float(changes[field])
            except (TypeError, ValueError):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} must be a number")
            minimum = 0 if field == "costPrice" else 0
            if value < minimum or value >= 1_000_000_000 or (field == "unitPrice" and value == 0):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} is outside the allowed range")
            normalized[field] = value
        return normalized
    if request_type == "product-deactivation":
        if changes not in ({"status": "inactive"}, {}):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Product deactivation must request status inactive")
        return {"status": "inactive"}
    if request_type == "customer-information-change":
        if not changes or set(changes) - _CUSTOMER_FIELDS.keys():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Customer changes contain unsupported or missing fields")
        normalized: dict[str, Any] = {}
        for field, value in changes.items():
            if value is not None and not isinstance(value, str):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} must be text or null")
            value = value.strip() if isinstance(value, str) else value
            if field in {"fullName", "email", "phoneNumber", "addressLine1", "city", "state", "country", "postalCode"} and not value:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} cannot be blank")
            max_lengths = {"phoneNumber": 50, "addressLine2": 255}
            if isinstance(value, str) and len(value) > max_lengths.get(field, 255):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} is too long")
            if field == "email" and value:
                try:
                    value = str(TypeAdapter(EmailStr).validate_python(value)).lower()
                except (ValidationError, ValueError):
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="email must be a valid email address")
            if field == "phoneNumber" and value and not re.fullmatch(r"\+?[0-9\-\s()]{7,20}", value):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="phoneNumber format is invalid")
            normalized[field] = value
        return normalized
    if request_type == "inventory-import-approval":
        if changes not in ({}, {"action": "start-import"}):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Import approval does not accept business data changes")
        return {"action": "start-import"}
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported workflow type")


def _current_values(request_type: str, record: Any, changes: dict[str, Any]) -> dict[str, Any]:
    if request_type == "stock-adjustment":
        inventory = record.inventory
        current_quantity = inventory.current_stock if inventory is not None else record.stock_quantity
        return {"currentQuantity": int(current_quantity)}
    if request_type == "product-price-change":
        return {"unitPrice": float(record.unit_price), "costPrice": float(record.cost_price)}
    if request_type == "product-deactivation":
        return {"status": _serialize_current(record.status)}
    if request_type == "customer-information-change":
        return {
            field: _serialize_current(getattr(record, attribute))
            for field, (attribute, _) in _CUSTOMER_FIELDS.items()
            if field in changes
        }
    return {"status": record.status, "filename": record.filename}


def _history(
    db: Session,
    approval: ApprovalRequest,
    *,
    action: str,
    actor_id: int | None,
    comment: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        ApprovalHistory(
            request_id=approval.id,
            company_id=approval.company_id,
            actor_id=actor_id,
            action=action,
            comment=comment,
            details=details,
        )
    )


def _notify(
    db: Session,
    approval: ApprovalRequest,
    *,
    event: str,
    recipients: list[int] | None = None,
    roles: list[UserRole] | None = None,
) -> None:
    request_id = f"APR-{approval.id:06d}"
    create_notification(
        db,
        company_id=approval.company_id,
        event_key=f"workflow:{approval.id}:{event}",
        notification_type="workflow-request",
        title=f"{TYPE_LABELS[approval.request_type]} {event.replace('-', ' ')}",
        message=f"{request_id} — {TYPE_LABELS[approval.request_type]} ({approval.status})",
        priority=approval.priority,
        resource_type="WorkflowRequest",
        resource_id=approval.id,
        details={"requestId": request_id, "requestType": approval.request_type, "status": approval.status, "url": f"/workflows?requestId={approval.id}"},
        user_ids=recipients,
        roles=roles,
    )


def _notify_approvers(db: Session, approval: ApprovalRequest, *, event: str = "assigned") -> None:
    config = db.scalar(
        select(WorkflowConfiguration).where(
            WorkflowConfiguration.company_id == approval.company_id,
            WorkflowConfiguration.request_type == approval.request_type,
        )
    )
    recipients = db.scalars(
        select(User.id).where(
            User.company_id == approval.company_id,
            User.role == UserRole(approval.approver_role),
            User.status == UserStatus.ACTIVE,
            *(
                []
                if config and config.allow_self_approval
                else [User.id != approval.requested_by_id]
            ),
        )
    ).all()
    _notify(db, approval, event=event, recipients=list(recipients))


def create_workflow_request(
    db: Session,
    user: User,
    payload: ApprovalRequestCreate,
    request: Request | None = None,
) -> dict[str, Any]:
    config = _get_or_create_config(db, user.company_id, payload.request_type)
    if not config.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This workflow is inactive")
    changes = _validated_changes(payload.request_type, payload.requested_changes)
    related = _load_related(
        db,
        user.company_id,
        payload.request_type,
        payload.related_record_id,
        require_uploaded_import=True,
    )
    current_values = _current_values(payload.request_type, related, changes)
    if payload.request_type == "stock-adjustment" and current_values["currentQuantity"] == changes["targetQuantity"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The requested stock quantity is unchanged")
    if payload.request_type == "product-price-change":
        requested_price = changes.get("unitPrice", float(related.unit_price))
        requested_cost = changes.get("costPrice", float(related.cost_price))
        if requested_price <= requested_cost:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unit price must be greater than product cost")
        if all(changes[field] == current_values[field] for field in changes):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The requested unit price is unchanged")
    if payload.request_type == "product-deactivation" and current_values["status"] == ProductStatus.INACTIVE.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product is already inactive")
    if payload.request_type == "customer-information-change" and all(
        _serialize_current(getattr(related, _CUSTOMER_FIELDS[field][0])) == value
        for field, value in changes.items()
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The requested customer information is unchanged")
    open_request = db.scalar(
        select(ApprovalRequest.id).where(
            ApprovalRequest.company_id == user.company_id,
            ApprovalRequest.request_type == payload.request_type,
            ApprovalRequest.related_record_id == payload.related_record_id,
            ApprovalRequest.status.in_(("draft", "pending-approval", "processing")),
        )
    )
    if open_request is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An open request already exists for this record and workflow")
    initial_status = "draft" if payload.draft else "pending-approval"
    if not config.approval_required and not payload.draft:
        initial_status = "approved"
    approval = ApprovalRequest(
        company_id=user.company_id,
        request_type=payload.request_type,
        requested_by_id=user.id,
        approver_role=config.approver_role,
        related_record_type={
            "stock-adjustment": "Product",
            "product-deactivation": "Product",
            "product-price-change": "Product",
            "customer-information-change": "Customer",
            "inventory-import-approval": "Import",
        }[payload.request_type],
        related_record_id=payload.related_record_id,
        current_values=current_values,
        requested_changes=changes,
        reason=payload.reason,
        priority=payload.priority,
        status=initial_status,
    )
    db.add(approval)
    db.flush()
    _history(db, approval, action="created", actor_id=user.id, details={"status": "draft"})
    create_audit_log(
        db,
        company_id=user.company_id,
        user_id=user.id,
        performed_by=user.name,
        entity_type="Workflow Request",
        resource_id=approval.id,
        entity_name=TYPE_LABELS[approval.request_type],
        action=AuditAction.WORKFLOW_REQUEST_CREATED,
        request=request,
        description=f"Created {TYPE_LABELS[approval.request_type]} request APR-{approval.id:06d}",
        after_values={"requestType": approval.request_type, "requestedChanges": changes, "status": initial_status},
    )
    if not payload.draft:
        _history(db, approval, action="submitted", actor_id=user.id)
        if config.approval_required:
            _history(db, approval, action="pending-approval", actor_id=user.id)
            _notify_approvers(db, approval)
        else:
            _apply_requested_change(db, approval, user, request)
            _history(db, approval, action="auto-approved", actor_id=None, comment="Approval is not required by workflow configuration")
            create_audit_log(
                db,
                company_id=user.company_id,
                user_id=None,
                performed_by="System",
                entity_type="Workflow Request",
                resource_id=approval.id,
                entity_name=TYPE_LABELS[approval.request_type],
                action=AuditAction.WORKFLOW_REQUEST_APPROVED,
                request=request,
                description=f"Automatically approved request APR-{approval.id:06d}",
                after_values={"status": "approved"},
            )
        create_audit_log(
            db,
            company_id=user.company_id,
            user_id=user.id,
            performed_by=user.name,
            entity_type="Workflow Request",
            resource_id=approval.id,
            entity_name=TYPE_LABELS[approval.request_type],
            action=AuditAction.WORKFLOW_REQUEST_SUBMITTED,
            request=request,
            description=f"Submitted request APR-{approval.id:06d}",
            after_values={"status": approval.status},
        )
        _notify(db, approval, event="submitted", recipients=[user.id])
        if not config.approval_required:
            _notify(db, approval, event="approved", recipients=[user.id])
    db.commit()
    db.refresh(approval)
    return get_workflow_request(db, user, approval.id, record_view=False)


def _apply_requested_change(
    db: Session,
    approval: ApprovalRequest,
    actor: User,
    request: Request | None,
    comment: str | None = None,
) -> dict[str, Any]:
    changes = _validated_changes(approval.request_type, approval.requested_changes)
    related = _load_related(db, approval.company_id, approval.request_type, approval.related_record_id)
    current = _current_values(approval.request_type, related, changes)
    if current != approval.current_values:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The related record changed after submission. Cancel this request and submit an updated request.",
        )
    if approval.request_type == "stock-adjustment":
        inventory = _get_inventory_for_product(db, approval.company_id, related.id)
        target = changes["targetQuantity"]
        _apply_inventory_change(
            db,
            inventory=inventory,
            movement_type=InventoryMovementType.MANUAL_ADJUSTMENT,
            quantity_delta=target - inventory.current_stock,
            reason=approval.reason,
            remarks=comment,
            actor=actor,
            request=request,
        )
        run_incremental_checks(db, actor, product_ids={related.id}, request=request)
    elif approval.request_type == "product-price-change":
        requested_price = changes.get("unitPrice", float(related.unit_price))
        requested_cost = changes.get("costPrice", float(related.cost_price))
        if requested_price <= requested_cost:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product cost changed; the requested price is no longer valid")
        if "unitPrice" in changes:
            related.unit_price = changes["unitPrice"]
        if "costPrice" in changes:
            related.cost_price = changes["costPrice"]
        run_incremental_checks(db, actor, product_ids={related.id}, request=request)
    elif approval.request_type == "product-deactivation":
        related.status = ProductStatus.INACTIVE
        run_incremental_checks(db, actor, product_ids={related.id}, request=request)
    elif approval.request_type == "customer-information-change":
        for field, value in changes.items():
            attribute, _ = _CUSTOMER_FIELDS[field]
            if field in {"email", "phoneNumber"} and value:
                duplicate = db.scalar(
                    select(Customer.id).where(
                        Customer.company_id == approval.company_id,
                        getattr(Customer, attribute) == value,
                        Customer.id != related.id,
                        Customer.is_deleted.is_(False),
                    )
                )
                if duplicate:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Another customer already uses {field}")
            setattr(related, attribute, value)
        related.updated_by = actor.id
        db.add(
            CustomerTimeline(
                company_id=approval.company_id,
                customer_id=related.id,
                event_type=CustomerTimelineType.PROFILE_UPDATED,
                title="Customer information updated",
                description=f"Approved workflow request APR-{approval.id:06d}",
                created_by=actor.id,
            )
        )
        run_incremental_checks(db, actor, customer_ids={related.id}, request=request)
    elif approval.request_type == "inventory-import-approval":
        start_staged_import(db, actor, related.id, request, commit=False)
    db.flush()
    return {"recordType": approval.related_record_type, "recordId": approval.related_record_id}


def _can_view(user: User, approval: ApprovalRequest) -> bool:
    return (
        approval.company_id == user.company_id
        and (approval.requested_by_id == user.id or _is_admin(user) or approval.approver_role == _role_value(user.role))
    )


def _get_request(db: Session, user: User, request_id: int, *, lock: bool = False) -> ApprovalRequest:
    statement = (
        select(ApprovalRequest)
        .options(joinedload(ApprovalRequest.requester))
        .where(ApprovalRequest.id == request_id, ApprovalRequest.company_id == user.company_id)
    )
    if lock:
        statement = statement.with_for_update()
    approval = db.scalar(statement)
    if approval is None or not _can_view(user, approval):
        raise _not_found()
    return approval


def _history_payload(db: Session, approval: ApprovalRequest) -> list[dict[str, Any]]:
    rows = db.execute(
        select(ApprovalHistory, User.name)
        .outerjoin(User, ApprovalHistory.actor_id == User.id)
        .where(ApprovalHistory.request_id == approval.id, ApprovalHistory.company_id == approval.company_id)
        .order_by(ApprovalHistory.created_at, ApprovalHistory.id)
    ).all()
    return [
        {
            "id": item.id,
            "action": item.action,
            "actorId": item.actor_id,
            "actorName": actor_name or ("System" if item.actor_id is None else "Former user"),
            "comment": item.comment,
            "details": item.details,
            "createdAt": item.created_at,
        }
        for item, actor_name in rows
    ]


def _related_payload(db: Session, approval: ApprovalRequest) -> dict[str, Any]:
    record = _load_related(db, approval.company_id, approval.request_type, approval.related_record_id)
    if approval.request_type in {"stock-adjustment", "product-deactivation", "product-price-change"}:
        return {"type": "Product", "id": record.id, "name": record.name, "sku": record.sku, "category": record.category.name}
    if approval.request_type == "customer-information-change":
        return {"type": "Customer", "id": record.id, "name": record.full_name, "email": record.email}
    return {"type": "Import", "id": record.id, "name": record.filename, "status": record.status}


def _request_payload(db: Session, approval: ApprovalRequest, *, include_history: bool = True) -> dict[str, Any]:
    config = db.scalar(
        select(WorkflowConfiguration).where(
            WorkflowConfiguration.company_id == approval.company_id,
            WorkflowConfiguration.request_type == approval.request_type,
        )
    )
    return {
        "id": approval.id,
        "requestId": f"APR-{approval.id:06d}",
        "requestType": approval.request_type,
        "requestTypeLabel": TYPE_LABELS[approval.request_type],
        "requestedBy": {
            "id": approval.requester.id,
            "name": approval.requester.name,
            "email": approval.requester.email,
        },
        "companyId": approval.company_id,
        "companyName": db.scalar(select(Company.name).where(Company.id == approval.company_id)),
        "relatedRecordType": approval.related_record_type,
        "relatedRecordId": approval.related_record_id,
        "relatedRecord": _related_payload(db, approval),
        "currentValues": approval.current_values,
        "requestedChanges": approval.requested_changes,
        "reason": approval.reason,
        "priority": approval.priority,
        "status": approval.status,
        "approverRole": approval.approver_role,
        "allowSelfApproval": bool(config and config.allow_self_approval),
        "createdAt": approval.created_at,
        "updatedAt": approval.updated_at,
        "history": _history_payload(db, approval) if include_history else [],
    }


def get_workflow_request(
    db: Session,
    user: User,
    request_id: int,
    *,
    record_view: bool = True,
) -> dict[str, Any]:
    approval = _get_request(db, user, request_id)
    if record_view:
        _history(db, approval, action="viewed", actor_id=user.id)
        db.commit()
        db.refresh(approval)
    return _request_payload(db, approval)


def list_workflow_requests(
    db: Session,
    user: User,
    *,
    scope: str = "all",
    request_type: str | None = None,
    status_filter: str | None = None,
    search: str | None = None,
    sort_direction: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    if scope not in {"all", "mine", "queue"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid workflow scope")
    conditions = [ApprovalRequest.company_id == user.company_id]
    if scope == "mine" or (scope == "all" and not _is_admin(user)):
        conditions.append(ApprovalRequest.requested_by_id == user.id)
    elif scope == "queue":
        conditions.extend(
            [
                ApprovalRequest.status == "pending-approval",
                or_(
                    ApprovalRequest.approver_role == _role_value(user.role),
                    _is_admin(user),
                ),
                or_(
                    ApprovalRequest.requested_by_id != user.id,
                    exists(
                        select(WorkflowConfiguration.id).where(
                            WorkflowConfiguration.company_id == ApprovalRequest.company_id,
                            WorkflowConfiguration.request_type == ApprovalRequest.request_type,
                            WorkflowConfiguration.allow_self_approval.is_(True),
                        )
                    ),
                ),
            ]
        )
    if request_type:
        if request_type not in WORKFLOW_TYPES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid workflow type")
        conditions.append(ApprovalRequest.request_type == request_type)
    if status_filter:
        if status_filter not in {"draft", "submitted", "pending-approval", "approved", "rejected", "cancelled"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid workflow status")
        conditions.append(ApprovalRequest.status == status_filter)
    if search:
        pattern = f"%{search.strip().lower()}%"
        conditions.append(
            func.lower(ApprovalRequest.reason).like(pattern)
            | func.lower(ApprovalRequest.request_type).like(pattern)
            | func.cast(ApprovalRequest.related_record_id, String).like(pattern)
        )
    total = db.scalar(select(func.count(ApprovalRequest.id)).where(*conditions)) or 0
    direction = ApprovalRequest.created_at.asc() if sort_direction == "asc" else ApprovalRequest.created_at.desc()
    approvals = db.scalars(
        select(ApprovalRequest)
        .options(joinedload(ApprovalRequest.requester))
        .where(*conditions)
        .order_by(direction, ApprovalRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()
    return {
        "items": [_request_payload(db, approval, include_history=False) for approval in approvals],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": ceil(total / page_size) if total else 0,
    }


def _ensure_pending(db: Session, approval: ApprovalRequest) -> None:
    result = db.execute(
        update(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval.id,
            ApprovalRequest.company_id == approval.company_id,
            ApprovalRequest.status == "pending-approval",
        )
        .values(status="processing", updated_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request is no longer pending approval")
    approval.status = "processing"


def _authorize_approver(db: Session, user: User, approval: ApprovalRequest) -> WorkflowConfiguration:
    config = db.scalar(
        select(WorkflowConfiguration).where(
            WorkflowConfiguration.company_id == approval.company_id,
            WorkflowConfiguration.request_type == approval.request_type,
        )
    )
    if config is None or not config.approval_required:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This workflow is not accepting approval actions")
    if user.role.value != config.approver_role and not _is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not an approver for this workflow")
    if approval.requested_by_id == user.id and not config.allow_self_approval:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot approve your own request")
    return config


def approve_workflow_request(
    db: Session,
    user: User,
    request_id: int,
    comment: str | None,
    request: Request | None,
) -> dict[str, Any]:
    approval = _get_request(db, user, request_id, lock=True)
    _authorize_approver(db, user, approval)
    _ensure_pending(db, approval)
    approval.status = "approved"
    _apply_requested_change(db, approval, user, request, comment)
    _history(db, approval, action="approved", actor_id=user.id, comment=comment)
    _history(db, approval, action="change-applied", actor_id=user.id, details={"recordType": approval.related_record_type, "recordId": approval.related_record_id})
    create_audit_log(
        db,
        company_id=approval.company_id,
        user_id=user.id,
        performed_by=user.name,
        entity_type="Workflow Request",
        resource_id=approval.id,
        entity_name=TYPE_LABELS[approval.request_type],
        action=AuditAction.WORKFLOW_REQUEST_APPROVED,
        request=request,
        description=f"Approved request APR-{approval.id:06d} and applied its requested change",
        before_values=approval.current_values,
        after_values=approval.requested_changes,
    )
    _notify(db, approval, event="approved", recipients=[approval.requested_by_id])
    db.commit()
    db.refresh(approval)
    return _request_payload(db, approval)


def reject_workflow_request(
    db: Session,
    user: User,
    request_id: int,
    comment: str,
    request: Request | None,
) -> dict[str, Any]:
    approval = _get_request(db, user, request_id, lock=True)
    _authorize_approver(db, user, approval)
    _ensure_pending(db, approval)
    approval.status = "rejected"
    _history(db, approval, action="rejected", actor_id=user.id, comment=comment)
    create_audit_log(
        db,
        company_id=approval.company_id,
        user_id=user.id,
        performed_by=user.name,
        entity_type="Workflow Request",
        resource_id=approval.id,
        entity_name=TYPE_LABELS[approval.request_type],
        action=AuditAction.WORKFLOW_REQUEST_REJECTED,
        request=request,
        description=f"Rejected request APR-{approval.id:06d}",
        after_values={"status": "rejected", "reason": comment},
    )
    _notify(db, approval, event="rejected", recipients=[approval.requested_by_id])
    db.commit()
    db.refresh(approval)
    return _request_payload(db, approval)


def cancel_workflow_request(
    db: Session,
    user: User,
    request_id: int,
    request: Request | None,
) -> dict[str, Any]:
    approval = _get_request(db, user, request_id, lock=True)
    if approval.requested_by_id != user.id and not _is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the requester or a company admin can cancel this request")
    if approval.status not in {"draft", "pending-approval"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft or pending requests can be cancelled")
    result = db.execute(
        update(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval.id,
            ApprovalRequest.company_id == user.company_id,
            ApprovalRequest.status == approval.status,
        )
        .values(status="cancelled", updated_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request is no longer cancellable")
    approval.status = "cancelled"
    _history(db, approval, action="cancelled", actor_id=user.id)
    create_audit_log(
        db,
        company_id=user.company_id,
        user_id=user.id,
        performed_by=user.name,
        entity_type="Workflow Request",
        resource_id=approval.id,
        entity_name=TYPE_LABELS[approval.request_type],
        action=AuditAction.WORKFLOW_REQUEST_CANCELLED,
        request=request,
        description=f"Cancelled request APR-{approval.id:06d}",
        after_values={"status": "cancelled"},
    )
    _notify(db, approval, event="cancelled", recipients=[approval.requested_by_id])
    _notify_approvers(db, approval, event="cancelled")
    db.commit()
    db.refresh(approval)
    return _request_payload(db, approval)


def submit_workflow_request(
    db: Session,
    user: User,
    request_id: int,
    request: Request | None,
) -> dict[str, Any]:
    approval = _get_request(db, user, request_id, lock=True)
    if approval.requested_by_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the requester can submit this request")
    if approval.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft requests can be submitted")
    config = _get_or_create_config(db, user.company_id, approval.request_type)
    if not config.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This workflow is inactive")
    result = db.execute(
        update(ApprovalRequest)
        .where(ApprovalRequest.id == approval.id, ApprovalRequest.status == "draft")
        .values(
            status="pending-approval" if config.approval_required else "approved",
            approver_role=config.approver_role,
            updated_at=datetime.now(UTC),
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request can no longer be submitted")
    approval.status = "pending-approval" if config.approval_required else "approved"
    approval.approver_role = config.approver_role
    _history(db, approval, action="submitted", actor_id=user.id)
    if config.approval_required:
        _history(db, approval, action="pending-approval", actor_id=user.id)
        _notify_approvers(db, approval)
    else:
        _apply_requested_change(db, approval, user, request)
        _history(db, approval, action="auto-approved", actor_id=None, comment="Approval is not required by workflow configuration")
        create_audit_log(
            db,
            company_id=user.company_id,
            user_id=None,
            performed_by="System",
            entity_type="Workflow Request",
            resource_id=approval.id,
            entity_name=TYPE_LABELS[approval.request_type],
            action=AuditAction.WORKFLOW_REQUEST_APPROVED,
            request=request,
            description=f"Automatically approved request APR-{approval.id:06d}",
            after_values={"status": "approved"},
        )
    create_audit_log(
        db,
        company_id=user.company_id,
        user_id=user.id,
        performed_by=user.name,
        entity_type="Workflow Request",
        resource_id=approval.id,
        entity_name=TYPE_LABELS[approval.request_type],
        action=AuditAction.WORKFLOW_REQUEST_SUBMITTED,
        request=request,
        description=f"Submitted request APR-{approval.id:06d}",
    )
    _notify(db, approval, event="submitted", recipients=[user.id])
    if not config.approval_required:
        _notify(db, approval, event="approved", recipients=[user.id])
    db.commit()
    db.refresh(approval)
    return _request_payload(db, approval)


def get_pending_approval_count(db: Session, user: User) -> dict[str, int]:
    mine = db.scalar(
        select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.company_id == user.company_id,
            ApprovalRequest.requested_by_id == user.id,
            ApprovalRequest.status.in_(("draft", "pending-approval")),
        )
    ) or 0
    queue_conditions = [
            ApprovalRequest.company_id == user.company_id,
            ApprovalRequest.status == "pending-approval",
            or_(
                ApprovalRequest.approver_role == _role_value(user.role),
                _is_admin(user),
            ),
            or_(
                ApprovalRequest.requested_by_id != user.id,
                exists(
                    select(WorkflowConfiguration.id).where(
                        WorkflowConfiguration.company_id == ApprovalRequest.company_id,
                        WorkflowConfiguration.request_type == ApprovalRequest.request_type,
                        WorkflowConfiguration.allow_self_approval.is_(True),
                    )
                ),
            ),
    ]
    queue = db.scalar(select(func.count(ApprovalRequest.id)).where(*queue_conditions)) or 0
    return {"pendingApprovalCount": queue, "myOpenRequestCount": mine}
