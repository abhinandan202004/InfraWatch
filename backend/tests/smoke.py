"""End-to-end lifecycle test against an in-process app (SQLite, no external services).
Run:  python -m tests.smoke   (from backend/)
"""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/t.db"
os.environ["KAFKA_ENABLED"] = "false"
os.environ["SMTP_PORT"] = "1"  # nothing listening -> mail fails quietly

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def login(c, email):
    r = c.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


with TestClient(app) as c:
    ps = login(c, "support1@infrawatch.dev")
    ps2 = login(c, "support2@infrawatch.dev")
    dev = login(c, "dev1@infrawatch.dev")
    sre = login(c, "sre1@infrawatch.dev")
    dev_outsider = login(c, "dev3@infrawatch.dev")

    teams = {t["name"]: t for t in c.get("/api/teams", headers=ps).json()}
    pay = teams["Payments Dev"]
    users = {u["email"]: u for u in c.get("/api/users", headers=ps).json()}

    r = c.post("/api/incidents", headers=ps, json={
        "title": "Checkout latency high", "description": "p95 > 5s", "severity": 2,
        "service": "payments-api", "assignment_group_id": pay["id"],
        "evidence": [{"type": "metric", "query": "cpu", "note": "CPU 95%"}]})
    assert r.status_code == 200, r.text
    inc = r.json(); iid = inc["id"]
    assert inc["number"] == "INC0000001" and inc["status"] == "assigned_group"

    # assignee must be in group
    r = c.post(f"/api/incidents/{iid}/assign", headers=dev, json={"assignee_id": users["dev3@infrawatch.dev"]["id"]})
    assert r.status_code == 400
    r = c.post(f"/api/incidents/{iid}/assign", headers=dev, json={"assignee_id": users["dev2@infrawatch.dev"]["id"]})
    assert r.json()["status"] == "assigned_member"

    # outsider cannot update
    assert c.post(f"/api/incidents/{iid}/notes", headers=dev_outsider, json={"body": "x"}).status_code == 403

    assert c.post(f"/api/incidents/{iid}/status", headers=dev, json={"status": "investigating"}).json()["status"] == "investigating"
    assert c.post(f"/api/incidents/{iid}/notes", headers=sre, json={"body": "Looks like a bad deploy"}).status_code == 200
    assert c.post(f"/api/incidents/{iid}/status", headers=dev, json={"status": "mitigated"}).status_code == 200

    # resolve -> runbook gate
    r = c.post(f"/api/incidents/{iid}/status", headers=dev, json={"status": "resolved"})
    assert r.json()["status"] == "runbook_pending" and r.json()["runbook"]["status"] == "draft"

    # cannot close yet
    assert c.post(f"/api/incidents/{iid}/close", headers=ps).status_code == 409

    # incomplete runbook rejected
    assert c.put(f"/api/incidents/{iid}/runbook?submit=true", headers=dev, json={"summary": "x"}).status_code == 422
    rb = {"summary": "Bad deploy", "impact": "Checkout slow 30m", "detection": "Alert + user report",
          "root_cause_category": "deployment_issue", "root_cause": "N+1 query in v1.4.2", "trigger": "Deploy at 10:02",
          "mitigation": "Rolled back", "permanent_fix": "Add query test", "prevention_actions": "Canary deploys"}
    r = c.put(f"/api/incidents/{iid}/runbook?submit=true", headers=dev, json=rb)
    assert r.status_code == 200 and r.json()["status"] == "runbook_review", r.text

    # plain dev cannot review (not lead? dev1 IS lead of Payments) -> use dev2 path: outsider
    assert c.post(f"/api/incidents/{iid}/runbook/review", headers=dev_outsider, json={"approve": True}).status_code == 403
    # reject then resubmit
    assert c.post(f"/api/incidents/{iid}/runbook/review", headers=sre, json={"approve": False, "comment": "more detail"}).json()["status"] == "runbook_pending"
    assert c.put(f"/api/incidents/{iid}/runbook?submit=true", headers=dev, json=rb).status_code == 200
    r = c.post(f"/api/incidents/{iid}/runbook/review", headers=sre, json={"approve": True, "comment": "good"})
    assert r.json()["runbook"]["status"] == "approved" and r.json()["status"] == "runbook_review"

    # close: dev (not caller group) forbidden; other prod support (caller's group) allowed
    assert c.post(f"/api/incidents/{iid}/close", headers=dev).status_code == 403
    r = c.post(f"/api/incidents/{iid}/close", headers=ps2)
    assert r.status_code == 200 and r.json()["status"] == "closed", r.text

    # list + search (Zinc down -> SQL fallback)
    assert len(c.get("/api/incidents?q=checkout", headers=ps).json()) == 1
    # on-call
    assert len(c.get(f"/api/teams/{pay['id']}/oncall", headers=ps).json()) == 2
print("ALL SMOKE TESTS PASSED")
