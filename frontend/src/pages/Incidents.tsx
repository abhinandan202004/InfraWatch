import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Incident, STATUS_LABEL, Team, User } from "../api";

export const SevBadge = ({ s }: { s: number }) => <span className={`badge sev${s}`}>Sev{s}</span>;

export default function Incidents({ user }: { user: User }) {
  const nav = useNavigate();
  const [rows, setRows] = useState<Incident[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [filter, setFilter] = useState("open");
  const [mine, setMine] = useState(false);
  const [q, setQ] = useState("");
  const [show, setShow] = useState(false);
  const [err, setErr] = useState("");
  const [f, setF] = useState({ title: "", description: "", service: "", severity: 3, assignment_group_id: 0, evidence: "" });

  const load = () => {
    const p = new URLSearchParams();
    if (filter) p.set("status", filter);
    if (mine) p.set("mine", "true");
    if (q) p.set("q", q);
    api<Incident[]>(`/incidents?${p}`).then(setRows).catch((e) => setErr(e.message));
  };
  useEffect(load, [filter, mine]);
  useEffect(() => { api<Team[]>("/teams").then((t) => { setTeams(t); setF((x) => ({ ...x, assignment_group_id: t.find((a) => a.name === "Payments Dev")?.id ?? t[0]?.id ?? 0 })); }); }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    try {
      const evidence = f.evidence.trim() ? [{ type: "note", text: f.evidence, attached_by: user.name, at: new Date().toISOString() }] : [];
      const inc = await api<Incident>("/incidents", { body: { ...f, severity: Number(f.severity), evidence } });
      nav(`/incidents/${inc.id}`);
    } catch (e: any) { setErr(e.message); }
  };

  return (
    <>
      <div className="row"><h1 className="grow">Incidents</h1><button onClick={() => setShow(!show)}>{show ? "Cancel" : "+ New incident"}</button></div>
      {err && <div className="err">{err}</div>}
      {show && (
        <form className="card" onSubmit={create} style={{ marginBottom: 16 }}>
          <div className="row">
            <div className="grow"><label>Title</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} required /></div>
            <div style={{ width: 200 }}><label>Service</label><input value={f.service} onChange={(e) => setF({ ...f, service: e.target.value })} placeholder="payments-api" /></div>
            <div style={{ width: 150 }}><label>Severity</label>
              <select value={f.severity} onChange={(e) => setF({ ...f, severity: Number(e.target.value) })}>
                <option value={1}>1 - Critical</option><option value={2}>2 - High</option><option value={3}>3 - Medium</option><option value={4}>4 - Low</option>
              </select></div>
            <div style={{ width: 220 }}><label>Assignment group</label>
              <select value={f.assignment_group_id} onChange={(e) => setF({ ...f, assignment_group_id: Number(e.target.value) })}>
                {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select></div>
          </div>
          <label>Description</label><textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
          <label>Evidence / observability notes (graphs, logs, links — live telemetry attach arrives in Phase 2)</label>
          <textarea value={f.evidence} onChange={(e) => setF({ ...f, evidence: e.target.value })} />
          <div style={{ marginTop: 12 }}><button type="submit">Create &amp; notify group</button></div>
        </form>
      )}
      <div className="row" style={{ marginBottom: 12 }}>
        <select style={{ width: 190 }} value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="open">Open</option><option value="">All</option>
          {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <label style={{ margin: 0 }}><input type="checkbox" style={{ width: "auto" }} checked={mine} onChange={(e) => setMine(e.target.checked)} /> Mine / my groups</label>
        <input style={{ width: 260 }} placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} />
        <button className="sec" onClick={load}>Search</button>
      </div>
      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead><tr><th>Number</th><th>Title</th><th>Sev</th><th>Status</th><th>Group</th><th>Assignee</th><th>Caller</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="click" onClick={() => nav(`/incidents/${r.id}`)}>
                <td>{r.number}</td><td>{r.title}<div className="muted">{r.service}</div></td><td><SevBadge s={r.severity} /></td>
                <td><span className="badge">{STATUS_LABEL[r.status]}</span></td>
                <td>{r.assignment_group?.name}</td><td>{r.assignee?.name ?? "—"}</td><td>{r.caller.name}</td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={7} className="muted">No incidents</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
