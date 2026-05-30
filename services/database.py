import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.getenv("DATABASE_PATH", "deckhand.db")

def get_db():
    """Connects to the SQLite database with WAL mode enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db(app=None):
    """Initializes the database schema for Phase 1 and Phase 2."""
    with get_db() as conn:
        # Containers Table (Phase 1 core)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS containers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                container_id TEXT UNIQUE,
                host TEXT,
                container_name TEXT,
                image_repo TEXT,
                current_tag TEXT,
                latest_tag TEXT,
                digest_current TEXT,
                digest_latest TEXT,
                version_delta INTEGER DEFAULT 0,
                cve_score REAL DEFAULT 0,
                cve_count INTEGER DEFAULT 0,
                status TEXT,
                heat INTEGER DEFAULT 0,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_updated DATETIME
            )
        ''')

        # Migration: Add container_id if it's an old database
        try:
            conn.execute('ALTER TABLE containers ADD COLUMN container_id TEXT')
            conn.execute('CREATE UNIQUE INDEX idx_container_id ON containers(container_id)')
        except sqlite3.OperationalError:
            pass # Already exists

        # Migration: Add heat if missing
        try:
            conn.execute('ALTER TABLE containers ADD COLUMN heat INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass

        # Update History Table (Phase 1 manual updates)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                container_id TEXT,
                old_tag TEXT,
                new_tag TEXT,
                old_digest TEXT,
                new_digest TEXT,
                timestamp INTEGER
            )
        ''')

        # Events / Audit Log Table (Phase 2)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                container_id TEXT,
                event_type TEXT,
                payload TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def log_event(container_id, event_type, data):
    """Utility to log intelligence events (mismatches, updates, etc)."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO events (container_id, event_type, payload) VALUES (?, ?, ?)",
            (str(container_id), event_type, json.dumps(data))
        )

def upsert_container(data):
    """Persists fleet state by updating or inserting container records."""
    with get_db() as conn:
        # Check if version or digest changed to update 'last_updated'
        existing = conn.execute(
            "SELECT current_tag, digest_current FROM containers WHERE container_id = ?",
            (data['container_id'],)
        ).fetchone()

        last_updated_clause = ""
        if existing:
            tag_changed = existing['current_tag'] != data['current_tag']
            digest_changed = existing['digest_current'] != data['digest_current']
            if tag_changed or digest_changed:
                last_updated_clause = ", last_updated = CURRENT_TIMESTAMP"

        conn.execute(f'''
            INSERT INTO containers (
                container_id, host, container_name, image_repo, 
                current_tag, latest_tag, digest_current, digest_latest, 
                version_delta, heat, status, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(container_id) DO UPDATE SET
                latest_tag = excluded.latest_tag,
                digest_latest = excluded.digest_latest,
                digest_current = excluded.digest_current,
                heat = excluded.heat,
                last_seen = CURRENT_TIMESTAMP
                {last_updated_clause}
        ''', (
            data['container_id'], data['endpoint_name'], data['name'], data['image'],
            data['current_tag'], data['latest_tag'], data['digest_current'], data['digest_latest'],
            data.get('version_delta', 0), data['heat'], 
            'warning' if data['update_available'] else 'green'
        ))

def add_update_history(container_id, old_tag, new_tag, old_digest, new_digest):
    """Logs a successful manual update."""
    import time
    with get_db() as conn:
        conn.execute(
            "INSERT INTO history (container_id, old_tag, new_tag, old_digest, new_digest, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (container_id, old_tag, new_tag, old_digest, new_digest, int(time.time()))
        )

def get_update_history(container_id, limit=50):
    """Retrieves manual update history for the UI."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, container_id, old_tag, new_tag, old_digest, new_digest, timestamp "
            "FROM history WHERE container_id = ? ORDER BY timestamp DESC LIMIT ?",
            (container_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

def get_events_for_container(container_id):
    """Retrieves all events for a specific container ordered by most recent."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, container_id, event_type, payload, timestamp "
            "FROM events WHERE container_id = ? ORDER BY timestamp DESC",
            (container_id,)
        )
        return [dict(row) for row in cursor.fetchall()]