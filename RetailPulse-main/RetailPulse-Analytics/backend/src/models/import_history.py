import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ImportType(str, enum.Enum):
    PRODUCTS = "products"
    INVENTORY = "inventory"
    CUSTOMERS = "customers"
    SALES = "sales"


class ImportStatus(str, enum.Enum):
    UPLOADED = "Uploaded"
    VALIDATING = "Validating"
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    COMPLETED_WITH_ERRORS = "Completed with Errors"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class ImportHistory(Base):
    __tablename__ = "import_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    import_type: Mapped[str] = mapped_column(String(40), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=ImportStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company = relationship("Company", back_populates="import_history")
    uploader = relationship("User")
    errors = relationship("ImportErrorRecord", back_populates="import_history", cascade="all, delete-orphan")
    job = relationship("ImportJob", back_populates="import_history", uselist=False, cascade="all, delete-orphan")


class ImportJob(Base):
    __tablename__ = "import_jobs"

    import_id: Mapped[int] = mapped_column(ForeignKey("import_history.id"), primary_key=True)
    source_data: Mapped[str] = mapped_column(Text, nullable=False)
    processed_ids: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    processed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    import_history = relationship("ImportHistory", back_populates="job")


class ImportErrorRecord(Base):
    __tablename__ = "import_error_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("import_history.id"), nullable=False, index=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    row_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    import_history = relationship("ImportHistory", back_populates="errors")
