from datetime import timedelta

from sqlalchemy.orm import Session

from .models import OnCallShift, Team, TeamMember, User, utcnow
from .security import hash_password

DEMO_PASSWORD = "password123"


def seed(db: Session) -> None:
    """Demo data on first run only."""
    if db.query(User).count():
        return

    def user(email, name, role):
        u = User(email=email, name=name, role=role, password_hash=hash_password(DEMO_PASSWORD))
        db.add(u)
        return u

    admin = user("admin@infrawatch.dev", "Admin", "admin")
    ps1 = user("support1@infrawatch.dev", "Priya (Prod Support)", "prod_support")
    ps2 = user("support2@infrawatch.dev", "Sam (Prod Support)", "prod_support")
    sre = user("sre1@infrawatch.dev", "Sara (SRE)", "sre")
    dev1 = user("dev1@infrawatch.dev", "Dev One (Payments)", "user")
    dev2 = user("dev2@infrawatch.dev", "Dev Two (Payments)", "user")
    dev3 = user("dev3@infrawatch.dev", "Dev Three (Platform)", "user")

    teams = {
        "Production Support": Team(name="Production Support", dl_email="prod-support@infrawatch.dev"),
        "SRE": Team(name="SRE", dl_email="sre@infrawatch.dev"),
        "Payments Dev": Team(name="Payments Dev", dl_email="payments-dev@infrawatch.dev"),
        "Platform Dev": Team(name="Platform Dev", dl_email="platform-dev@infrawatch.dev"),
    }
    db.add_all(teams.values())
    db.flush()

    def member(team, u, lead=False):
        db.add(TeamMember(team_id=teams[team].id, user_id=u.id, is_lead=lead))

    member("Production Support", ps1, True)
    member("Production Support", ps2)
    member("SRE", sre, True)
    member("Payments Dev", dev1, True)
    member("Payments Dev", dev2)
    member("Platform Dev", dev3, True)

    now = utcnow()
    db.add(OnCallShift(team_id=teams["Payments Dev"].id, user_id=dev1.id, level="primary",
                       start=now - timedelta(days=1), end=now + timedelta(days=6)))
    db.add(OnCallShift(team_id=teams["Payments Dev"].id, user_id=dev2.id, level="secondary",
                       start=now - timedelta(days=1), end=now + timedelta(days=6)))
    db.add(OnCallShift(team_id=teams["SRE"].id, user_id=sre.id, level="primary",
                       start=now - timedelta(days=1), end=now + timedelta(days=6)))
    db.commit()
