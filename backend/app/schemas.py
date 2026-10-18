from datetime import datetime
from pydantic import BaseModel as PydanticBaseModel, EmailStr, Field, ConfigDict
from typing import Literal

class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    refresh_token: str
    expires_in: int = 900
    access_token: str
    token_type: str = "bearer"


class FamilyCreate(BaseModel):
    name: str = Field(default="Minha Família", min_length=2, max_length=120)


class InviteCreate(BaseModel):
    role: Literal["guardian", "dependent"] = "dependent"


class InviteJoin(BaseModel):
    code: str = Field(min_length=6, max_length=32)
    display_name: str = Field(min_length=2, max_length=120)


class DeviceCreate(BaseModel):
    member_id: str
    platform: Literal["android", "ios"]
    device_name: str = Field(min_length=1, max_length=120)
    push_token: str | None = None
    app_version: str | None = None
    os_version: str | None = None


class PushTokenUpdate(BaseModel):
    push_token: str | None = None
    app_version: str | None = None
    os_version: str | None = None


class PermissionUpdate(BaseModel):
    location: Literal["authorized", "denied", "unknown"]
    background: Literal["authorized", "limited", "off", "denied", "unknown"]
    sharing_enabled: bool


class LocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    speed_mps: float | None = None
    battery_percent: int | None = Field(default=None, ge=0, le=100)
    source_mode: str | None = Field(default=None, max_length=20)
    captured_at: datetime | None = None


class GeofenceCreate(BaseModel):
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: float = Field(default=300, ge=50, le=5000)


class SOSIn(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class AppVersionCreate(BaseModel):
    platform: str = Field(pattern="^(android|ios)$")
    version: str = Field(min_length=1, max_length=40)
    build_number: int = Field(ge=1)
    required: bool = False
    store_url: str | None = None
    notes: str | None = None
