from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

STATUSES = [
    "new",
    "assigned_group",
    "assigned_member",
    "investigating",
    "mitigated",
    "resolved",
    "runbook_pending",
    "runbook_review",
    "closed",
]
ROOT_CAUSE_CATEGORIES = [
    "code_defect",
    "config_change",
    "capacity_resource",
    "upstream_dependency",
    "infrastructure_failure",
    "data_issue",
    "deployment_issue",
    "security",
    "human_error",
    "unknown",
]


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    role: Mapped[str] = mapped_column(String(32), default="user")  # user|prod_support|sre|admin
    memberships: Mapped[list["TeamMember"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    dl_email: Mapped[str] = mapped_column(String(255))
    members: Mapped[list["TeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    team: Mapped[Team] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class OnCallShift(Base):
    __tablename__ = "oncall_shifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    level: Mapped[str] = mapped_column(String(16), default="primary")  # primary|secondary
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[int] = mapped_column(Integer, default=3)  # 1 (critical) .. 4 (low)
    service: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    caller_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assignment_group_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, default=list)  # frozen telemetry snapshots / links
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    caller: Mapped[User] = relationship(foreign_keys=[caller_id])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    assignment_group: Mapped[Team | None] = relationship()
    updates: Mapped[list["IncidentUpdate"]] = relationship(
        back_populates="incident", order_by="IncidentUpdate.id", cascade="all, delete-orphan"
    )
    runbook: Mapped["Runbook | None"] = relationship(back_populates="incident", uselist=False, cascade="all, delete-orphan")

    @property
    def number(self) -> str:
        return f"INC{self.id:07d}"


class IncidentUpdate(Base):
    __tablename__ = "incident_updates"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(24), default="note")  # note|status|assign|runbook|system
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    incident: Mapped[Incident] = relationship(back_populates="updates")
    author: Mapped[User | None] = relationship()


class Runbook(Base):
    __tablename__ = "runbooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|in_review|approved|rejected
    summary: Mapped[str] = mapped_column(Text, default="")
    impact: Mapped[str] = mapped_column(Text, default="")
    detection: Mapped[str] = mapped_column(Text, default="")
    root_cause_category: Mapped[str] = mapped_column(String(48), default="")
    root_cause: Mapped[str] = mapped_column(Text, default="")
    trigger: Mapped[str] = mapped_column(Text, default="")
    contributing_factors: Mapped[str] = mapped_column(Text, default="")
    mitigation: Mapped[str] = mapped_column(Text, default="")
    permanent_fix: Mapped[str] = mapped_column(Text, default="")
    prevention_actions: Mapped[str] = mapped_column(Text, default="")
    evidence_links: Mapped[str] = mapped_column(Text, default="")
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_comment: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    incident: Mapped[Incident] = relationship(back_populates="runbook")


RUNBOOK_REQUIRED = [
    "summary",
    "impact",
    "detection",
    "root_cause_category",
    "root_cause",
    "trigger",
    "mitigation",
    "permanent_fix",
    "prevention_actions",
]
