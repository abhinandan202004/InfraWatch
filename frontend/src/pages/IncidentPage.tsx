import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, IncidentDetail, RC_CATEGORIES, Runbook, STATUS_LABEL, STATUSES, Team, User } from "../api";
import { SevBadge } from "./Incidents";

const RB_FIELDS: [keyof Runbook, string, boolean][] = [
  ["summary", "Summary", true], ["impact", "Impact & duration", true], ["detection", "How was it detected (and detection gap)?", true],
  ["root_cause", "Root cause", true], ["trigger", "Trigger", true], ["contributing_factors", "Contributing factors", false],
  ["mitigation", "Mitigation steps", true], ["permanent_fix", "Permanent fix / problem ticket", true],
  ["prevention_actions", "Prevention actions & owners", true], ["evidence_links", "Telemetry evidence links", false],
];

export default function IncidentPage({ user }: { user: User }) {
  const { id } = useParams();
  const [inc, setInc] = useState<IncidentDetail | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [rb, setRb] = useState<Partial<Runbook>>({});
  const [comment, setComment] = useState("");

  const apply = (i: IncidentDetail) => { setInc(i); setRb(i.runbook ?? {}); setErr(""); };
  const load = () => api<IncidentDetail>(`/incidents/${id}`).then(apply).catch((e) => setErr(e.message));
  useEffect(() => { load(); api<Team[]>("/teams").then(setTeams); }, [id]);
  const act = (path: string, body?: unknown, method = "POST") =>
    api<IncidentDetail>(`/incidents/${id}${path}`, { method, body: body ?? {} }).then(apply).catch((e) => setErr(e.message));

  if (!inc) return <>{err ? <div className="err">{err}</div> : <p className="muted">Loading…</p>}</>;

  const group = teams.find((t) => t.id === inc.assignment_group?.id);
  const cur = STATUSES.indexOf(inc.status);
  const isReviewer = user.role === "admin" || user.role === "sre" || !!group?.members.find((m) => m.user.id === user.id && m.is_lead);
  const rbEditable = inc.status === "runbook_pending" && inc.can_update;
  const rbBody = () => ({ ...Object.fromEntries(RB_FIELDS.map(([k]) => [k, (rb[k] as string) ?? ""])), root_cause_category: rb.root_cause_category ?? "" });
  const inRunbookPhase = inc.status === "runbook_pending" || inc.status === "runbook_review";

  return (
    <>
      <div className="row"><h1 className="grow">{inc.number} — {inc.title}</h1><SevBadge s={inc.severity} /></div>
      {err && <div className="err">{err}</div>}
      <div className="bar">
        {STATUSES.map((s, i) => <div key={s} className={`step ${i < cur ? "done" : i === cur ? "cur" : ""}`}>{STATUS_LABEL[s]}</div>)}
      </div>

      <div className="grid2">
        <div>
          <div className="card">
            <div className="kv">
              <div>Service</div><div>{inc.service || "—"}</div>
              <div>Caller</div><div>{inc.caller.name}</div>
              <div>Group</div><div>{inc.assignment_group?.name}</div>
              <div>Assignee</div><div>{inc.assignee?.name ?? "—"}</div>
            </div>
            <h2>Description</h2><div style={{ whiteSpace: "pre-wrap" }}>{inc.description || "—"}</div>
            {inc.evidence.length > 0 && (<><h2>Evidence</h2>{inc.evidence.map((e, i) => <pre key={i} className="muted" style={{ whiteSpace: "pre-wrap", margin: "4px 0" }}>{JSON.stringify(e, null, 1)}</pre>)}</>)}
          </div>

          {(inc.runbook || inRunbookPhase) && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="row"><h2 className="grow" style={{ margin: 0 }}>Runbook / RCA</h2><span className="badge">{inc.runbook?.status ?? "draft"}</span></div>
              {inc.runbook?.status === "rejected" && <div className="err">Rejected: {inc.runbook.review_comment}</div>}
              <label>Root cause category</label>
              <select disabled={!rbEditable} value={rb.root_cause_category ?? ""} onChange={(e) => setRb({ ...rb, root_cause_category: e.target.value })}>
                <option value="">— select —</option>{RC_CATEGORIES.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
              </select>
              {RB_FIELDS.map(([k, label, req]) => (
                <div key={k}><label>{label}{req && " *"}</label>
                  <textarea disabled={!rbEditable} value={(rb[k] as string) ?? ""} onChange={(e) => setRb({ ...rb, [k]: e.target.value })} /></div>
              ))}
              {rbEditable && (
                <div className="row" style={{ marginTop: 12 }}>
                  <button className="sec" onClick={() => act("/runbook", rbBody(), "PUT")}>Save draft</button>
                  <button onClick={() => act("/runbook?submit=true", rbBody(), "PUT")}>Submit for review</button>
                </div>
              )}
              {inc.status === "runbook_review" && inc.runbook?.status === "in_review" && isReviewer && (
                <div style={{ marginTop: 12 }}>
                  <label>Review comment</label><textarea value={comment} onChange={(e) => setComment(e.target.value)} />
                  <div className="row" style={{ marginTop: 8 }}>
                    <button className="ok" onClick={() => act("/runbook/review", { approve: true, comment })}>Approve</button>
                    <button className="bad" onClick={() => act("/runbook/review", { approve: false, comment })}>Reject</button>
                  </div>
                </div>
              )}
              {inc.runbook?.status === "approved" && inc.status !== "closed" && (
                <div style={{ marginTop: 12 }}>
                  <button className="ok" disabled={!inc.can_close} onClick={() => act("/close")}>Close incident</button>
                  {!inc.can_close && <span className="muted"> &nbsp;Only the caller or someone in the caller's group can close.</span>}
                </div>
              )}
            </div>
          )}
        </div>

        <div>
          {inc.can_update && inc.status !== "closed" && (
            <div className="card">
              <h2 style={{ marginTop: 0 }}>Actions</h2>
              {!inRunbookPhase && (<>
                <label>Group</label>
                <select value={inc.assignment_group?.id ?? ""} onChange={(e) => act("/assign", { group_id: Number(e.target.value) })}>
                  {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
                <label>Assign to member</label>
                <select value={inc.assignee?.id ?? ""} onChange={(e) => e.target.value && act("/assign", { assignee_id: Number(e.target.value) })}>
                  <option value="">— unassigned —</option>
                  {group?.members.map((m) => <option key={m.user.id} value={m.user.id}>{m.user.name}</option>)}
                </select>
                <label>Update status</label>
                <div className="row">
                  {["investigating", "mitigated", "resolved"].map((s) => <button key={s} className="sec" onClick={() => act("/status", { status: s })}>{STATUS_LABEL[s]}</button>)}
                </div>
              </>)}
              {inRunbookPhase && <button className="sec" onClick={() => act("/reopen")}>Reopen</button>}
              <label>Add update</label>
              <textarea value={note} onChange={(e) => setNote(e.target.value)} />
              <div style={{ marginTop: 8 }}><button disabled={!note.trim()} onClick={() => act("/notes", { body: note }).then(() => setNote(""))}>Post</button></div>
            </div>
          )}
          <div className="card" style={{ marginTop: 16 }}>
            <h2 style={{ marginTop: 0 }}>Timeline</h2>
            <div className="tl">
              {[...inc.updates].reverse().map((u) => (
                <div key={u.id} className={`it ${u.kind}`}>
                  <div style={{ whiteSpace: "pre-wrap" }}>{u.body}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{u.author?.name ?? "system"} · {new Date(u.created_at).toLocaleString()}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
