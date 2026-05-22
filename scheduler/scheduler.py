import json
import os
from flask_apscheduler import APScheduler

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "scheduler_config.json")

# Global scheduler instance (Flask extension)
scheduler = APScheduler()


# ---------------------------------------------------------
# INIT SCHEDULER (called from app.py)
# ---------------------------------------------------------
def init_scheduler(app):
    scheduler.init_app(app)

    cfg = load_scheduler_config()

    if cfg.get("enabled", False):
        interval = cfg.get("interval_minutes", 60)

        scheduler.add_job(
            id="deckhand_update_scheduler",
            func=run_scheduled_updates,
            trigger="interval",
            minutes=interval,
            replace_existing=True
        )

    scheduler.start()


# ---------------------------------------------------------
# CONFIG LOAD/SAVE
# ---------------------------------------------------------
def load_scheduler_config():
    if not os.path.exists(CONFIG_PATH):
        return {"enabled": False, "interval_minutes": 60, "skip": {}}

    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_scheduler_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)


# ---------------------------------------------------------
# MAIN SCHEDULER LOOP
# ---------------------------------------------------------
def run_scheduled_updates():
    """
    Runs automatically based on interval_minutes.
    """
    from flask import current_app
    from integrations.portainer import PortainerClient
    from services.registry_poller import RegistryPoller
    from db.database import add_update_history

    app = current_app._get_current_object()

    portainer = PortainerClient(
        base_url=app.config.get("PORTAINER_URL", ""),
        api_key=app.config.get("PORTAINER_API_KEY", "")
    )
    poller = RegistryPoller()

    cfg = load_scheduler_config()
    skip_list = cfg.get("skip", {})

    endpoints = portainer.list_endpoints()
    if not isinstance(endpoints, list):
        return

    for ep in endpoints:
        ep_id = ep.get("Id")
        containers = portainer.list_containers(ep_id)

        if not isinstance(containers, list):
            continue

        for c in containers:
            cid = c.get("Id")
            image_ref = c.get("Image", "")

            # Skip logic
            if skip_list.get(cid):
                continue

            poll = poller.poll_image(image_ref)

            current_tag = poll.get("current_tag")
            latest_tag = poll.get("latest_tag")

            update_needed = (
                latest_tag is not None
                and current_tag is not None
                and latest_tag != current_tag
            )

            if not update_needed:
                continue

            try:
                _perform_update(portainer, poller, ep_id, c, poll)
            except Exception:
                continue


# ---------------------------------------------------------
# INTERNAL UPDATE FUNCTION
# ---------------------------------------------------------
def _perform_update(portainer, poller, ep_id, container, poll_result):
    from db.database import add_update_history

    full_id = container.get("Id")
    inspect = portainer.inspect_container(ep_id, full_id)

    config = inspect.get("Config", {})
    host_config = inspect.get("HostConfig", {})
    networking = inspect.get("NetworkSettings", {}).get("Networks", {})

    repo = poll_result.get("repo")
    tag = poll_result.get("latest_tag") or poll_result.get("current_tag")

    old_tag = poll_result.get("current_tag")
    old_digest = poll_result.get("digest_current")

    # Pull
    portainer.pull_image(ep_id, repo, tag)

    # Stop + remove
    portainer.stop_container(ep_id, full_id)
    portainer.remove_container(ep_id, full_id)

    # Recreate
    container_name = inspect.get("Name", "").lstrip("/") or "container"

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

    created = portainer.create_container(ep_id, container_name, create_payload)
    new_id = created.get("Id")

    portainer.start_container(ep_id, new_id)

    new_digest = poll_result.get("digest_latest")

    add_update_history(
        container_id=full_id,
        old_tag=old_tag,
        new_tag=tag,
        old_digest=old_digest,
        new_digest=new_digest
    )
