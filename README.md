# InfraWatch 🛡️⚡

**InfraWatch** is an open-source, AI-augmented Observability and IT Service Management (ITSM) platform designed to replace legacy tools like ServiceNow with a streamlined, developer-centric workflow. 

It seamlessly connects **real-time system observability**, **incident management (Tickets, Requests, Changes)**, **on-call rosters**, **strict runbook governance**, and **AI-driven root cause prediction**.

---

## 📐 Architecture & Visual Data Flow

An interactive, self-contained architecture dashboard and process flow diagram is available in [InfraWatch-Architecture.html](file:///c:/Users/ABHI%20N%20P/Downloads/InfraWatch/InfraWatch-Architecture.html).

### View the HTML Architecture:
Simply open `InfraWatch-Architecture.html` in any web browser to explore:
1. **End-to-End Flow:** Step-by-step lifecycle from incident discovery to AI feedback loops.
2. **Technical Architecture:** 8-layer technical stack (Clients, Edge, Core Services, Event Backbone, AI/ML, Data Stores, Collectors, Estate).
3. **Incident Lifecycle:** State machine for status bar progression and close gates.
4. **AI & Data Pipeline:** Staged ML pipeline (RAG → Correlation → RCA Classifier) & additional data sources.
5. **Phase & Decisions:** Confirmed architectural decisions and lean setup roadmap.

---

## 🚀 Key Features & Core Flow

### 1. Common Observability & Telemetry
* Single-pane-of-glass monitoring for CPU, memory, disk, network, latency, error rates, logs, and traces using **OpenTelemetry**.
* Unified dashboards accessible to all users, engineers, and production support teams.

### 2. Triage & Evidence Snapshots
* Production Support or users spot issues and report incidents directly in the app.
* **Telemetry Evidence Frozen in Time:** Support teams attach live metric graphs, log snippets, and trace IDs to the incident. InfraWatch freezes and snapshots this telemetry into object storage so training context is preserved beyond live TSDB retention.

### 3. Smart Notifications & On-Call Routing
* **Group Mail:** Incidents automatically trigger email notifications sent to the designated Assignment Group Distribution List (DL).
* **Dynamic On-Call CC:** Developers and SREs manage their on-call rosters directly within InfraWatch. The system resolves the current primary/secondary on-call personnel at send-time and automatically includes them in **CC**.
* **Threaded Updates:** Email notifications use strict threading headers (`Message-ID` / `In-Reply-To`) so replies can be automatically ingested into the incident timeline.

### 4. Shared Real-Time Status Bar
* Live status bar visible across the app for all participating teams:
  $$\text{New} \longrightarrow \text{Assigned} \longrightarrow \text{Investigating} \longrightarrow \text{Mitigated} \longrightarrow \text{Resolved} \longrightarrow \text{Runbook Pending} \longrightarrow \text{Runbook Review} \longrightarrow \text{Closed}$$
* Intra-team task assignment: Each group assigns work to specific team members without cross-group friction.
* Integrated Change & Request links: If a fix requires production changes, an associated Change Record must be linked.

### 5. Mandatory Runbook & Closure Gate
* An incident **cannot be closed** directly after resolution.
* Resolution triggers an automated **Runbook (RCA) task** pre-filled with the incident timeline, metrics, and logs.
* **Strict Quality Gate:** SRE / Team Leads must review and approve the runbook.
* **Authorized Closure:** Once approved, **only the Caller or a member of the Caller's Assignment Group** can perform the final closure of the ticket.

---

## 🤖 AI Root-Cause Analysis (RCA) Engine

InfraWatch turns post-incident runbooks into ground-truth knowledge to train AI models that predict root causes for future incidents.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                  │
│  Observability • Incidents • Runbooks • Deploys/Commits • Production    │
│            Pulse • Chat Logs • Topology/CMDB • Kubernetes Events        │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    INGESTION & EVIDENCE SNAPSHOT                        │
│          PII Scrubbing • UTC Alignment • Context Linking                │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STAGED AI INFERENCE                             │
│  Stage 1: Retrieval (RAG) ──► Stage 2: Correlation ──► Stage 3: RCA     │
│  (Similar Incident Search)   (Telemetry & Change Scan)  (Classifier)    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         HUMAN FEEDBACK LOOP                             │
│       Probable Root Cause + Evidence Links displayed in UI             │
│    Feedback Buttons ("Correct" / "Wrong") ──► Confirmed Runbook RCA     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Keeping the AI in Pace with Production
To ensure predictions stay accurate as system architecture evolves:
* **Production Pulse:** Prod Support and SREs record brief daily notes on known issues, risky deployments, maintenance windows, and workarounds.
* **Change Calendar Ingestion:** CI/CD builds, Git commits, feature flags, and infrastructure updates are correlated automatically with incident timing.
* **Continuous Feedback:** Engineers rate AI suggestions directly in the UI. Confirmed runbook findings update vector embeddings and model parameters.

---

## 🏛️ Technical Stack (Lean "Side-Project" Architecture)

While designed for high-scale enterprise expansion, InfraWatch starts as a lightweight, developer-friendly stack:

| Component | Technology / Implementation | Description |
| :--- | :--- | :--- |
| **Backend** | Single Modular Monolith | Clear separation of Incident, Change/Request, Team/On-call, Runbook, and AI services |
| **Database** | PostgreSQL (Neon/Supabase free tier or Docker) | System of record: tickets, rosters, runbooks, audit |
| **Event Bus** | Apache Kafka (single-broker KRaft in Docker) | Topics `incident.*`, `change.*`, `runbook.*`, `alert.*`, `feedback.*` drive notifications, indexing and AI jobs |
| **Search** | ZincSearch (single binary, ~100 MB RAM) | Full-text search over tickets and runbooks; falls back to SQL if down |
| **Vector DB** | Qdrant (Cloud free cluster or Docker) | Embeddings for similar-incident RAG search |
| **Observability** | OpenTelemetry + Prometheus / Loki | Standardized metric collection, log aggregation, and snapshot storage |
| **Backend / Frontend** | Python FastAPI + React (Vite, TypeScript) | JWT login + Google SSO |
| **LLM Interface** | External API / Local LLM Proxy | Pluggable interface with automatic PII/secret scrubbing |
| **Deployment** | Docker Compose | One-command local setup for seamless development |

---

## 📋 Mandatory Runbook Schema

To guarantee high-quality AI training labels, runbooks enforce a structured schema:

* **Metadata:** Incident ID, impacted services, duration, business impact.
* **Timeline:** Detection time, triage milestones, mitigation time, resolution time.
* **Detection Mechanism:** How the issue was spotted and identified detection gaps.
* **Root Cause Taxonomy:** Categorized root cause (e.g., Code Defect, Config Drift, Capacity/Resource Limit, Upstream Dependency, Human Error).
* **Trigger & Contributing Factors:** What initiated the event and secondary causes.
* **Mitigation & Permanent Fix:** Short-term workaround and long-term action items with assignees.
* **Telemetry Evidence:** Frozen links to metrics, log snippets, and trace IDs.

---

## Quick Start (Phase 1)

```bash
cp .env.example .env            # set JWT_SECRET; optionally GOOGLE_CLIENT_ID
docker compose up --build
```

| Service | URL |
| :--- | :--- |
| App (React) | http://localhost:5173 |
| API docs (Swagger) | http://localhost:8000/docs |
| Mailpit (see sent mails) | http://localhost:8025 |
| ZincSearch UI | http://localhost:4080 (admin / admin123) |
| Qdrant | http://localhost:6333/dashboard |

**Demo logins** (password `password123`): `support1@infrawatch.dev` (Prod Support), `dev1@infrawatch.dev` (Payments lead), `sre1@infrawatch.dev`, `admin@infrawatch.dev`.

**Try the flow:** log in as support1 → create an incident for *Payments Dev* → check Mailpit (To: group DL, CC: on-call) → log in as dev1 → assign, update status, resolve → fill and submit the runbook → sre1 approves → support1 (or support2) closes.

**Run backend tests without Docker:** `cd backend && python -m tests.smoke` (SQLite, no external services needed).

**Google SSO:** create an OAuth Web client in Google Cloud Console, add `http://localhost:5173` as an authorised JS origin, and set `GOOGLE_CLIENT_ID` in `.env`.

### Implemented in Phase 1
- JWT + Google SSO auth, teams, on-call roster
- Incidents with status bar, timeline, group/member assignment
- Group mail with on-call in CC (via SMTP)
- Mandatory runbook, SRE/lead review, close-gate (caller or caller's group)
- Kafka events (`incident.*`, `runbook.published`), ZincSearch indexing

### Not yet built
Observability (OTel/Prometheus), Change & Request tickets, SLA engine, AI/RAG (Qdrant is provisioned but unused).
---

## 📁 Repository Structure

```
InfraWatch/
├── InfraWatch-Architecture.html   # Visual interactive architecture & workflow dashboard
├── README.md
├── docker-compose.yml
├── .env.example
├── backend/                       # FastAPI app (app/), tests/smoke.py
└── frontend/                      # React + Vite UI
```

---

## 🛠️ Next Steps & Roadmap

- [x] Technical Architecture & Data Flow Specification
- [x] Incident Lifecycle & Governance Rules Definition
- [ ] Database Schema Design (PostgreSQL) + Kafka topics + OpenSearch/Qdrant indices
- [ ] Application Scaffold & Core API (Incident & On-Call Roster)
- [ ] Notification & Email Integration (Group DL + CC)
- [ ] OpenTelemetry Ingestion & Evidence Snapshotting
- [ ] Runbook Approval Gate Workflow
- [ ] RAG-based AI Root Cause Prediction Engine
