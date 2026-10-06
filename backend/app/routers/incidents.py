from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import integrations, schemas
from ..db import get_db
from ..models import (
    ROOT_CAUSE_CATEGORIES,
    RUNBOOK_REQUIRED,
    Incident,
    IncidentUpdate,
    Runbook,
    Team,
    TeamMember,
    User,
    utcnow,
)
from ..security import current_user
from .teams import active_oncall, is_admin, is_member

router = APIRouter(prefix="/incidents", tags=["incidents"])

SEV = {1: "Sev1-Critical", 2: "Sev2-High", 3: "Sev3-Medium", 4: "Sev4-Low"}
MANUAL_STATUSES = {"investigating", "mitigated", "resolved"}


# ---------------- helpers ----------------
def load(db: Session, inc_id: int) -> Incident:
    inc = (
        db.query(Incident)
        .options(
            joinedload(Incident.caller),
            joinedload(Incident.assignee),
            joinedload(Incident.assignment_group).joinedload(Team.members).joinedload(TeamMember.user),
            joinedload(Incident.updates).joinedload(IncidentUpdate.author),
            joinedload(Incident.runbook),
        )
        .filter(Incident.id == inc_id)
        .first()
    )
    if not inc:
        raise HTTPException(404, "Incident not found")
    return inc


def shares_team(db: Session, a_id: int, b_id: int) -> bool:
    a = {m.team_id for m in db.query(TeamMember).filter_by(user_id=a_id)}
    b = {m.team_id for m in db.query(TeamMember).filter_by(user_id=b_id)}
    return bool(a & b)


def can_update(db: Session, u: User, inc: Incident) -> bool:
    if inc.status == "closed":
        return False
    if is_admin(u) or u.role == "prod_support" or inc.caller_id == u.id:
        return True
    return bool(inc.assignment_group_id and is_member(db, u, inc.assignment_group_id))


def can_close(db: Session, u: User, inc: Incident) -> bool:
    """Caller or anyone in the caller's assignment group, only after runbook approval."""
    if inc.status != "runbook_review" or not inc.runbook or inc.runbook.status != "approved":
        return False
    return inc.caller_id == u.id or shares_team(db, u.id, inc.caller_id)


def require_update(db: Session, u: User, inc: Incident):
    if not can_update(db, u, inc):
        raise HTTPException(403, "You can't update this incident")


def log_update(db: Session, inc: Incident, author: User | None, kind: str, body: str):
    db.add(IncidentUpdate(incident_id=inc.id, author_id=author.id if author else None, kind=kind, body=body))


def after_change(db: Session, bg: BackgroundTasks, inc: Incident, event: str, mail: bool, note: str = ""):
    """Index, publish to Kafka and (optionally) email the group with on-call in CC."""
    db.refresh(inc)
    doc = {
        "number": inc.number, "title": inc.title, "description": inc.description, "service": inc.service,
        "status": inc.status, "severity": inc.severity,
        "root_cause": inc.runbook.root_cause if inc.runbook else "",
    }
    bg.add_task(integrations.index_doc, "incidents", str(inc.id), doc)
    bg.add_task(integrations.publish, f"incident.{event}", inc.number,
                {**doc, "id": inc.id, "event": event, "group_id": inc.assignment_group_id, "ts": utcnow().isoformat()})
    if mail and inc.assignment_group:
        to = [inc.assignment_group.dl_email]
        cc = sorted({s.user.email for s in active_oncall(db, inc.assignment_group_id)})
        if inc.assignee and inc.assignee.email not in cc:
            cc.append(inc.assignee.email)
        subject = f"[{inc.number}] {SEV.get(inc.severity)} - {event.replace('_', ' ')}: {inc.title}"
        body = (
            f"{inc.number}: {inc.title}\nService: {inc.service}\nSeverity: {SEV.get(inc.severity)}\n"
            f"Status: {inc.status}\nCaller: {inc.caller.name}\nGroup: {inc.assignment_group.name}\n"
            f"Assignee: {inc.assignee.name if inc.assignee else '-'}\n\n{note or inc.description}\n"
        )
        bg.add_task(integrations.send_mail, to, cc, subject, body, inc.number)


def detail(db: Session, u: User, inc: Incident) -> schemas.IncidentDetail:
    d = schemas.IncidentDetail.model_validate(inc)
    d.can_update = can_update(db, u, inc)
    d.can_close = can_close(db, u, inc)
    return d


# ---------------- endpoints ----------------
@router.get("", response_model=list[schemas.IncidentOut])
def list_incidents(
    status: str | None = None,
    group_id: int | None = None,
    mine: bool = False,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    query = db.query(Incident).options(
        joinedload(Incident.caller), joinedload(Incident.assignee), joinedload(Incident.assignment_group)
    )
    if status == "open":
        query = query.filter(Incident.status != "closed")
    elif status:
        query = query.filter(Incident.status == status)
    if group_id:
        query = query.filter(Incident.assignment_group_id == group_id)
    if mine:
        team_ids = [m.team_id for m in db.query(TeamMember).filter_by(user_id=user.id)]
        query = query.filter(
            or_(Incident.caller_id == user.id, Incident.assignee_id == user.id, Incident.assignment_group_id.in_(team_ids))
        )
    if q:
        ids = integrations.search_ids("incidents", q)
        if ids is not None:
            query = query.filter(Incident.id.in_([int(i) for i in ids] or [0]))
        else:  # Zinc down -> SQL fallback
            like = f"%{q}%"
            query = query.filter(or_(Incident.title.ilike(like), Incident.description.ilike(like),
                                     Incident.service.ilike(like)))
    return query.order_by(Incident.id.desc()).limit(200).all()


@router.post("", response_model=schemas.IncidentDetail)
def create_incident(body: schemas.IncidentIn, bg: BackgroundTasks, db: Session = Depends(get_db),
                    user: User = Depends(current_user)):
    team = db.get(Team, body.assignment_group_id)
    if not team:
        raise HTTPException(400, "Unknown assignment group")
    inc = Incident(title=body.title, description=body.description, severity=body.severity, service=body.service,
                   caller_id=user.id, assignment_group_id=team.id, status="assigned_group", evidence=body.evidence)
    db.add(inc)
    db.flush()
    log_update(db, inc, user, "system", f"Incident created and assigned to {team.name}")
    db.commit()
    inc = load(db, inc.id)
    after_change(db, bg, inc, "created", mail=True)
    return detail(db, user, inc)


@router.get("/{inc_id}", response_model=schemas.IncidentDetail)
def get_incident(inc_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return detail(db, user, load(db, inc_id))


@router.post("/{inc_id}/assign", response_model=schemas.IncidentDetail)
def assign(inc_id: int, body: schemas.AssignIn, bg: BackgroundTasks, db: Session = Depends(get_db),
           user: User = Depends(current_user)):
    inc = load(db, inc_id)
    require_update(db, user, inc)
    if inc.status in ("runbook_pending", "runbook_review"):
        raise HTTPException(400, "Incident is in runbook phase")
    msgs = []
    if body.group_id and body.group_id != inc.assignment_group_id:
        team = db.get(Team, body.group_id)
        if not team:
            raise HTTPException(400, "Unknown group")
        inc.assignment_group_id = team.id
        inc.assignee_id = None
        inc.status = "assigned_group"
        msgs.append(f"Reassigned to group {team.name}")
    if body.assignee_id:
        if not inc.assignment_group_id or not is_member(db, User(id=body.assignee_id), inc.assignment_group_id):
            raise HTTPException(400, "Assignee must be a member of the assignment group")
        who = db.get(User, body.assignee_id)
        inc.assignee_id = who.id
        if inc.status in ("new", "assigned_group", "assigned_member"):
            inc.status = "assigned_member"
        msgs.append(f"Assigned to {who.name}")
    if not msgs:
        raise HTTPException(400, "Nothing to change")
    text = "; ".join(msgs) + (f" - {body.note}" if body.note else "")
    log_update(db, inc, user, "assign", text)
    db.commit()
    inc = load(db, inc_id)
    after_change(db, bg, inc, "assigned", mail=True, note=text)
    return detail(db, user, inc)


@router.post("/{inc_id}/status", response_model=schemas.IncidentDetail)
def set_status(inc_id: int, body: schemas.StatusIn, bg: BackgroundTasks, db: Session = Depends(get_db),
               user: User = Depends(current_user)):
    inc = load(db, inc_id)
    require_update(db, user, inc)
    if body.status not in MANUAL_STATUSES:
        raise HTTPException(400, f"Status must be one of {sorted(MANUAL_STATUSES)}")
    if inc.status in ("runbook_pending", "runbook_review"):
        raise HTTPException(400, "Incident is in runbook phase; use reopen to go back")
    note = f" - {body.note}" if body.note else ""
    log_update(db, inc, user, "status", f"Status: {inc.status} -> {body.status}{note}")
    inc.status = body.status
    if body.status == "resolved":
        # Resolution always triggers the mandatory runbook; closing is blocked until it is approved.
        if not inc.runbook:
            db.add(Runbook(incident_id=inc.id))
        inc.status = "runbook_pending"
        log_update(db, inc, None, "system", "Resolved. Runbook (RCA) is now required before the incident can be closed.")
    db.commit()
    inc = load(db, inc_id)
    after_change(db, bg, inc, "status_changed", mail=True, note=body.note)
    return detail(db, user, inc)


@router.post("/{inc_id}/reopen", response_model=schemas.IncidentDetail)
def reopen(inc_id: int, bg: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    inc = load(db, inc_id)
    require_update(db, user, inc)
    if inc.status not in ("runbook_pending", "runbook_review"):
        raise HTTPException(400, "Only resolved incidents can be reopened")
    inc.status = "investigating"
    if inc.runbook and inc.runbook.status != "approved":
        inc.runbook.status = "draft"
    log_update(db, inc, user, "status", "Reopened - back to investigating")
    db.commit()
    inc = load(db, inc_id)
    after_change(db, bg, inc, "reopened", mail=True)
    return detail(db, user, inc)


@router.post("/{inc_id}/notes", response_model=schemas.IncidentDetail)
def add_note(inc_id: int, body: schemas.NoteIn, bg: BackgroundTasks, db: Session = Depends(get_db),
             user: User = Depends(current_user)):
    inc = load(db, inc_id)
    require_update(db, user, inc)
    log_update(db, inc, user, "note", body.body)
    db.commit()
    inc = load(db, inc_id)
    after_change(db, bg, inc, "note_added", mail=False)
    return detail(db, user, inc)


# ---------------- runbook ----------------
@router.put("/{inc_id}/runbook", response_model=schemas.IncidentDetail)
def save_runbook(inc_id: int, body: schemas.RunbookIn, submit: bool = False, bg: BackgroundTasks = None,
                 db: Session = Depends(get_db), user: User = Depends(current_user)):
    inc = load(db, inc_id)
    require_update(db, user, inc)
    if inc.status != "runbook_pending" or not inc.runbook:
        raise HTTPException(400, "Runbook can only be edited while the incident is in 'runbook_pending'")
    if body.root_cause_category and body.root_cause_category not in ROOT_CAUSE_CATEGORIES:
        raise HTTPException(400, f"root_cause_category must be one of {ROOT_CAUSE_CATEGORIES}")
    for k, v in body.model_dump().items():
        setattr(inc.runbook, k, v)
    if submit:
        missing = [f for f in RUNBOOK_REQUIRED if not str(getattr(inc.runbook, f)).strip()]
        if missing:
            raise HTTPException(422, f"Runbook incomplete. Missing: {', '.join(missing)}")
        inc.runbook.status = "in_review"
        inc.status = "runbook_review"
        log_update(db, inc, user, "runbook", "Runbook submitted for SRE/lead review")
    db.commit()
    inc = load(db, inc_id)
    after_change(db, bg, inc, "runbook_submitted" if submit else "runbook_saved", mail=submit)
    return detail(db, user, inc)


@router.post("/{inc_id}/runbook/review", response_model=schemas.IncidentDetail)
def review_runbook(inc_id: int, body: schemas.ReviewIn, bg: BackgroundTasks, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    inc = load(db, inc_id)
    is_lead = bool(
        inc.assignment_group_id
        and db.query(TeamMember).filter_by(team_id=inc.assignment_group_id, user_id=user.id, is_lead=True).first()
    )
    if not (is_admin(user) or is_lead):
        raise HTTPException(403, "Only SRE, admin or the group lead can review the runbook")
    if inc.status != "runbook_review" or not inc.runbook or inc.runbook.status != "in_review":
        raise HTTPException(400, "No runbook awaiting review")
    inc.runbook.reviewer_id = user.id
    inc.runbook.review_comment = body.comment
    if body.approve:
        inc.runbook.status = "approved"
        log_update(db, inc, user, "runbook", f"Runbook approved{': ' + body.comment if body.comment else ''}")
    else:
        inc.runbook.status = "rejected"
        inc.status = "runbook_pending"
        log_update(db, inc, user, "runbook", f"Runbook rejected: {body.comment}")
    db.commit()
    inc = load(db, inc_id)
    after_change(db, bg, inc, "runbook_approved" if body.approve else "runbook_rejected", mail=True, note=body.comment)
    return detail(db, user, inc)


@router.post("/{inc_id}/close", response_model=schemas.IncidentDetail)
def close(inc_id: int, bg: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(current_user)):
    inc = load(db, inc_id)
    if inc.status != "runbook_review" or not inc.runbook or inc.runbook.status != "approved":
        raise HTTPException(409, "Incident can only be closed after its runbook is approved")
    if not can_close(db, user, inc):
        raise HTTPException(403, "Only the caller or a member of the caller's group can close this incident")
    inc.status = "closed"
    inc.closed_at = utcnow()
    log_update(db, inc, user, "status", "Incident closed")
    db.commit()
    inc = load(db, inc_id)
    rb = inc.runbook
    after_change(db, bg, inc, "closed", mail=True)
    # Knowledge base: approved runbooks are indexed for search and (later) RAG / model training.
    bg.add_task(integrations.index_doc, "runbooks", str(inc.id), {
        "number": inc.number, "title": inc.title, "service": inc.service, "root_cause_category": rb.root_cause_category,
        "root_cause": rb.root_cause, "mitigation": rb.mitigation, "permanent_fix": rb.permanent_fix,
        "summary": rb.summary,
    })
    bg.add_task(integrations.publish, "runbook.published", inc.number, {"incident_id": inc.id, "number": inc.number})
    return detail(db, user, inc)
