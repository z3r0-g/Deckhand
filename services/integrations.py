import os
import logging
try:
    import docker
    DOCKER_LIB_AVAILABLE = True
except ImportError:
    DOCKER_LIB_AVAILABLE = False

from integrations.portainer import PortainerClient
from integrations.dockge import DockgeClient
from integrations.arcane import ArcaneClient
from integrations.dockhand import DockhandClient
from services.health_monitor import health_monitor

logger = logging.getLogger(__name__)

class IntegrationProvider:
    """Base interface for all container orchestration providers."""
    def list_endpoints(self): return []
    def list_containers(self, endpoint_id): return []
    def inspect_container(self, endpoint_id, container_id): return {}
    def pull_image(self, endpoint_id, image, tag): return {"error": "not_implemented"}
    def stop_container(self, endpoint_id, container_id): return {"error": "not_implemented"}
    def remove_container(self, endpoint_id, container_id): return {"error": "not_implemented"}
    def create_container(self, endpoint_id, name, config): return {"error": "not_implemented"}
    def start_container(self, endpoint_id, container_id): return {"error": "not_implemented"}
    def get_images(self, endpoint_id, filters=None): return []
    def prune_images(self, endpoint_id, prune_all=False): return {"error": "not_implemented"}

    def execute_container_update(self, endpoint_id, container_id, image, tag, inspect_data):
        """Standard orchestration flow: Pull -> Stop -> Remove -> Create -> Start"""
        log = []
        def log_step(msg, data=None):
            log.append(f"{msg}: {data}" if data else msg)

        log_step("Pulling image", f"{image}:{tag}")
        pull = self.pull_image(endpoint_id, image, tag)
        if "error" in pull: return {"error": "pull_failed", "details": pull, "log": log}

        log_step("Stopping container")
        stop = self.stop_container(endpoint_id, container_id)
        if "error" in stop: return {"error": "stop_failed", "details": stop, "log": log}

        log_step("Removing container")
        rm = self.remove_container(endpoint_id, container_id)
        if "error" in rm: return {"error": "remove_failed", "details": rm, "log": log}

        name = inspect_data.get("Name", "").lstrip("/")
        log_step("Recreating container", name)
        
        config = inspect_data.get("Config", {})
        host_config = inspect_data.get("HostConfig", {})
        networking = inspect_data.get("NetworkSettings", {}).get("Networks", {})
        
        create_payload = {
            "Image": f"{image}:{tag}",
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
        
        created = self.create_container(endpoint_id, name, create_payload)
        if "error" in created: return {"error": "create_failed", "details": created, "log": log}
        
        new_id = created.get("Id")
        log_step("Starting container", new_id)
        self.start_container(endpoint_id, new_id)

        return {"Id": new_id, "status": "ok", "log": log}

class HealthMonitoredProvider(IntegrationProvider):
    """Wrapper that monitors provider health and records metrics."""
    def __init__(self, provider, provider_name, provider_type):
        self.provider = provider
        self.provider_name = provider_name
        self.provider_type = provider_type
        health_monitor.register_provider(provider_name, provider_type)

    def _call_with_health_tracking(self, method_name, *args, **kwargs):
        """Call provider method and track health."""
        try:
            method = getattr(self.provider, method_name)
            result = method(*args, **kwargs)
            health_monitor.record_success(self.provider_name)
            return result
        except Exception as e:
            health_monitor.record_failure(self.provider_name, str(e))
            raise

    def list_endpoints(self):
        return self._call_with_health_tracking("list_endpoints")

    def list_containers(self, endpoint_id):
        return self._call_with_health_tracking("list_containers", endpoint_id)

    def inspect_container(self, endpoint_id, container_id):
        return self._call_with_health_tracking("inspect_container", endpoint_id, container_id)

    def pull_image(self, endpoint_id, image, tag):
        return self._call_with_health_tracking("pull_image", endpoint_id, image, tag)

    def stop_container(self, endpoint_id, container_id):
        return self._call_with_health_tracking("stop_container", endpoint_id, container_id)

    def remove_container(self, endpoint_id, container_id):
        return self._call_with_health_tracking("remove_container", endpoint_id, container_id)

    def create_container(self, endpoint_id, name, config):
        return self._call_with_health_tracking("create_container", endpoint_id, name, config)

    def start_container(self, endpoint_id, container_id):
        return self._call_with_health_tracking("start_container", endpoint_id, container_id)

    def get_images(self, endpoint_id, filters=None):
        return self._call_with_health_tracking("get_images", endpoint_id, filters)

    def prune_images(self, endpoint_id, prune_all=False):
        return self._call_with_health_tracking("prune_images", endpoint_id, prune_all)

    def execute_container_update(self, endpoint_id, container_id, image, tag, inspect_data):
        return self._call_with_health_tracking("execute_container_update", endpoint_id, container_id, image, tag, inspect_data)

class PortainerProvider(IntegrationProvider):
    def __init__(self, url, key):
        self.client = PortainerClient(url, key)
    
    def list_endpoints(self):
        return self.client.list_endpoints()

    def list_containers(self, endpoint_id):
        return self.client.list_containers(endpoint_id)
    
    def inspect_container(self, endpoint_id, container_id):
        return self.client.inspect_container(endpoint_id, container_id)
    
    def pull_image(self, endpoint_id, image, tag):
        return self.client.pull_image(endpoint_id, image, tag)
    
    def stop_container(self, endpoint_id, container_id):
        return self.client.stop_container(endpoint_id, container_id)
    
    def remove_container(self, endpoint_id, container_id):
        return self.client.remove_container(endpoint_id, container_id)
    
    def create_container(self, endpoint_id, name, config):
        return self.client.create_container(endpoint_id, name, config)
    
    def start_container(self, endpoint_id, container_id):
        return self.client.start_container(endpoint_id, container_id)
    
    def get_images(self, endpoint_id, filters=None):
        return self.client.get_images(endpoint_id, filters)
    
    def prune_images(self, endpoint_id, prune_all=False):
        return self.client.prune_images(endpoint_id, prune_all)

class DockerProvider(IntegrationProvider):
    """Native Docker Engine Provider."""
    def __init__(self, host):
        self.host = host
        self.client = docker.DockerClient(base_url=host) if DOCKER_LIB_AVAILABLE else None
    
    def list_endpoints(self):
        status = "Active" if self.client else "Library Missing"
        return [{"Id": "native", "Name": f"Local Docker Engine ({status})", "Type": "native"}]

    def list_containers(self, endpoint_id):
        if not self.client:
            return {"error": "docker_library_not_installed"}
        
        containers = []
        for c in self.client.containers.list(all=True):
            attrs = c.attrs
            # If the image name is a SHA or missing, resolve it from the image tags
            # or container labels (Compose often stores the intended image name there)
            img_ref = attrs.get("Image", "")
            if img_ref.startswith("sha256:") or not img_ref:
                # Check labels for a readable image name
                labels = attrs.get("Config", {}).get("Labels", {}) or attrs.get("Labels", {})
                attrs["Image"] = labels.get("com.docker.compose.image") or \
                                labels.get("org.opencontainers.image.ref.name") or \
                                (c.image.tags[0] if c.image.tags else img_ref)
            containers.append(attrs)
            
        return containers

    def inspect_container(self, endpoint_id, container_id):
        try:
            return self.client.containers.get(container_id).attrs
        except Exception as e:
            return {"error": str(e)}

    def pull_image(self, endpoint_id, image, tag):
        try:
            self.client.images.pull(image, tag=tag)
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e)}

    def stop_container(self, endpoint_id, container_id):
        try:
            self.client.containers.get(container_id).stop()
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e)}

    def remove_container(self, endpoint_id, container_id):
        try:
            self.client.containers.get(container_id).remove(force=True)
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e)}

    def create_container(self, endpoint_id, name, config):
        try:
            # Map PascalCase (Docker API) to snake_case (docker-py) for compatibility
            params = {
                "name": name,
                "image": config.get("Image"),
                "command": config.get("Cmd"),
                "environment": config.get("Env"),
                "entrypoint": config.get("Entrypoint"),
                "working_dir": config.get("WorkingDir"),
                "user": config.get("User"),
                "labels": config.get("Labels"),
                "host_config": config.get("HostConfig"),
                "networking_config": config.get("NetworkingConfig"),
                "ports": config.get("ExposedPorts"),
                "volumes": config.get("Volumes")
            }
            # Filter out None values
            params = {k: v for k, v in params.items() if v is not None}
            return self.client.api.create_container(**params)
        except Exception as e:
            return {"error": str(e)}

    def start_container(self, endpoint_id, container_id):
        try:
            self.client.containers.get(container_id).start()
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e)}

    def get_images(self, endpoint_id, filters=None):
        return [img.attrs for img in self.client.images.list(filters=filters)]

    def prune_images(self, endpoint_id, prune_all=False):
        if not self.client:
            return {"error": "docker_library_not_installed"}
        try:
            # dangling=False prunes all unused images (Docker's 'all' flag)
            filters = {"dangling": not prune_all}
            return self.client.images.prune(filters=filters)
        except Exception as e:
            return {"error": str(e)}

class DockgeProvider(IntegrationProvider):
    """Dockge Orchestrator Adapter."""
    def __init__(self, url, key):
        self.client = DockgeClient(url, key)
    
    def list_endpoints(self):
        return [{"Id": "dockge", "Name": "Dockge Host", "Type": "dockge"}]

    def list_containers(self, endpoint_id):
        containers = self.client.get_containers()
        if isinstance(containers, dict) and "error" in containers:
            return containers
            
        normalized = []
        for c in containers:
            normalized.append({
                "Id": c.get("containerId") or c.get("id"),
                "Names": [f"/{c.get('name')}"],
                "Image": c.get("image"),
                "Labels": c.get("labels", {}),
                "State": c.get("state"),
                "Status": c.get("status"),
                "_dockge_stack": c.get("_stack_name")
            })
        return normalized

    def inspect_container(self, endpoint_id, container_id):
        # Dockge doesn't provide a direct Docker-style inspect.
        # We resolve basic metadata from the stack container list to satisfy the update route.
        containers = self.client.get_containers()
        for c in containers:
            cid = c.get("containerId") or c.get("id")
            if cid == container_id:
                return {
                    "Config": {
                        "Image": c.get("image"),
                        "Labels": c.get("labels", {})
                    },
                    "Id": container_id,
                    "Name": c.get("name")
                }
        return {"error": "container_not_found_in_dockge"}

    def pull_image(self, endpoint_id, image, tag):
        # Dockge handles pull at the stack level during the update flow
        return {"status": "ok"}

    def stop_container(self, endpoint_id, container_id):
        # Handled by stack up action
        return {"status": "ok"}

    def remove_container(self, endpoint_id, container_id):
        # Handled by stack up action
        return {"status": "ok"}

    def execute_container_update(self, endpoint_id, container_id, image, tag, inspect_data):
        log = []
        def log_step(msg, data=None):
            log.append(f"{msg}: {data}" if data else msg)

        labels = inspect_data.get("Config", {}).get("Labels", {})
        stack_name = labels.get("com.docker.compose.project")
        
        if not stack_name:
            return {"error": "dockge_stack_not_identified"}
            
        log_step("Pulling stack", stack_name)
        p_res = self.client.pull_stack(stack_name)
        if isinstance(p_res, dict) and "error" in p_res:
            return {"error": "dockge_pull_failed", "details": p_res, "log": log}
        
        log_step("Updating stack", stack_name)
        res = self.client.up_stack(stack_name)
        
        if isinstance(res, dict) and "error" in res:
            return {"error": "dockge_up_failed", "details": res, "log": log}
            
        return {"Id": container_id, "status": "ok", "log": log}

    def create_container(self, endpoint_id, name, config):
        return {"error": "use_execute_container_update_for_dockge"}

    def start_container(self, endpoint_id, container_id):
        return {"status": "ok"}

    def get_images(self, endpoint_id, filters=None):
        return []

    def prune_images(self, endpoint_id, prune_all=False):
        return {"error": "not_supported_by_dockge"}

class ArcaneProvider(IntegrationProvider):
    """Arcane Orchestrator Adapter for secure/custom environments."""
    def __init__(self, url, key):
        self.client = ArcaneClient(url, key)
    
    def list_endpoints(self):
        return [{"Id": "arcane", "Name": "Arcane Secure Host", "Type": "arcane"}]

    def list_containers(self, endpoint_id):
        return self.client.list_containers()

    def inspect_container(self, endpoint_id, container_id):
        return self.client.inspect_container(container_id)

    def execute_container_update(self, endpoint_id, container_id, image, tag, inspect_data):
        return self.client.update_container(container_id, image, tag)

    def get_images(self, endpoint_id, filters=None):
        return []

class DockhandProvider(IntegrationProvider):
    """Adapter for the Dockhand Orchestrator."""
    def __init__(self, url, key):
        self.client = DockhandClient(url, key)
    
    def list_endpoints(self):
        return [{"Id": "dockhand_host", "Name": "Dockhand Host", "Type": "dockhand"}]

    def list_containers(self, endpoint_id):
        containers = self.client.get_containers()
        if isinstance(containers, dict) and "error" in containers: return containers
        normalized = []
        for c in containers:
            normalized.append({
                "Id": str(c.get("id")),
                "Names": [f"/{c.get('name')}"],
                "Image": c.get("image"),
                "State": c.get("status", "unknown"),
                "Labels": {}
            })
        return normalized

    def inspect_container(self, endpoint_id, container_id):
        return self.client.inspect_container(container_id)

    def execute_container_update(self, endpoint_id, container_id, image, tag, inspect_data):
        return self.client.update_container(container_id)

    def get_images(self, endpoint_id, filters=None):
        return []

class IntegrationManager:
    def __init__(self):
        self.providers = {}
        self.discover_providers()
    
    def discover_providers(self):
        """Detects and initializes enabled providers based on environment variables."""
        # 1. Native Docker (Socket/API)
        d_host = os.getenv("DOCKER_HOST")
        if not d_host:
            for path in ["/var/run/docker.sock", "/run/docker.sock"]:
                if os.path.exists(path):
                    d_host = f"unix://{path}"
                    break

        if d_host and DOCKER_LIB_AVAILABLE:
            docker_provider = DockerProvider(d_host)
            self.providers["native"] = HealthMonitoredProvider(docker_provider, "native", "docker")
            logger.info(f"Initialized provider: native (docker)")

        # 2. Portainer (Multi-host support: PORTAINER_URL, PORTAINER_1_URL, etc)
        self._discover_multi("portainer", "PORTAINER", PortainerProvider)

        # 3. Dockge (Multi-host support: DOCKGE_URL, DOCKGE_1_URL, etc)
        self._discover_multi("dockge", "DOCKGE", DockgeProvider)

        # 4. Arcane
        self._discover_multi("arcane", "ARCANE", ArcaneProvider)

        # 5. Dockhand (Federated Agents)
        self._discover_multi("dockhand", "DOCKHAND", DockhandProvider)

    def _discover_multi(self, provider_prefix, env_prefix, provider_class):
        """Helper to discover multiple instances of a provider based on environment patterns."""
        # Check primary/default instance
        url = os.getenv(f"{env_prefix}_URL")
        key = os.getenv(f"{env_prefix}_API_KEY")
        if url and key:
            if "://" not in url: url = f"http://{url}"
            provider = provider_class(url.rstrip("/"), key)
            self.providers[provider_prefix] = HealthMonitoredProvider(provider, provider_prefix, provider_prefix)
            logger.info(f"Initialized provider: {provider_prefix}")

        # Check numbered instances (1 to 10)
        for i in range(1, 11):
            url = os.getenv(f"{env_prefix}_{i}_URL")
            key = os.getenv(f"{env_prefix}_{i}_API_KEY")
            if url and key:
                if "://" not in url: url = f"http://{url}"
                provider = provider_class(url.rstrip("/"), key)
                provider_name = f"{provider_prefix}_{i}"
                self.providers[provider_name] = HealthMonitoredProvider(provider, provider_name, provider_prefix)
                logger.info(f"Initialized provider: {provider_name}")

    def is_configured(self):
        """Returns True if at least one integration provider is enabled."""
        return len(self.providers) > 0

    def get_provider(self, name):
        return self.providers.get(name)

    def get_all_endpoints(self):
        """Aggregates all endpoints from all enabled providers."""
        aggregated = []
        for p_name, provider in self.providers.items():
            try:
                eps = provider.list_endpoints()
                if isinstance(eps, list):
                    for ep in eps:
                        ep["_provider"] = p_name
                        aggregated.append(ep)
            except Exception:
                continue
        return aggregated

manager = IntegrationManager()