import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class WatchedFolder(Base):
    __tablename__ = "watched_folders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    host_path: Mapped[str] = mapped_column(Text, nullable=False)
    dest_subdir: Mapped[str] = mapped_column(Text, nullable=False)
    recursive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])


class ProcessedFile(Base):
    __tablename__ = "processed_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    folder_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("watched_folders.id"), nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    dest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        UniqueConstraint("owner_id", "source_path", "content_hash", name="uq_owner_path_hash"),
    )

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    folder: Mapped["WatchedFolder"] = relationship("WatchedFolder", foreign_keys=[folder_id])


class SyncState(Base):
    """Singleton row (id=1) holding the last sync result — survives restarts."""
    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scan_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
