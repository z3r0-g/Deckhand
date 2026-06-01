from flask import Blueprint, current_app, jsonify, request, Response
from services.registry_poller import RegistryPoller
from services.cache import cache
from services.intelligence import evaluate_container_intelligence
from services.database import (
    upsert_container,
    log_event,
    get_all_schedule_rules,
    add_update_history,
    get_update_history,
    get_events_for_container,
    set_schedule_rule
)
from services.integrations import manager
from services.health_monitor import health_monitor
import json
import time

api_blueprint = Blueprint("api", __name__)

# ---------------------------------------------------------
# GET /api/hosts
# ---------------------------------------------------------
@api_blueprint.get("/hosts")
def get_hosts():
    endpoints = manager.get_all_endpoints()

    # Enrich endpoints with health status
    for ep in endpoints:
        provider_name = ep.get("_provider", "")
        health = health_monitor.get_provider_status(provider_name)
        if health:
            ep["health"] = health
        else:
            ep["health"] = {
                "status": "unknown",
                "last_check": None,
                "error_message": None,
                "consecutive_failures": 0
            }

    return jsonify(endpoints)


# ---------------------------------------------------------
# GET /api/containers
# ---------------------------------------------------------
@api_blueprint.get("/containers")
def get_containers():
    endpoints = manager.get_all_endpoints()

    if not isinstance(endpoints, list):
        return jsonify({"error": "Failed to fetch endpoints", "details": endpoints})

    all_containers = []

    for ep in endpoints:
        ep_id = ep.get("Id")
        ep_name = ep.get("Name")
        provider = manager.get_provider(ep.get("_provider"))
        containers = provider.list_containers(ep_id)

        all_containers.append({
            "endpoint_id": ep_id,
            "endpoint_name": ep_name,
            "containers": containers
        })

    return jsonify(all_containers)


# ---------------------------------------------------------
# GET /api/containers/scan
# ---------------------------------------------------------
@api_blueprint.get("/containers/scan")
def scan_containers():
    poller = RegistryPoller()
    endpoints = manager.get_all_endpoints()
    results = []

    if not isinstance(endpoints, list):
        return jsonify({"error": "Failed to fetch endpoints", "details": endpoints})

    for ep in endpoints:
        ep_id = ep.get("Id")
        ep_name = ep.get("Name")
        provider = manager.get_provider(ep.get("_provider"))

        containers = provider.list_containers(ep_id)

        if isinstance(containers, dict) and "error" in containers:
            results.append({
                "endpoint_id": ep_id,
                "endpoint_name": ep_name,
                "error": containers["error"]
            })
            continue

        scanned = []

        for c in containers:
            image_ref = c.get("Image", "")
            poll_result = poller.poll_image(image_ref)

            heat = poll_result.get("heat", 0)

            scanned.append({
                "container_id": c.get("Id"),
                "container_name": c.get("Names", ["unknown"])[0],
                "image": image_ref,
                "scan": poll_result,
                "heat": heat
            })

        results.append({
            "endpoint_id": ep_id,
            "endpoint_name": ep_name,
            "containers": scanned
        })

    return jsonify(results)


# ---------------------------------------------------------
# POST /api/containers/<container_id>/update
# ---------------------------------------------------------
@api_blueprint.post("/containers/<container_id>/update")
def update_container(container_id):
    """
    Triggers a Portainer-managed update flow for a single container.
    Pulls the latest image, stops, removes, and recreates the container
    preserving existing configurations.
    """
    poller = RegistryPoller()
    endpoint_id = request.args.get("endpoint_id")
    provider_name = request.args.get("provider")

    log = []
    def log_step(msg, data=None):
        entry = msg if data is None else f"{msg}: {data}"
        log.append(entry)
    
    endpoints = manager.get_all_endpoints()
    if not isinstance(endpoints, list):
        return jsonify({"error": "Failed to fetch endpoints", "details": endpoints}), 500

    found = None
    found_ep_id = None
    found_provider = None

    for ep in endpoints:
        # Filter by endpoint_id and provider if provided
        if endpoint_id is not None and str(ep.get("Id")) != endpoint_id: continue
        if provider_name and ep.get("_provider") != provider_name: continue

        ep_id = ep.get("Id")
        provider = manager.get_provider(ep.get("_provider"))
        containers = provider.list_containers(ep_id)

        if not isinstance(containers, list):
            continue

        for c in containers:
            if c.get("Id") == container_id:
                found = c
                found_ep_id = ep_id
                found_provider = provider
                break

        if found:
            break

        for c in containers:
            if c.get("Id", "").startswith(container_id):
                found = c
                found_ep_id = ep_id
                found_provider = provider
                break

        if found:
            break

    if not found:
        return jsonify({"error": "container_not_found", "container_id": container_id}), 404

    full_id = found.get("Id")
    log_step("Resolved container", full_id)

    inspect = found_provider.inspect_container(found_ep_id, full_id)
    if isinstance(inspect, dict) and "error" in inspect:
        return jsonify({"error": "inspect_failed", "details": inspect}), 500

    config = inspect.get("Config", {})
    host_config = inspect.get("HostConfig", {})
    networking = inspect.get("NetworkSettings", {}).get("Networks", {})

    image_ref = config.get("Image", found.get("Image", ""))
    poll_result = poller.poll_image(image_ref)

    repo = poll_result.get("repo")
    tag = poll_result.get("latest_tag") or poll_result.get("current_tag")

    log_step("Image reference", image_ref)
    log_step("Poll result", poll_result)

    if not repo or not tag:
        return jsonify({
            "error": "image_resolution_failed",
            "image_ref": image_ref,
            "poll_result": poll_result,
            "log": log
        }), 500

    old_tag = poll_result.get("current_tag")
    old_digest = poll_result.get("digest_current")

    # Delegate Orchestration to the Provider
    # This allows Dockge to use stack-up and Docker to use pull/rm/run
    update_result = found_provider.execute_container_update(
        endpoint_id=found_ep_id,
        container_id=full_id,
        image=repo,
        tag=tag,
        inspect_data=inspect
    )

    if "error" in update_result:
        return jsonify(update_result), 500

    # Log Event and History
    log_event(full_id, "update_executed", {"from": old_tag, "to": tag, "status": "success"})
    add_update_history(full_id, old_tag, tag, old_digest, poll_result.get("digest_latest"))

    return jsonify({
        "status": "updated",
        "endpoint_id": found_ep_id,
        "new_container_id": update_result.get("Id"),
        "image_before": image_ref,
        "image_after": f"{repo}:{tag}",
        "log": update_result.get("log", [])
    })


# ---------------------------------------------------------
# GET /api/containers/<container_id>/history
# ---------------------------------------------------------
@api_blueprint.get("/containers/<container_id>/history")
def container_history(container_id):
    try:
        history = get_update_history(container_id, limit=50)
        return jsonify(history)
    except Exception as e:
        current_app.logger.error(f"History fetch failed for {container_id}: {e}")
        return jsonify({
            "error": "history_fetch_failed",
            "container_id": container_id
        }), 500


# ---------------------------------------------------------
# GET /api/containers/<container_id>/events
# ---------------------------------------------------------
@api_blueprint.get("/containers/<container_id>/events")
def container_events(container_id):
    """
    Returns the intelligence audit log for a specific container.
    Phase 2 component.
    """
    try:
        events = get_events_for_container(container_id)
        # Parse JSON payloads for the frontend
        for e in events:
            if e.get('payload'):
                try:
                    e['payload'] = json.loads(e['payload'])
                except (json.JSONDecodeError, TypeError):
                    pass
        return jsonify(events)
    except Exception as e:
        current_app.logger.error(f"Event fetch failed for {container_id}: {e}")
        return jsonify({"error": "event_fetch_failed"}), 500


# ---------------------------------------------------------
# GET /api/containers/status
# ---------------------------------------------------------
@api_blueprint.get("/containers/status")
def containers_status():
    """
    Aggregates container status across all endpoints, performs registry
    polling, and triggers intelligence evaluation. Gracefully continues
    if individual providers fail.
    """
    from scheduler.scheduler import load_scheduler_config
    cfg = load_scheduler_config()
    skip_list = cfg.get("skip", {})
    rules = get_all_schedule_rules()
    poller = RegistryPoller()
    results = []
    provider_errors = []

    endpoints = manager.get_all_endpoints()
    current_app.logger.info(f"Integration Discovery: Found {len(endpoints)} endpoints across configured providers")

    for ep in endpoints:
        ep_id = ep.get("Id")
        ep_name = ep.get("Name")
        provider_name = ep.get("_provider")
        provider = manager.get_provider(provider_name)

        try:
            containers = provider.list_containers(ep_id)
        except Exception as e:
            error_msg = str(e)
            current_app.logger.error(f"Provider {provider_name} failed to list containers: {error_msg}")
            health_monitor.record_failure(provider_name, error_msg)
            provider_errors.append({
                "provider": provider_name,
                "endpoint_id": ep_id,
                "endpoint_name": ep_name,
                "error": error_msg
            })
            continue

        if not isinstance(containers, list):
            current_app.logger.warning(f"Endpoint {ep_name} (ID: {ep_id}) returned non-list containers: {containers}")
            continue

        # Record success for this provider
        health_monitor.record_success(provider_name)

        for c in containers:
            cid = c.get("Id")
            raw_image_id = c.get("ImageID") or c.get("Image", "")
            image_ref = c.get("Image", "")
            labels = c.get("Labels", {})

            # If we see a SHA, try to recover the human-readable image name from labels.
            # This is common when an image is updated/dangling but the container is still running the old ID.
            if image_ref.startswith("sha256:") or len(image_ref) == 64:
                image_ref = labels.get("com.docker.compose.image") or \
                            labels.get("org.opencontainers.image.ref.name") or \
                            labels.get("org.opencontainers.image.title") or \
                            image_ref

            # Wrap polling in a try/except so one registry failure doesn't kill the whole list
            try:
                poll = poller.poll_image(image_ref)
            except Exception as e:
                current_app.logger.error(f"Failed to poll image {image_ref}: {e}")
                poll = {"heat": 0, "current_tag": "unknown", "latest_tag": None}

            current_tag = poll.get("current_tag")
            latest_tag = poll.get("latest_tag")
            digest_current = poll.get("digest_current")
            digest_latest = poll.get("digest_latest")
            heat = poll.get("heat", 0)

            # Ensure we have strings to compare
            is_outdated = False
            if latest_tag and current_tag:
                 is_outdated = str(latest_tag) != str(current_tag)

            update_available = is_outdated

            # Stack Detection from labels
            labels = c.get("Labels", {})
            stack_name = labels.get("com.docker.compose.project") or labels.get("com.docker.stack.namespace") or "Standalone"

            container_data = {
                "container_id": cid,
                "name": c.get("Names", ["unknown"])[0].lstrip("/"),
                "image": image_ref,
                "image_id": raw_image_id,
                "current_tag": current_tag,
                "latest_tag": latest_tag,
                "digest_current": digest_current,
                "digest_latest": digest_latest,
                "heat": heat,
                "update_available": update_available,
                "endpoint_id": ep_id,
                "endpoint_name": ep_name,
                "provider": ep.get("_provider"),
                "update_url": f"/api/containers/{cid}/update",
                "skipped": skip_list.get(cid, False),
                "stack": stack_name,
                "policy": rules.get(cid, {}).get('policy', 'manual')
            }

            # Trigger Intelligence Evaluation
            evaluate_container_intelligence(container_data)

            # PHASE 2: Fleet State Persistence
            upsert_container(container_data)

            results.append(container_data)

    # Log provider errors summary
    if provider_errors:
        current_app.logger.warning(f"Provider failures during status aggregation: {len(provider_errors)} endpoint(s) failed")
        for err in provider_errors:
            current_app.logger.warning(
                f"  - Provider '{err['provider']}' ({err['endpoint_name']}): {err['error']}"
            )

    # Cache the full status for the SSE stream to consume
    cache.set("container_status", results, ttl=300)

    return jsonify(results)

# ---------------------------------------------------------
# GET /api/stream/status
# ---------------------------------------------------------
@api_blueprint.get("/stream/status")
def stream_status():
    def event_stream():
        last_payload = None

        while True:
            payload = cache.get("container_status")

            if payload is not None:
                serialized = json.dumps(payload)

                if serialized != last_payload:
                    yield f"data: {serialized}\n\n"
                    last_payload = serialized

            time.sleep(1)

    return Response(event_stream(), mimetype="text/event-stream")

# ---------------------------------------------------------
# GET /api/scheduler/config
# ---------------------------------------------------------
@api_blueprint.get("/scheduler/config")
def scheduler_get_config():
    from scheduler.scheduler import load_scheduler_config
    cfg = load_scheduler_config()
    return jsonify(cfg)

# ---------------------------------------------------------
# POST /api/scheduler/config
# ---------------------------------------------------------
@api_blueprint.post("/scheduler/config")
def scheduler_update_config():
    from scheduler.scheduler import load_scheduler_config, save_scheduler_config, scheduler

    data = request.json or {}
    cfg = load_scheduler_config()

    # Update fields
    if "enabled" in data:
        cfg["enabled"] = bool(data["enabled"])

    if "interval_minutes" in data:
        cfg["interval_minutes"] = int(data["interval_minutes"])

    save_scheduler_config(cfg)

    # Rebuild scheduler job
    try:
        # Explicitly remove job to avoid duplicates on interval changes
        scheduler.remove_job("deckhand_update_scheduler")
    except Exception:
        pass

    if cfg["enabled"]:
        scheduler.add_job(
            id="deckhand_update_scheduler",
            func="scheduler.scheduler:run_scheduled_updates",
            trigger="interval",
            minutes=cfg["interval_minutes"],
            replace_existing=True
        )

    return jsonify({"status": "ok", "config": cfg})

@api_blueprint.get("/maintenance/prune/dry-run")
def maintenance_prune_dry_run():
    """Returns a list of dangling images across all endpoints for confirmation."""
    from services.maintenance import get_unused_images
    return jsonify(get_unused_images())

@api_blueprint.post("/maintenance/prune")
def maintenance_prune():
    """
    Triggers a prune of unused Docker images across all endpoints.
    Phase 2 Cleanup Task.
    """
    from services.maintenance import execute_maintenance_prune
    return jsonify(execute_maintenance_prune())

# ---------------------------------------------------------
# PHASE 3: SCHEDULING ENGINE API
# ---------------------------------------------------------
@api_blueprint.get("/scheduler/targets")
def get_scheduler_targets():
    """Lists all possible scheduling targets (Stacks and individual Containers)."""
    status = cache.get("container_status") or []

    stacks = {}

    for c in status:
        s_name = c.get('stack', 'Standalone')
        if s_name not in stacks:
            stacks[s_name] = []
            
        stacks[s_name].append({
            "id": c['container_id'],
            "name": c['name'],
            "policy": c.get('policy', 'manual'),
            "host": c.get('endpoint_name')
        })

    return jsonify({
        "stacks": stacks
    })

@api_blueprint.post("/scheduler/rules")
def update_scheduler_rule():
    """Updates the policy for a specific target."""
    data = request.json
    target_id = data.get("target_id")
    target_type = data.get("target_type", "container")
    policy = data.get("policy") # 'auto', 'manual', 'ignore'

    set_schedule_rule(target_id, target_type, policy)
    return jsonify({"status": "ok"})
