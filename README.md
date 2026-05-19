# 🛳️ Deckhand
### *Agentless Container Update Intelligence for Portainer + Homarr*

Deckhand is a modern, lightweight, agentless replacement for **DIUN** and **Watchtower**, designed for homelab and small‑scale container environments that use **Portainer** for orchestration and **Homarr** as a unified dashboard.

Instead of automatically updating containers, Deckhand provides **intelligent monitoring**, **version awareness**, **CVE scoring**, and **manual or scheduled update controls** directly from a Homarr widget. You stay in control — Deckhand simply gives you the visibility and tools to act.

---

## 🚀 Features

### 🔍 **Agentless Container Discovery**
Deckhand connects directly to the **Portainer API** to discover:

- Containers  
- Stacks  
- Image tags  
- Image digests  
- Registry credentials  
- Endpoint metadata  

No sidecars, no host agents, no Docker socket mounts.

---

### 🏷️ **Registry Polling (DIUN Replacement)**
Deckhand polls container registries to detect:

- New tags  
- New digests  
- Semantic version changes  
- Patch/minor/major deltas  
- Deprecated or removed tags  

Supports:

- Docker Hub  
- GHCR  
- Private registries (via Portainer credentials)

---

### 🛡️ **CVE‑Aware Intelligence**
Deckhand optionally integrates with **Trivy** to scan images and extract:

- Highest CVE severity  
- Critical CVE count  
- Patched version (if available)  
- Vulnerability metadata  

CVE data is merged with version delta to determine severity.

---

### 🎨 **Severity‑Based Status Colors**
Deckhand uses a simple, intuitive color system:

| State | Meaning | Color | Conditions |
|-------|---------|--------|------------|
| **Green** | Up to date | `#00C853` | version delta = 0 |
| **Warning** | Slightly behind | `#FFD600` | delta = 1 |
| **Urgent** | Outdated or vulnerable | `#D50000` | delta ≥ 2 OR critical CVE |

These colors appear directly in the Homarr widget.

---

### 🧭 **Homarr UI Controls**
Deckhand exposes a clean, responsive UI inside Homarr with:

- **Update Now**  
- **Schedule Update**  
- **Ignore Version**  
- **View CVEs**  
- **View Version History**  
- **Force Scan**  

All actions are performed through Deckhand’s API and executed via Portainer.

---

### 🔧 **Portainer‑Driven Updates (Watchtower Replacement)**
Deckhand performs updates using the Portainer API:

- Pull new image  
- Recreate container  
- Redeploy stack  
- Restart services  
- Log update events  

Deckhand never mutates your system without your explicit approval.

---

### 🕒 **Built‑In Scheduler**
Deckhand includes a flexible scheduler supporting:

- Cron expressions  
- Patch‑only updates  
- CVE‑triggered updates  
- Per‑container schedules  
- Per‑host schedules  

Schedules are stored in SQLite (WAL mode).

---

### 📦 **Lightweight & Self‑Contained**
Deckhand runs as a single container:

- FastAPI or Flask backend  
- SQLite WAL database  
- Optional Trivy binary  
- Zero agents  
- Zero sidecars  

---

## 🧱 Architecture Overview
┌──────────────────────────┐
│        Homarr         │
│  (Deckhand Widget)       │
└─────────────┬────────────┘
              │
              ▼
┌───────────────────┐
│   Deckhand   │
│  API + Scanner    │
│  Scheduler + DB   │
└───────┬──────────┘
        │
        ┴────────────────────────────────┐
        │                                │
        ▼                                ▼
┌──────────────────┐          ┌──────────────────────┐
│  Registry Poller  │         │  Security Scanner    │
│ (Docker Hub/GHCR) │         │   (Trivy API)        │
└──────────────────┘          └──────────────────────┘
        │
        ▼
┌──────────────────┐
│   Portainer API  │
│  (Discovery +    │
│   Update Exec)   │
└──────────────────┘


---

## 📚 API Overview

### `GET /hosts`
List Portainer endpoints.

### `GET /containers`
Return all containers with status, version delta, and CVE data.

### `GET /containers/{id}`
Return detailed metadata for a single container.

### `POST /containers/{id}/update`
Trigger a Portainer‑managed update.

### `POST /containers/{id}/schedule`
Create or modify an update schedule.

### `POST /containers/{id}/ignore`
Ignore a specific version.

### `POST /scan`
Force a full registry + CVE scan.

---
## 🗄️ Database Schema

Deckhand uses a lightweight, high‑performance SQLite database (WAL mode) to store container metadata, CVE results, schedules, and event history.

### `containers`
Tracks the current state of every discovered container across all Portainer endpoints.

id                INTEGER PRIMARY KEY
host              TEXT            -- Portainer endpoint name or ID
container_name    TEXT
image_repo        TEXT            -- e.g. "linuxserver/sonarr"
current_tag       TEXT            -- tag currently deployed
latest_tag        TEXT            -- latest tag detected in registry
digest_current    TEXT            -- digest of deployed image
digest_latest     TEXT            -- digest of latest image
version_delta     INTEGER         -- semantic version difference
cve_score         REAL            -- highest CVE severity
cve_count         INTEGER         -- number of critical CVEs
status            TEXT            -- green | warning | urgent
last_seen         DATETIME
last_updated      DATETIME        -- last time container was updated

Code

---

### `events`
Audit log of all actions and detections performed by Deckhand.

id                INTEGER PRIMARY KEY
container_id      INTEGER
event_type        TEXT            -- update_detected, cve_detected, update_executed
payload           TEXT            -- JSON blob with event details
timestamp         DATETIME

Code

---

### `schedules`
Stores user‑defined update schedules for containers.

id                INTEGER PRIMARY KEY
container_id      INTEGER
cron_expression   TEXT
enabled           BOOLEAN
created_at        DATETIME


---

## 🛠️ Installation (Coming Soon)

A `docker-compose.yml` will be provided once the API and UI stabilize.  
Deckhand will run as a single container with optional Trivy integration.

---

## 🧭 Roadmap

### **Phase 1 — MVP**
- Portainer endpoint discovery  
- Registry polling engine  
- Semantic version delta logic  
- Manual update execution via Portainer  
- Basic Homarr widget (status + update button)

### **Phase 2 — Intelligence**
- CVE scanning (Trivy local or remote)  
- Digest mismatch detection  
- Event history + audit log  
- Version history tracking

### **Phase 3 — UX**
- Scheduling engine (cron)  
- Ignore version rules  
- Advanced Homarr modals  
- Host health indicators  
- Per‑container settings

### **Phase 4 — Ecosystem**
- ntfy.sh notifications  
- MQTT publishing  
- Prometheus exporter  
- Grafana dashboard  
- Webhook integrations

---

## 🤝 Contributing

PRs, issues, and feature requests are welcome.  
Deckhand is built for the homelab community — help shape it.

---

## 📜 License

MIT License (or your preferred license)

---

## ⭐ Acknowledgements

Deckhand is inspired by the strengths of:

- Portainer  
- DIUN  
- Watchtower  
- Homarr  

…but built to solve the gaps between them with a clean, modern, agentless approach.
