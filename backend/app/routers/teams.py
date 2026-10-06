from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import schemas
from ..db import get_db
from ..models import OnCallShift, Team, TeamMember, User
from ..security import current_user

router = APIRouter(tags=["teams"])


def is_admin(u: User) -> bool:
    return u.role in ("admin", "sre")


def is_member(db: Session, u: User, team_id: int) -> bool:
    return db.query(TeamMember).filter_by(team_id=team_id, user_id=u.id).first() is not None


def active_oncall(db: Session, team_id: int, now: datetime | None = None) -> list[OnCallShift]:
    now = now or datetime.now(timezone.utc)
    return (
        db.query(OnCallShift)
        .options(joinedload(OnCallShift.user))
        .filter(OnCallShift.team_id == team_id, OnCallShift.start <= now, OnCallShift.end >= now)
        .all()
    )


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return db.query(User).order_by(User.name).all()


@router.get("/teams", response_model=list[schemas.TeamOut])
def list_teams(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return db.query(Team).options(joinedload(Team.members).joinedload(TeamMember.user)).order_by(Team.name).all()


@router.post("/teams", response_model=schemas.TeamOut)
def create_team(body: schemas.TeamIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not is_admin(user):
        raise HTTPException(403, "Admin/SRE only")
    if db.query(Team).filter(Team.name == body.name).first():
        raise HTTPException(409, "Team exists")
    team = Team(name=body.name, dl_email=body.dl_email)
    db.add(team)
    db.commit()
    return team


@router.post("/teams/{team_id}/members", response_model=schemas.TeamOut)
def add_member(team_id: int, body: schemas.MemberIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    if not (is_admin(user) or is_member(db, user, team_id)):
        raise HTTPException(403, "Not allowed")
    if not db.get(User, body.user_id):
        raise HTTPException(404, "User not found")
    if not is_member(db, User(id=body.user_id), team_id):
        db.add(TeamMember(team_id=team_id, user_id=body.user_id, is_lead=body.is_lead))
        db.commit()
    return db.query(Team).options(joinedload(Team.members).joinedload(TeamMember.user)).get(team_id)


@router.get("/teams/{team_id}/oncall", response_model=list[schemas.OnCallOut])
def list_oncall(team_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    now = datetime.now(timezone.utc)
    return (
        db.query(OnCallShift)
        .options(joinedload(OnCallShift.user))
        .filter(OnCallShift.team_id == team_id, OnCallShift.end >= now)
        .order_by(OnCallShift.start)
        .all()
    )


@router.post("/teams/{team_id}/oncall", response_model=schemas.OnCallOut)
def add_oncall(team_id: int, body: schemas.OnCallIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not (is_admin(user) or is_member(db, user, team_id)):
        raise HTTPException(403, "Only team members can edit the on-call roster")
    if not is_member(db, User(id=body.user_id), team_id):
        raise HTTPException(400, "On-call person must be a member of the team")
    if body.end <= body.start:
        raise HTTPException(400, "end must be after start")
    if body.level not in ("primary", "secondary"):
        raise HTTPException(400, "level must be primary or secondary")
    shift = OnCallShift(team_id=team_id, **body.model_dump())
    db.add(shift)
    db.commit()
    return db.query(OnCallShift).options(joinedload(OnCallShift.user)).get(shift.id)


@router.delete("/oncall/{shift_id}")
def delete_oncall(shift_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    shift = db.get(OnCallShift, shift_id)
    if not shift:
        raise HTTPException(404, "Not found")
    if not (is_admin(user) or is_member(db, user, shift.team_id)):
        raise HTTPException(403, "Not allowed")
    db.delete(shift)
    db.commit()
    return {"ok": True}
