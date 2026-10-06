export type User = { id: number; email: string; name: string; role: string };
export type Member = { user: User; is_lead: boolean };
export type Team = { id: number; name: string; dl_email: string; members: Member[] };
export type Update = { id: number; kind: string; body: string; created_at: string; author: User | null };
export type Runbook = {
  id: number; status: string; review_comment: string; reviewer: User | null;
  summary: string; impact: string; detection: string; root_cause_category: string; root_cause: string;
  trigger: string; contributing_factors: string; mitigation: string; permanent_fix: string;
  prevention_actions: string; evidence_links: string;
};
export type Incident = {
  id: number; number: string; title: string; description: string; severity: number; service: string;
  status: string; caller: User; assignment_group: Team | null; assignee: User | null;
  created_at: string; updated_at: string; closed_at: string | null;
};
export type IncidentDetail = Incident & {
  evidence: Record<string, unknown>[]; updates: Update[]; runbook: Runbook | null;
  can_update: boolean; can_close: boolean;
};
export type OnCall = { id: number; team_id: number; level: string; start: string; end: string; user: User };

export const STATUSES = [
  "new", "assigned_group", "assigned_member", "investigating", "mitigated",
  "resolved", "runbook_pending", "runbook_review", "closed",
];
export const STATUS_LABEL: Record<string, string> = {
  new: "New", assigned_group: "Assigned to Group", assigned_member: "Assigned to Member",
  investigating: "Investigating", mitigated: "Mitigated", resolved: "Resolved",
  runbook_pending: "Runbook Pending", runbook_review: "Runbook Review", closed: "Closed",
};
export const RC_CATEGORIES = [
  "code_defect", "config_change", "capacity_resource", "upstream_dependency", "infrastructure_failure",
  "data_issue", "deployment_issue", "security", "human_error", "unknown",
];

const KEY = "infrawatch_token";
export const getToken = () => localStorage.getItem(KEY);
export const setToken = (t: string | null) => (t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY));

export async function api<T>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: opts.method || (opts.body ? "POST" : "GET"),
    headers: { "Content-Type": "application/json", ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}) },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401 && !path.startsWith("/auth/")) {
    setToken(null);
    window.location.href = "/login";
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  return res.json();
}
