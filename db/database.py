# db/database.py
import sqlite3
import time
from flask import g

DB_PATH = "deckhand.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    app.teardown_appcontext(close_db)

    with app.app_context():
        db = get_db()
        with open("db/schema.sql", "r") as f:
            db.executescript(f.read())
        db.commit()


# ---------------------------------------------------------
# UPDATE HISTORY HELPERS
# ---------------------------------------------------------

def add_update_history(container_id, old_tag, new_tag, old_digest, new_digest):
    """
    Append a new update-history entry for a container.
    """
    db = get_db()
    db.execute(
        """
        INSERT INTO update_history (container_id, timestamp, old_tag, new_tag, old_digest, new_digest)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(container_id),
            int(time.time()),
            old_tag,
            new_tag,
            old_digest,
            new_digest,
        ),
    )
    db.commit()


def get_update_history(container_id, limit=50):
    """
    Retrieve update history entries for a container, newest first.
    """
    db = get_db()
    cur = db.execute(
        """
        SELECT timestamp, old_tag, new_tag, old_digest, new_digest
        FROM update_history
        WHERE container_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (str(container_id), limit),
    )
    return [dict(row) for row in cur.fetchall()]
