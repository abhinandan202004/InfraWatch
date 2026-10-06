from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth / users ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1)
    password: str = Field(min_length=6)


class GoogleIn(BaseModel):
    id_token: str


class UserOut(ORM):
    id: int
    email: str
    name: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    user: UserOut


# ---------- teams ----------
class MemberOut(ORM):
    user: UserOut
    is_lead: bool


class TeamOut(ORM):
    id: int
    name: str
    dl_email: str
    members: list[MemberOut] = []


class TeamIn(BaseModel):
    name: str
    dl_email: EmailStr


class MemberIn(BaseModel):
    user_id: int
    is_lead: bool = False


class OnCallIn(BaseModel):
    user_id: int
    level: str = "primary"
    start: datetime
    end: datetime


class OnCallOut(ORM):
    id: int
    team_id: int
    level: str
    start: datetime
    end: datetime
    user: UserOut


# ---------- incidents ----------
class IncidentIn(BaseModel):
    title: str = Field(min_length=3)
    description: str = ""
    severity: int = Field(default=3, ge=1, le=4)
    service: str = ""
    assignment_group_id: int
    evidence: list[dict] = []


class UpdateOut(ORM):
    id: int
    kind: str
    body: str
    created_at: datetime
    author: UserOut | None = None


class RunbookIn(BaseModel):
    summary: str = ""
    impact: str = ""
    detection: str = ""
    root_cause_category: str = ""
    root_cause: str = ""
    trigger: str = ""
    contributing_factors: str = ""
    mitigation: str = ""
    permanent_fix: str = ""
    prevention_actions: str = ""
    evidence_links: str = ""


class RunbookOut(RunbookIn, ORM):
    id: int
    status: str
    review_comment: str = ""
    reviewer: UserOut | None = None


class IncidentOut(ORM):
    id: int
    number: str
    title: str
    description: str
    severity: int
    service: str
    status: str
    caller: UserOut
    assignment_group: TeamOut | None = None
    assignee: UserOut | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class IncidentDetail(IncidentOut):
    evidence: list[dict] = []
    updates: list[UpdateOut] = []
    runbook: RunbookOut | None = None
    can_update: bool = False
    can_close: bool = False


class AssignIn(BaseModel):
    group_id: int | None = None
    assignee_id: int | None = None
    note: str = ""


class StatusIn(BaseModel):
    status: str
    note: str = ""


class NoteIn(BaseModel):
    body: str = Field(min_length=1)


class ReviewIn(BaseModel):
    approve: bool
    comment: str = ""
