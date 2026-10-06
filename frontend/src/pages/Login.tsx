import { useEffect, useRef, useState } from "react";
import { api, setToken, User } from "../api";

declare global {
  interface Window { google?: any }
}

type TokenOut = { access_token: string; user: User };

export default function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [email, setEmail] = useState("support1@infrawatch.local");
  const [password, setPassword] = useState("password123");
  const [name, setName] = useState("");
  const [register, setRegister] = useState(false);
  const [err, setErr] = useState("");
  const gbtn = useRef<HTMLDivElement>(null);

  const done = (t: TokenOut) => { setToken(t.access_token); onLogin(t.user); };

  useEffect(() => {
    api<{ google_client_id: string }>("/auth/config").then(({ google_client_id }) => {
      if (!google_client_id) return;
      const init = () => {
        if (!window.google || !gbtn.current) return false;
        window.google.accounts.id.initialize({
          client_id: google_client_id,
          callback: (r: { credential: string }) =>
            api<TokenOut>("/auth/google", { body: { id_token: r.credential } }).then(done).catch((e) => setErr(e.message)),
        });
        window.google.accounts.id.renderButton(gbtn.current, { theme: "filled_blue", size: "large", width: 300 });
        return true;
      };
      if (!init()) { const i = setInterval(() => init() && clearInterval(i), 300); setTimeout(() => clearInterval(i), 10000); }
    }).catch(() => {});
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    try {
      done(await api<TokenOut>(register ? "/auth/register" : "/auth/login", { body: register ? { email, password, name } : { email, password } }));
    } catch (e: any) { setErr(e.message); }
  };

  return (
    <div className="login card">
      <h1>Infra<span style={{ color: "var(--acc)" }}>Watch</span></h1>
      <p className="muted">Observability + incident management</p>
      <form onSubmit={submit}>
        {register && (<><label>Name</label><input value={name} onChange={(e) => setName(e.target.value)} required /></>)}
        <label>Email</label><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label>Password</label><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {err && <div className="err">{err}</div>}
        <div className="row" style={{ marginTop: 14 }}>
          <button type="submit">{register ? "Create account" : "Sign in"}</button>
          <a href="#" onClick={(e) => { e.preventDefault(); setRegister(!register); }}>{register ? "Have an account?" : "Register"}</a>
        </div>
      </form>
      <div ref={gbtn} style={{ marginTop: 18 }} />
      <p className="muted" style={{ fontSize: 12, marginTop: 18 }}>
        Demo users (password <code>password123</code>): support1@, dev1@, sre1@, admin@ <code>infrawatch.local</code>
      </p>
    </div>
  );
}
