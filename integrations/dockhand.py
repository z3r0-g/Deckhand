import requests

class DockhandClient:
    """Client for the Dockhand Orchestrator API."""
    def __init__(self, url, key):
        self.url = url.rstrip('/')
        # Dockhand uses X-Api-Key for authentication
        self.headers = {"X-Api-Key": key, "Accept": "application/json"}

    def get_containers(self):
        """Fetch container status from Dockhand."""
        try:
            # Ensure we target the API prefix if not provided in URL
            endpoint = f"{self.url}/containers" if "/api" in self.url else f"{self.url}/api/containers"
            r = requests.get(endpoint, headers=self.headers, timeout=15)
            if r.status_code == 200:
                return r.json()
            return {"error": f"Dockhand API error: {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def inspect_container(self, container_id):
        """Inspect a specific container via Dockhand."""
        containers = self.get_containers()
        if isinstance(containers, list):
            for c in containers:
                if str(c.get("id")) == str(container_id):
                    return {"Config": {"Image": c.get("image")}, "Id": str(c.get("id")), "Name": c.get("name")}
        return {"error": "dockhand_container_not_found"}

    def update_container(self, container_id):
        """Trigger an update for a container managed by Dockhand."""
        try:
            endpoint = f"{self.url}/containers/{container_id}/update" if "/api" in self.url else f"{self.url}/api/containers/{container_id}/update"
            r = requests.post(endpoint, headers=self.headers, timeout=120)
            return r.json()
        except Exception as e:
            return {"error": str(e)}