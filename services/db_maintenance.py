import logging
import time
from datetime import datetime, timedelta
from services.database import get_db

logger = logging.getLogger(__name__)


def prune_events(days=90):
    """Delete events older than N days."""
    cutoff_time = time.time() - (days * 86400)
    cutoff_date = datetime.fromtimestamp(cutoff_time)

    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "DELETE FROM events WHERE timestamp < datetime(?, 'seconds')",
            (int(cutoff_time),)
        )

        deleted = cursor.rowcount
        db.commit()

        logger.info(f"Database maintenance: Pruned {deleted} events older than {days} days")
        return deleted

    except Exception as e:
        logger.error(f"Failed to prune events: {e}")
        return 0


def prune_history(days=90):
    """Delete history records older than N days."""
    cutoff_time = time.time() - (days * 86400)

    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "DELETE FROM history WHERE timestamp < datetime(?, 'seconds')",
            (int(cutoff_time),)
        )

        deleted = cursor.rowcount
        db.commit()

        logger.info(f"Database maintenance: Pruned {deleted} history records older than {days} days")
        return deleted

    except Exception as e:
        logger.error(f"Failed to prune history: {e}")
        return 0


def cleanup_stale_containers(days=30):
    """Delete containers not seen in N days (stale entries)."""
    cutoff_time = time.time() - (days * 86400)

    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "DELETE FROM containers WHERE last_seen < datetime(?, 'seconds')",
            (int(cutoff_time),)
        )

        deleted = cursor.rowcount
        db.commit()

        logger.info(f"Database maintenance: Cleaned up {deleted} stale container records (not seen in {days} days)")
        return deleted

    except Exception as e:
        logger.error(f"Failed to cleanup stale containers: {e}")
        return 0


def get_db_stats():
    """Return row counts and approximate sizes of main tables."""
    try:
        db = get_db()
        cursor = db.cursor()

        stats = {}

        # Get row counts
        for table in ["containers", "history", "events", "schedule_rules"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            stats[table] = {"rows": count}

        # Get approximate page counts (for size estimation)
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        total_size_bytes = page_count * page_size

        stats["database"] = {
            "pages": page_count,
            "page_size": page_size,
            "size_bytes": total_size_bytes,
            "size_mb": round(total_size_bytes / (1024 * 1024), 2)
        }

        logger.debug(f"Database stats: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return {}


def execute_maintenance(db_retention_days=90, stale_days=30):
    """Execute full maintenance routine: prune old data and cleanup stale containers."""
    logger.info("Starting database maintenance...")

    start_time = time.time()

    # Run pruning operations
    events_deleted = prune_events(days=db_retention_days)
    history_deleted = prune_history(days=db_retention_days)
    containers_deleted = cleanup_stale_containers(days=stale_days)

    # Get stats
    stats = get_db_stats()

    elapsed = time.time() - start_time

    logger.info(
        f"Database maintenance completed in {elapsed:.2f}s: "
        f"deleted {events_deleted} events, {history_deleted} history records, {containers_deleted} stale containers. "
        f"Database size: {stats.get('database', {}).get('size_mb')}MB"
    )

    return {
        "elapsed_seconds": elapsed,
        "events_deleted": events_deleted,
        "history_deleted": history_deleted,
        "containers_deleted": containers_deleted,
        "stats": stats
    }
