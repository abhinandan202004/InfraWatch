import { useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { api, getToken, setToken, User } from "./api";
import IncidentPage from "./pages/IncidentPage";
import Incidents from "./pages/Incidents";
import Login from "./pages/Login";
import Teams from "./pages/Teams";

function Shell({ user }: { user: User }) {
  const nav = useNavigate();
  return (
    <>
      <header className="top">
        <div className="logo">Infra<span>Watch</span></div>
        <nav>
          <NavLink to="/incidents">Incidents</NavLink>
          <NavLink to="/teams">Teams &amp; On-call</NavLink>
        </nav>
        <span className="muted">{user.name} · {user.role}</span>
        <button className="sec" onClick={() => { setToken(null); nav("/login"); }}>Sign out</button>
      </header>
      <main>
        <Routes>
          <Route path="/incidents" element={<Incidents user={user} />} />
          <Route path="/incidents/:id" element={<IncidentPage user={user} />} />
          <Route path="/teams" element={<Teams user={user} />} />
          <Route path="*" element={<Navigate to="/incidents" />} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const nav = useNavigate();

  const loadMe = () =>
    api<User>("/auth/me").then(setUser).catch(() => setUser(null)).finally(() => setReady(true));

  useEffect(() => { if (getToken()) loadMe(); else setReady(true); }, []);

  if (!ready) return null;
  return (
    <Routes>
      <Route path="/login" element={<Login onLogin={(u) => { setUser(u); nav("/incidents"); }} />} />
      <Route path="/*" element={user ? <Shell user={user} /> : <Navigate to="/login" />} />
    </Routes>
  );
}
