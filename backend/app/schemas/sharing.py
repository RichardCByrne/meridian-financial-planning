from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

_ROLE_PATTERN = "^(viewer|editor|owner)$"


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    role: str
    email: str | None = None
    display_name: str | None = None
    created_at: datetime


class MemberRoleUpdate(BaseModel):
    role: str = Field(pattern=_ROLE_PATTERN)


class InviteCreate(BaseModel):
    role: str = Field(pattern=_ROLE_PATTERN)
    email: EmailStr | None = None
    expires_days: int | None = Field(default=30, ge=1, le=365)


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    role: str
    token: str
    email: str | None
    created_at: datetime
    expires_at: datetime | None
    accepted_at: datetime | None
    accepted_by_user_id: int | None


class InvitePreview(BaseModel):
    """Public preview shown on the accept page before the user signs in.

    Deliberately omits the inviter's identity beyond display name — we don't
    leak which Firebase UID created it.
    """

    plan_id: int
    plan_name: str
    role: str
    email_bound: bool
    inviter_display_name: str | None
    expires_at: datetime | None
