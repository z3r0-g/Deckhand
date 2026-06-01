# 🛳️ Deckhand
![Deckhand](static/Deckhand.png)
### *Agentless Container Update Intelligence for Docker, Portainer & Dockge*

Deckhand is a modern, lightweight, agentless replacement for **DIUN** and **Watchtower**, designed for homelab and small‑scale container environments that want a simple unified dashboard widget responsive to scaling. 

Instead of automatically updating containers like Watchtower, Deckhand provides **intelligent monitoring**, **version awareness**, **CVE scoring**, and **manual or scheduled update controls** directly from any iFrame-capable Dashboard UI.

---

## 🚀 Features

### 🔍 **Agnostic Lifecycle Orchestration**
Deckhand is provider-agnostic. It automatically discovers, monitors, and manages containers across:

- **Docker Engine:** Local socket (`/var/run/docker.sock`) or remote API.
- **Portainer:** Full environment aggregation and endpoint management.
- **Dockge:** Specialized Docker Compose stack management.

Once discovered, Deckhand performs updates (pull, stop, remove, recreate) using the specific API of your detected backend without requiring host agents or sidecars.

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
- **Private Registries** (via Provider-level authentication)

---

### 🛡️ **CVE‑Aware Intelligence**
Deckhand optionally integrates with **Trivy** to scan images and extract:

- Highest CVE severity  
- Critical CVE count  
- Patched version (if available)  
- Vulnerability metadata  

CVE data is merged with version delta to determine severity.

---

### 🎨 **Heat-Based Update Status**

Deckhand uses an intuitive "heat" system to indicate update urgency. The UI supports two modes:

**Professional Mode:**
| Heat | Meaning | Icon | Condition |
|------|---------|------|-----------|
| 0 | Up to date | ✔️ | No updates available |
| 1 | Patch available | ⬆️ | Patch version update |
| 2 | Minor available | 🔧 | Minor version update |
| 3 | Major available | ⚠️ | Major version update |
| 4 | Critical | 🔥 | Critical update or vulnerabilities |

**Fun Mode:**
| Heat | Meaning | Icon | Condition |
|------|---------|------|-----------|
| 0 | Cool | 🧊 | Chillin' (up to date) |
| 1 | Warm | 🌡️ | A little spicy (patch) |
| 2 | Hot | 🔥 | Getting toasty (minor) |
| 3 | Burning | ⚠️🔥 | This is fine 🔥🐶 (major) |
| 4 | Streaming | 🌋 | Meltdown imminent (critical) |

---

### 🧭 **UI Controls**
Deckhand exposes a clean, responsive UI:

- **Update Now** — Immediately pull and deploy the latest image  
- **View Version History** — See all previous updates  
- **Show/Hide Updates** — Filter to only show containers with updates  
- **Refresh Status** — Force a registry scan and state refresh
- **Scheduler** — Configure automatic updates (Phase 1+)  

All actions are performed through Deckhand’s API and executed via the detected orchestration backend (Docker, Portainer, or Dockge).

---

---

### 🕒 **Built‑In Scheduler**
Deckhand includes a flexible scheduler supporting:

- Interval-based automatic updates  
- Skip lists (per-container)  
- Event logging  

Advanced cron expressions and CVE-triggered updates are planned for later phase.

---

### 📦 **Lightweight & Self‑Contained**
Deckhand runs as a single container:

- Flask backend  
- SQLite WAL database  
- Zero agents  
- Zero sidecars  

---

## 📸 Screenshots

| ![Default View](screenshots/default.png) | ![Unfiltered View](screenshots/unfilter.png) |
|:---:|:---:|
| *Default View* | *Unfiltered View* |



---

## � UI Overview

### `GET /health`
JSON Health Check:

```json
{
  "service": "deckhand",
  "status": "ok"
}
```

### `GET /`
Scalable User Interface, intended to be iFramed into Homarr or any other dashboard until that platform supports direct integration with the API.

---

## 📚 API Overview

### `GET /api/hosts`
List all discovered orchestration endpoints (Docker, Portainer, Dockge).

### `GET /api/containers` (Internal)
Return all raw container data from all providers.

### `GET /api/containers/scan`
Force a full registry + CVE scan.

### `GET /api/containers/status`
Return all containers with status, version delta, and CVE data.

### `POST /api/containers/{id}/update`
Trigger a Watchtower-style update flow for a single container by ID (full or prefix).

Query Param:
`endpoint_id` (optional) - to restrict search to specific host

### `POST /api/scheduler/rules`
Create or modify an update policy (`auto`, `manual`, `ignore`) for a specific container or stack.

### `POST /api/scheduler/config`
Update global scheduler settings (interval, master enable).


---
## 🗄️ Database Schema

Deckhand uses a lightweight, high‑performance SQLite database (WAL mode) to store container metadata, CVE results, schedules, and event history.

### `containers`
Tracks the current state of every discovered container across all managed endpoints.

| Column | Type | Description |
|:---|:---|:---|
| `id` | INTEGER | PRIMARY KEY |
| `host` | TEXT | Endpoint name (Docker host, Portainer env, etc.) |
| `container_name` | TEXT | Name of the discovered container |
| `image_repo` | TEXT | e.g. "linuxserver/sonarr" |
| `current_tag` | TEXT | Tag currently deployed |
| `latest_tag` | TEXT | Latest tag detected in registry |
| `digest_current` | TEXT | Digest of deployed image |
| `digest_latest` | TEXT | Digest of latest image |
| `version_delta` | INTEGER | Semantic version difference |
| `cve_score` | REAL | Highest CVE severity |
| `cve_count` | INTEGER | Number of critical CVEs |
| `status` | TEXT | green \| warning \| urgent |
| `last_seen` | DATETIME | Timestamp of last discovery |
| `last_updated` | DATETIME | Last time container was updated |

---

### `events`
Audit log of all actions and detections performed by Deckhand.

| Column | Type | Description |
|:---|:---|:---|
| `id` | INTEGER | PRIMARY KEY |
| `container_id` | INTEGER | ID of the container |
| `event_type` | TEXT | `update_detected`, `cve_detected`, `update_executed` |
| `payload` | TEXT | JSON blob with event details |
| `timestamp` | DATETIME | Timestamp of the event |

---

### `schedule_rules`
Stores user‑defined update policies for containers and stacks.

| Column | Type | Description |
|:---|:---|:---|
| `id` | INTEGER | PRIMARY KEY |
| `target_id` | TEXT | Container ID or Stack Name |
| `target_type` | TEXT | 'container' or 'stack' |
| `policy` | TEXT | 'auto', 'manual', or 'ignore' |
| `updated_at` | DATETIME | Last modification timestamp |

---

## 🛠️ Installation

### Prerequisites

- **Docker** & **Docker Compose** (because why else do you want this project?)

### Quick Start
```yaml
services:
  deckhand:
    image: ghcr.io/z3r0-g/deckhand:latest
    container_name: deckhand
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - deckhand-db:/app/data
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - FLASK_ENV=production
      - DECKHAND_UI_MODE=fun
      - DATABASE_PATH=/app/data/deckhand.db
    security_opt:
      - no-new-privileges:true
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s

volumes:
  deckhand-db:
    driver: local
```

**Steps:**
1. Create a `docker-compose.yml` with the content above.
2. (Optional) Add environment variables for Portainer or Dockge if you wish to manage remote endpoints or stacks.
3. Run `docker compose up -d`.
4. Access the UI at `http://localhost:5000`.

---

---

## ⚙️ Configuration

All configuration is managed via **environment variables** (see `.env.example` for defaults).
Deckhand is **Zero-Config** by default when running on a local Docker host with the socket mounted.

### Environment Variables

| Category | Variable | Description |
|----------|----------|-------------|
| **General** | `DECKHAND_UI_MODE` | UI theme (`fun` or `pro`) |
| | `DATABASE_PATH` | SQLite database location |
| | `SECRET_KEY` | Flask session key (auto-generated if missing) |
| **Docker Engine** | `DOCKER_HOST` | Remote Docker API URL (e.g., `tcp://10.0.0.5:2375`) |
| **Portainer** | `PORTAINER_URL` | Portainer API endpoint (e.g., `https://portainer:9443`) |
| | `PORTAINER_API_KEY` | Portainer API key (Format: `ptr_...`) |
| | `PORTAINER_X_URL` | Additional instances (e.g., `PORTAINER_1_URL`, `PORTAINER_2_URL`) |
| **Dockge** | `DOCKGE_URL` | Dockge API endpoint (e.g., `http://dockge:5001`) |
| | `DOCKGE_API_KEY` | Dockge API key |
| | `DOCKGE_X_URL` | Additional instances (e.g., `DOCKGE_1_URL`, `DOCKGE_2_URL`) |
| **Arcane** | `ARCANE_URL` | Arcane API endpoint (e.g., `http://arcane:8080`) |
| | `ARCANE_API_KEY` | Arcane API key |
| | `ARCANE_X_URL` | Additional instances (e.g., `ARCANE_1_URL`) |
| **Dockhand** | `DOCKHAND_URL` | Dockhand API endpoint (e.g., `http://dockhand:8080`) |
| | `DOCKHAND_API_KEY` | Dockhand API key |
| | `DOCKHAND_X_URL` | Additional instances (e.g., `DOCKHAND_1_URL`) |

---

**Note:** This project is configured to use a **.devcontainer** but can be started manually as follows:
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables (If using multi-host, specify the stack manager details here)
export PORTAINER_URL="https://your-portainer:9000"
export PORTAINER_API_KEY="ptr_your_key"

# Run locally
python app.py
# Open http://localhost:5000
```

---

## 🗺️ Registry Support

Deckhand auto-detects and polls the following registries without additional configuration:

### Automatically Supported Container Registries

| Registry | Example Image | Notes |
|----------|-------|-------|
| **Docker Hub** | `linuxserver/nginx:latest` | Public & private (via Portainer auth) |
| **GHCR** (GitHub) | `ghcr.io/z3r0-g/deckhand:latest` | Public & private (via token) |
| **lscr.io** (LinuxServer) | `lscr.io/linuxserver/nginx:latest` | Rolling tags aware |
| **Private Registries** | `registry.example.com:5000/myapp:v1.0` | Self-signed certs OK |

### Registry Detection Logic

Deckhand automatically detects registries by image prefix:

- Images with `ghcr.io/` → polled via **GHCR API**
- Images with `lscr.io/` → polled via **LinuxServer API** (rolling-tag safe)
- Images with custom domain (e.g., `registry.example.com/`) → polled via **Private Registry API**
- Plain images (e.g., `linuxserver/nginx`) → polled via **Docker Hub API**

### Using GHCR Images

To use images from **GitHub Container Registry** (GHCR):

1. **Public GHCR images** work out of the box:
   ```
   ghcr.io/z3r0-g/deckhand:latest
   ```

2. **Private GHCR images** require a GitHub Personal Access Token:
   - Create a PAT in GitHub → Settings → Developer Settings → Personal Access Tokens
   - Select `read:packages` scope
   - Ensure your provider (Portainer, Docker, etc.) has credentials configured for `ghcr.io`.
   - Deckhand will automatically leverage the provider's stored authentication.

### Example: Adding a GHCR-Hosted Container

```bash
# Deploy your container via your chosen provider:
ghcr.io/your-org/your-app:v1.2.3

# Deckhand will:
# 1. Detect it's GHCR
# 2. Poll ghcr.io for available tags
# 3. Compare semantic versions
# 4. Show update status in UI
# 5. Pull the latest image when you click "Update Now"
```

---

---

## 🧭 Roadmap

### **✅ Phase 1 — MVP (COMPLETE)**
- ✅ Portainer endpoint discovery  
- ✅ Registry polling engine  
- ✅ Semantic version delta logic  
- ✅ Manual update execution via Portainer  
- ✅ Basic Homarr widget (status + update button)
- ✅ GHCR support (public + private)
- ✅ Docker Hub support
- ✅ Private registry support
- ✅ Self-contained docker container
- ✅ Production-ready docker-compose

### **✅ Phase 2 — Intelligence (COMPLETE)**
- ✅ Digest mismatch detection
- ✅ Event history + audit log
- ✅ Version history tracking
- ✅ Unused image/volume/network cleanup

### **✅ Phase 3 — UX (COMPLETE)**
- ✅ Scheduling Engine (defined by stack) 
  - ✅ Update Scheduler Modal with rich UI elements enabling stack-level scheduling (in the style of "Azure Update Rings")
  - ✅ Enable Ignore Version Rules (Defined in Scheduler Modal by existing Container Image)
- ✅ Advance Event Modal
  - ✅ Add 'last container version' history record, to display in Events
  - ✅ Add identified 'Portainer Notifications' records, to display in Events

---

---
### **✅ Phase 4 — Multi‑Backend Orchestration (COMPLETE)**  
Deckhand is now a universal container management engine. This phase introduced a **Provider Abstraction Layer** that enables Deckhand to operate across multiple backend providers simultaneously.

- ✅ **🐳 Direct Docker "Native" Engine:** Support for the Direct Docker API (Socket/TLS) out of the box.
- ✅ **Standardized Update Logic:** Native `pull -> stop -> rm -> run` orchestration within the Docker provider.
- ✅ **Orchestrator Adapters:** Seamless integration with Portainer while maintaining a "Source of Truth" for your fleet.

#### **🔌 Orchestrator Adapters**
To ensure Deckhand doesn't break the "Source of Truth" for users who prefer specific UIs, we will implement **Adapters**. These tell the orchestrator to perform the update so the UI stays in sync:
- ✅ **Portainer Adapter** (Refactor of current logic)
- ✅ **Dockge Adapter** (Stack-based updates)
* ✅ **Dockhand Adapter** (Support for Dockhand Orchestrator)
* ✅ **Arcane Adapter** (Secure orchestrator support)

#### **🌐 Unified Fleet Management**
- **Backend-Agnostic discovery:** Manage a heterogeneous fleet where some hosts are raw Docker, some are Portainer endpoints, others use Dockge, Arcane, or Dockhand.
- **Multi-Host Aggregation:** A single Deckhand instance acting as a "Command Center" for your entire homelab. Supports multiple orchestration instances via numbered environment variables (e.g., `PORTAINER_1_URL`, `DOCKGE_1_URL`, `ARCANE_1_URL`, `DOCKHAND_1_URL`).
- **Agentless philosophy:** All communication remains remote and agentless, requiring only network/API access to the target hosts.

---

### **Phase 5 — Homelab Intelligence & Stack Mapping (Planned)**  
As homelabs scale, they naturally evolve into complex ecosystems: dozens of containers, multiple stacks, reverse proxies, VPN tunnels, shared volumes, and service chains that become difficult to visualize over time. Phase 5 introduces **Homelab Intelligence** — a new layer of insight designed to make Deckhand feel like “Immich‑level polish for homelab container management.”

#### **🗺️ Automatic Architecture Diagrams**  
Generate real‑time, interactive diagrams for any container or stack using provider metadata, networks, volumes, and reverse‑proxy rules.

A new **“View Network Map”** button will appear on each container card, opening a modal that displays:

- Container‑level topology  
- Connected services  
- Network boundaries  
- Volume mounts  
- Reverse‑proxy chains  
- Upstream/downstream dependencies  

This modal will also be accessible from inside the **Update Scheduler** modal via a compact **View Network Map* icon.

#### **🔗 Dependency Mapping**  
Automatically map relationships between containers, including:

- Reverse proxy → service routing  
- Database → application links  
- VPN → client tunnels  
- Multi‑container stack relationships  
- Cross‑host dependencies (via managed endpoints)

This provides a clear picture of how updates may impact the rest of the stack.

#### **🤖 AI‑Powered Upgrade Planning**  
Create new **intelligence** service, with ability to use external local LLM as default, or optional Gemini and Copilot integrations, to analyze stack dependencies and generate an **optimal update sequence** that avoids downtime or broken chains.

The scheduler will:

- Reorder updates based on dependency graph  
- Warn about breaking changes  
- Suggest safe update windows  
- Automatically apply the correct sequence when schedules run  

---

### **Phase 6 — Maintenance & Utilities**
- Create new modal to Backup and Restore container volumes

  **Backup Command:**
  ```bash
  # Replace my_volume with your volume name
  docker run --rm \
    -v my_volume:/data \
    -v $(pwd):/backup \
    alpine tar czf /backup/my_volume_backup.tar.gz -C /data .
  ```

  **Restore Command:**
  ```bash
  docker run --rm \
    -v my_volume:/data \
    -v $(pwd):/backup \
    alpine sh -c "cd /data && tar xzf /backup/my_volume_backup.tar.gz --strip 1"
  ```

---

### **Phase 7 — Continue to Expand Functionality**
- CVE scanning (Trivy integration, any others to consider?)  
- Notifications (ntfy.shintegration, any others to consider?)
- Enable MQTT publishing (TBD, tell me what to integrate!)  
- Create Prometheus Exporter (A feature request for this and I will create an Exporter!)
- **Exposed Ports Audit**  
  - Identify containers exposing ports to LAN/WAN  
  - Highlight reverse‑proxy boundaries  
  - Surface weak or unintended network exposure  
  - Integrate with existing security risk scoring  
- **Open to other ideas! Drop me a feature request!**

---

## 🤝 Contributing

PRs, issues, and feature requests are welcome!  
Deckhand is my first community project, after abadoning Synology DSM for my homelab, help me make it better!

---

## 📜 License

Apache 2.0

---

## ⭐ Acknowledgements

Deckhand is inspired by the strengths of:

- Portainer  
- DIUN  
- Watchtower  
- Homarr  

…but built to solve the gaps between them with a clean, modern, agentless approach to Container Update Management.
