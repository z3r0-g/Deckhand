import requests

class DockgeClient:
    """
    A client for the Dockge API.
    Note: Dockge API is primarily websocket-based. This client assumes 
    a REST-compatible bridge or future REST implementation.
    """
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _request(self, method, path, **kwargs):
        url = f"{self.base_url}{path}"
        try:
            r = requests.request(method, url, headers=self.headers, timeout=30, **kwargs)
            r.raise_for_status()
            if r.status_code == 204:
                return {"status": "success"}
            return r.json()
        except Exception as e:
            return {"error": str(e), "url": url}

    def list_stacks(self):
        """Lists all stacks managed by Dockge."""
        return self._request("GET", "/api/stacks")

    def get_stack(self, stack_name):
        """Gets detailed info for a specific stack."""
        return self._request("GET", f"/api/stacks/{stack_name}")

    def pull_stack(self, stack_name):
        """Triggers a pull for all images in a stack."""
        return self._request("POST", f"/api/stacks/{stack_name}/pull")

    def up_stack(self, stack_name):
        """Triggers a stack up (create/start)."""
        return self._request("POST", f"/api/stacks/{stack_name}/up")

    def get_containers(self):
        """Helper to get all containers across all stacks."""
        stacks = self.list_stacks()
        if isinstance(stacks, dict) and "error" in stacks:
            return []
            
        all_containers = []
        for stack in stacks:
            name = stack.get("name")
            details = self.get_stack(name)
            if isinstance(details, dict) and "containers" in details:
                for c in details["containers"]:
                    c["_stack_name"] = name
                    all_containers.append(c)
        return all_containers