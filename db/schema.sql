-- ---------------------------------------------------------
-- CORE FUNCTION TABLES
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS containers (
    id INTEGER PRIMARY KEY,
    host TEXT,
    container_name TEXT,
    image_repo TEXT,
    current_tag TEXT,
    latest_tag TEXT,
    digest_current TEXT,
    digest_latest TEXT,
    version_delta INTEGER,
    cve_score REAL,
    cve_count INTEGER,
    status TEXT,
    last_seen DATETIME,
    last_updated DATETIME
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    container_id INTEGER,
    event_type TEXT,
    payload TEXT,
    timestamp DATETIME
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY,
    container_id INTEGER,
    cron_expression TEXT,
    enabled BOOLEAN,
    created_at DATETIME
);

-- ---------------------------------------------------------
-- AMMENDED DATA TABLES
-- ---------------------------------------------------------

-- Update History (append-only)
CREATE TABLE IF NOT EXISTS update_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    container_id TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    old_tag TEXT,
    new_tag TEXT,
    old_digest TEXT,
    new_digest TEXT
);

CREATE INDEX IF NOT EXISTS idx_history_container
    ON update_history (container_id);


-- Ignored Containers (per-container ignore toggle)
CREATE TABLE IF NOT EXISTS ignored_containers (
    container_id TEXT PRIMARY KEY
);


-- Pinned Major Versions (per-container version pin)
CREATE TABLE IF NOT EXISTS pinned_versions (
    container_id TEXT PRIMARY KEY,
    major_version INTEGER NOT NULL
);
