from flask import Blueprint, current_app, jsonify, request, Response
from integrations.portainer import PortainerClient
from services.registry_poller import RegistryPoller
from cache import cache
import json
import time

api_blueprint = Blueprint("api", __name__)


# ---------------------------------------------------------
# Portainer Client Loader
# ---------------------------------------------------------
def get_portainer():
    url = current_app.config.get("PORTAINER_URL", "")
    key = current_app.config.get("PORTAINER_API_KEY", "")
    if not url or not key:
        current_app.logger.error(f"Portainer config missing: URL='{url}', Key='{'***' if key else 'MISSING'}'")
    return PortainerClient(
        base_url=url,
        api_key=key
    )


# ---------------------------------------------------------
# GET /api/hosts
# ---------------------------------------------------------
@api_blueprint.get("/hosts")
def get_hosts():
    portainer = get_portainer()
    endpoints = portainer.list_endpoints()
    return jsonify(endpoints)


# ---------------------------------------------------------
# GET /api/containers
# ---------------------------------------------------------
@api_blueprint.get("/containers")
def get_containers():
    portainer = get_portainer()
    endpoints = portainer.list_endpoints()

    if not isinstance(endpoints, list):
        return jsonify({"error": "Failed to fetch endpoints", "details": endpoints})

    all_containers = []

    for ep in endpoints:
        ep_id = ep.get("Id")
        ep_name = ep.get("Name")

        containers = portainer.list_containers(ep_id)

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
    portainer = get_portainer()
    poller = RegistryPoller()

    endpoints = portainer.list_endpoints()
    results = []

    if not isinstance(endpoints, list):
        return jsonify({"error": "Failed to fetch endpoints", "details": endpoints})

    for ep in endpoints:
        ep_id = ep.get("Id")
        ep_name = ep.get("Name")

        containers = portainer.list_containers(ep_id)

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
    from db.database import add_update_history

    portainer = get_portainer()
    poller = RegistryPoller()
    endpoint_id = request.args.get("endpoint_id", type=int)

    log = []
    def log_step(msg, data=None):
        entry = msg if data is None else f"{msg}: {data}"
        log.append(entry)

    endpoints = portainer.list_endpoints()
    if not isinstance(endpoints, list):
        return jsonify({"error": "Failed to fetch endpoints", "details": endpoints}), 500

    if endpoint_id is not None:
        endpoints_to_search = [e for e in endpoints if e.get("Id") == endpoint_id]
        if not endpoints_to_search:
            return jsonify({"error": "endpoint_not_found", "endpoint_id": endpoint_id}), 404
    else:
        endpoints_to_search = endpoints

    found = None
    found_ep_id = None

    for ep in endpoints_to_search:
        ep_id = ep.get("Id")
        containers = portainer.list_containers(ep_id)

        if not isinstance(containers, list):
            continue

        for c in containers:
            if c.get("Id") == container_id:
                found = c
                found_ep_id = ep_id
                break

        if found:
            break

        for c in containers:
            if c.get("Id", "").startswith(container_id):
                found = c
                found_ep_id = ep_id
                break

        if found:
            break

    if not found:
        return jsonify({"error": "container_not_found", "container_id": container_id}), 404

    full_id = found.get("Id")
    log_step("Resolved container", full_id)

    inspect = portainer.inspect_container(found_ep_id, full_id)
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

    log_step("Pulling image", f"{repo}:{tag}")
    pull_result = portainer.pull_image(found_ep_id, repo, tag)
    log_step("Pull result", pull_result)

    if isinstance(pull_result, dict) and "error" in pull_result:
        return jsonify({"error": "image_pull_failed", "details": pull_result, "log": log}), 500

    log_step("Stopping container")
    stop_result = portainer.stop_container(found_ep_id, full_id)
    log_step("Stop result", stop_result)

    if isinstance(stop_result, dict) and "error" in stop_result:
        return jsonify({"error": "stop_failed", "details": stop_result, "log": log}), 500

    log_step("Removing container")
    rm_result = portainer.remove_container(found_ep_id, full_id)
    log_step("Remove result", rm_result)

    if isinstance(rm_result, dict) and "error" in rm_result:
        return jsonify({"error": "remove_failed", "details": rm_result, "log": log}), 500

    container_name = inspect.get("Name") or found.get("Names", ["unknown"])[0]
    if container_name.startswith("/"):
        container_name = container_name[1:]

    log_step("Recreating container", container_name)

    create_payload = {
        "Image": f"{repo}:{tag}",
        "Env": config.get("Env"),
        "Cmd": config.get("Cmd"),
        "Entrypoint": config.get("Entrypoint"),
        "WorkingDir": config.get("WorkingDir"),
        "User": config.get("User"),
        "Labels": config.get("Labels"),
        "ExposedPorts": config.get("ExposedPorts"),
        "Volumes": config.get("Volumes"),
        "HostConfig": host_config,
        "NetworkingConfig": {"EndpointsConfig": networking}
    }

    created = portainer.create_container(found_ep_id, container_name, create_payload)
    log_step("Create result", created)

    if isinstance(created, dict) and "error" in created:
        return jsonify({"error": "create_failed", "details": created, "log": log}), 500

    new_id = created.get("Id")

    log_step("Starting container", new_id)
    start_result = portainer.start_container(found_ep_id, new_id)
    log_step("Start result", start_result)

    if isinstance(start_result, dict) and "error" in start_result:
        return jsonify({"error": "start_failed", "details": start_result, "log": log}), 500

    log_step("Update complete")

    new_tag = tag
    new_digest = poll_result.get("digest_latest")

    add_update_history(
        container_id=full_id,
        old_tag=old_tag,
        new_tag=new_tag,
        old_digest=old_digest,
        new_digest=new_digest
    )

    return jsonify({
        "status": "updated",
        "endpoint_id": found_ep_id,
        "old_container_id": full_id,
        "new_container_id": new_id,
        "image_before": image_ref,
        "image_after": f"{repo}:{tag}",
        "log": log
    })


# ---------------------------------------------------------
# GET /api/containers/<container_id>/history
# ---------------------------------------------------------
@api_blueprint.get("/containers/<container_id>/history")
def container_history(container_id):
    from db.database import get_update_history

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
# GET /api/containers/status
# ---------------------------------------------------------
@api_blueprint.get("/containers/status")
def containers_status():
    from scheduler.scheduler import load_scheduler_config
    cfg = load_scheduler_config()
    skip_list = cfg.get("skip", {})

    portainer = get_portainer()
    poller = RegistryPoller()

    results = []

    endpoints = portainer.list_endpoints()
    current_app.logger.info(f"Portainer Discovery: Found {len(endpoints) if isinstance(endpoints, list) else 0} endpoints")

    if not isinstance(endpoints, list):
        current_app.logger.error(f"Failed to fetch Portainer endpoints: {endpoints}")
        return jsonify({"error": "portainer_connection_failed", "details": endpoints}), 500

    for ep in endpoints:
        ep_id = ep.get("Id")
        ep_name = ep.get("Name")

        containers = portainer.list_containers(ep_id)
        if not isinstance(containers, list):
            current_app.logger.warning(f"Endpoint {ep_name} (ID: {ep_id}) returned non-list containers: {containers}")
            continue

        current_app.logger.info(f"Endpoint {ep_name}: Processing {len(containers)} containers")

        for c in containers:
            cid = c.get("Id")
            image_ref = c.get("Image", "")

            # Wrap polling in a try/except so one registry failure doesn't kill the whole list
            try:
                poll = poller.poll_image(image_ref)
            except Exception as e:
                current_app.logger.error(f"Failed to poll image {image_ref}: {e}")
                poll = {"heat": 0, "current_tag": "unknown", "latest_tag": None}

            current_tag = poll.get("current_tag")
            latest_tag = poll.get("latest_tag")
            heat = poll.get("heat", 0)

            # Ensure we have strings to compare
            is_outdated = False
            if latest_tag and current_tag:
                 is_outdated = str(latest_tag) != str(current_tag)

            update_available = is_outdated

            results.append({
                "container_id": cid,
                "name": c.get("Names", ["unknown"])[0].lstrip("/"),
                "image": image_ref,
                "current_tag": current_tag,
                "latest_tag": latest_tag,
                "heat": heat,
                "update_available": update_available,
                "endpoint_id": ep_id,
                "endpoint_name": ep_name,
                "update_url": f"/api/containers/{cid}/update",
                "skipped": skip_list.get(cid, False)
            })

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
    scheduler.remove_job("deckhand_update_scheduler", jobstore=None, silent=True)

    if cfg["enabled"]:
        scheduler.add_job(
            id="deckhand_update_scheduler",
            func="scheduler.scheduler:run_scheduled_updates",
            trigger="interval",
            minutes=cfg["interval_minutes"],
            replace_existing=True
        )

    return jsonify({"status": "ok", "config": cfg})
