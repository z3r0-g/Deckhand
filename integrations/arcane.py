import requests

class ArcaneClient:
    """Minimal client for Arcane Orchestrator API."""
    def __init__(self, url, key):
        self.url = url.rstrip('/')
        self.headers = {"X-Arcane-Key": key, "Accept": "application/json"}

    def list_containers(self):
        try:
            r = requests.get(f"{self.url}/containers", headers=self.headers, timeout=10)
            return r.json() if r.status_code == 200 else {"error": f"Arcane error: {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def inspect_container(self, container_id):
        try:
            r = requests.get(f"{self.url}/containers/{container_id}", headers=self.headers, timeout=10)
            return r.json() if r.status_code == 200 else {"error": "not_found"}
        except Exception as e:
            return {"error": str(e)}

    def update_container(self, container_id, image, tag):
        try:
            payload = {"image": image, "tag": tag}
            r = requests.post(f"{self.url}/containers/{container_id}/update", 
                              headers=self.headers, json=payload, timeout=60)
            return r.json() if r.status_code == 200 else {"error": "update_failed"}
        except Exception as e:
            return {"error": str(e)}