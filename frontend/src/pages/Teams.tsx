import { useEffect, useState } from "react";
import { api, OnCall, Team, User } from "../api";

function toIso(local: string) { return new Date(local).toISOString(); }
const localNow = (addDays = 0) => {
  const d = new Date(Date.now() + addDays * 864e5 - new Date().getTimezoneOffset() * 6e4);
  return d.toISOString().slice(0, 16);
};

function TeamCard({ team, user, reload }: { team: Team; user: User; reload: () => void }) {
  const [shifts, setShifts] = useState<OnCall[]>([]);
  const [f, setF] = useState({ user_id: 0, level: "primary", start: localNow(), end: localNow(7) });
  const [err, setErr] = useState("");
  const canEdit = user.role === "admin" || user.role === "sre" || team.members.some((m) => m.user.id === user.id);

  const load = () => api<OnCall[]>(`/teams/${team.id}/oncall`).then(setShifts);
  useEffect(() => { load(); }, [team.id]);
  useEffect(() => { if (!f.user_id && team.members[0]) setF((x) => ({ ...x, user_id: team.members[0].user.id })); }, [team]);

  const add = async () => {
    setErr("");
    try { await api(`/teams/${team.id}/oncall`, { body: { ...f, user_id: Number(f.user_id), start: toIso(f.start), end: toIso(f.end) } }); load(); }
    catch (e: any) { setErr(e.message); }
  };
  const del = async (id: number) => { await api(`/oncall/${id}`, { method: "DELETE" }); load(); };

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="row"><h2 className="grow" style={{ margin: 0 }}>{team.name}</h2><span className="muted">DL: {team.dl_email}</span></div>
      <div style={{ margin: "10px 0" }}>
        {team.members.map((m) => <span key={m.user.id} className="badge" style={{ marginRight: 6 }}>{m.user.name}{m.is_lead ? " ★" : ""}</span>)}
      </div>
      <h2>On-call roster <span className="muted" style={{ fontSize: 12 }}>(CC'd on incident mails to this group)</span></h2>
      <table>
        <thead><tr><th>Level</th><th>Person</th><th>From</th><th>To</th><th /></tr></thead>
        <tbody>
          {shifts.map((s) => (
            <tr key={s.id}><td>{s.level}</td><td>{s.user.name}</td><td>{new Date(s.start).toLocaleString()}</td><td>{new Date(s.end).toLocaleString()}</td>
              <td>{canEdit && <button className="sec" onClick={() => del(s.id)}>Remove</button>}</td></tr>
          ))}
          {!shifts.length && <tr><td colSpan={5} className="muted">No upcoming on-call shifts — devs should add them here.</td></tr>}
        </tbody>
      </table>
      {canEdit && (
        <>
          {err && <div className="err">{err}</div>}
          <div className="row" style={{ marginTop: 10 }}>
            <select style={{ width: 200 }} value={f.user_id} onChange={(e) => setF({ ...f, user_id: Number(e.target.value) })}>
              {team.members.map((m) => <option key={m.user.id} value={m.user.id}>{m.user.name}</option>)}
            </select>
            <select style={{ width: 120 }} value={f.level} onChange={(e) => setF({ ...f, level: e.target.value })}><option>primary</option><option>secondary</option></select>
            <input style={{ width: 200 }} type="datetime-local" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} />
            <input style={{ width: 200 }} type="datetime-local" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} />
            <button onClick={add}>Add shift</button>
          </div>
        </>
      )}
    </div>
  );
}

export default function Teams({ user }: { user: User }) {
  const [teams, setTeams] = useState<Team[]>([]);
  const load = () => api<Team[]>("/teams").then(setTeams);
  useEffect(() => { load(); }, []);
  return (<><h1>Teams &amp; On-call</h1>{teams.map((t) => <TeamCard key={t.id} team={t} user={user} reload={load} />)}</>);
}
