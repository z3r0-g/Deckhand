from services.database import log_event, get_db
import json

def evaluate_container_intelligence(container):
    """
    Analyzes a container record for Phase 2 triggers:
    1. Digest mismatch detection (Stale image on same tag)
    2. Version history changes
    """
    container_id = container.get('container_id')
    current_digest = container.get('digest_current')
    latest_digest = container.get('digest_latest')
    
    intelligence_results = {
        "digest_mismatch": False,
        "new_event_logged": False
    }

    # 1. Digest Mismatch Detection
    # Useful for rolling tags like :latest or :main
    if current_digest and latest_digest and current_digest != latest_digest:
        intelligence_results["digest_mismatch"] = True

        # Only log if the last event for this container wasn't the same mismatch
        with get_db() as conn:
            last_event = conn.execute(
                "SELECT payload FROM events WHERE container_id = ? AND event_type = ? ORDER BY timestamp DESC LIMIT 1",
                (container_id, "digest_mismatch_detected")
            ).fetchone()

            if not last_event or last_event['payload'] != json.dumps({"old": current_digest, "new": latest_digest}):
                log_event(
                    container_id, 
                    "digest_mismatch_detected", 
                    {"old": current_digest, "new": latest_digest}
                )
                intelligence_results["new_event_logged"] = True

    # 2. Version Change Tracking
    # Detect if the latest_tag has changed compared to running tag
    latest_tag = container.get('latest_tag')
    if latest_tag and container['current_tag'] != latest_tag:
        with get_db() as conn:
            last_event = conn.execute(
                "SELECT payload FROM events WHERE container_id = ? AND event_type = ? ORDER BY timestamp DESC LIMIT 1",
                (container_id, "version_bump_detected")
            ).fetchone()

            if not last_event or last_event['payload'] != json.dumps({"from": container['current_tag'], "to": latest_tag}):
                log_event(
                    container_id,
                    "version_bump_detected",
                    {"from": container['current_tag'], "to": latest_tag}
                )
                intelligence_results["new_event_logged"] = True

    return intelligence_results