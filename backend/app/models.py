from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Boolean, DateTime, Float, ForeignKey, Text, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now)


class Family(Base):
    __tablename__ = "families"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120), default="Minha Família")
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now)


class FamilyMember(Base):
    __tablename__ = "family_members"
    __table_args__ = (UniqueConstraint("family_id", "user_id", name="uq_family_user"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # guardian | dependent
    display_name: Mapped[str] = mapped_column(String(120))
    location_sharing_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now)


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(20), default="dependent")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    family_member_id: Mapped[str] = mapped_column(ForeignKey("family_members.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(20))
    device_name: Mapped[str] = mapped_column(String(120))
    push_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    offline_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    push_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    battery_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    permission_location: Mapped[str] = mapped_column(String(30), default="unknown")
    permission_background: Mapped[str] = mapped_column(String(30), default="unknown")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now, index=True)


class Geofence(Base):
    __tablename__ = "geofences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[float] = mapped_column(Float, default=300)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class GeofenceState(Base):
    __tablename__ = "geofence_states"
    __table_args__ = (UniqueConstraint("geofence_id", "device_id", name="uq_geofence_device"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    geofence_id: Mapped[str] = mapped_column(ForeignKey("geofences.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    inside: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    family_member_id: Mapped[str | None] = mapped_column(ForeignKey("family_members.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class Emergency(Base):
    __tablename__ = "emergencies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    family_id: Mapped[str] = mapped_column(ForeignKey("families.id", ondelete="CASCADE"), index=True)
    family_member_id: Mapped[str] = mapped_column(ForeignKey("family_members.id", ondelete="CASCADE"), index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now)


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    family_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(50), default="push")
    status: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now)


class AppVersion(Base):
    __tablename__ = "app_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    platform: Mapped[str] = mapped_column(String(20), index=True)
    version: Mapped[str] = mapped_column(String(40))
    build_number: Mapped[int] = mapped_column(Integer)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    store_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scope: Mapped[str] = mapped_column(String(16), default="mobile")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
