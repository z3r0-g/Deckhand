import requests


class PortainerClient:
    def __init__(self, base_url, api_key):
        # Ensure URL has scheme
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url  # Portainer 2.41 defaults to HTTPS

        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

        # Portainer 2.41 uses self-signed certs by default
        self.verify_ssl = False

    # ---------------------------------------------------------
    # Internal GET helper
    # ---------------------------------------------------------
    def _get(self, path):
        url = f"{self.base_url}{path}"
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "url": url}

    # ---------------------------------------------------------
    # Endpoint + Container Listing
    # ---------------------------------------------------------
    def list_endpoints(self):
        return self._get("/api/endpoints")

    def list_containers(self, endpoint_id):
        return self._get(f"/api/endpoints/{endpoint_id}/docker/containers/json?all=1")

    def inspect_container(self, endpoint_id, container_id):
        return self._get(
            f"/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
        )

    # ---------------------------------------------------------
    # Image Pull (Watchtower behavior)
    # ---------------------------------------------------------
    def pull_image(self, endpoint_id, image, tag):
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/create"
        params = {"fromImage": image, "tag": tag}

        try:
            r = requests.post(
                url,
                headers=self.headers,
                params=params,
                timeout=120,
                verify=self.verify_ssl
            )
            r.raise_for_status()
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e), "url": url}

    # ---------------------------------------------------------
    # Container Stop / Remove
    # ---------------------------------------------------------
    def stop_container(self, endpoint_id, container_id):
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stop"
        try:
            r = requests.post(
                url,
                headers=self.headers,
                timeout=30,
                verify=self.verify_ssl
            )
            r.raise_for_status()
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e), "url": url}

    def remove_container(self, endpoint_id, container_id):
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}"
        params = {"force": 1}

        try:
            r = requests.delete(
                url,
                headers=self.headers,
                params=params,
                timeout=30,
                verify=self.verify_ssl
            )
            r.raise_for_status()
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e), "url": url}

    # ---------------------------------------------------------
    # Container Create / Start (Watchtower-style recreation)
    # ---------------------------------------------------------
    def create_container(self, endpoint_id, name, config):
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/create"
        params = {"name": name.lstrip("/")}

        try:
            r = requests.post(
                url,
                headers=self.headers,
                params=params,
                json=config,
                timeout=120,
                verify=self.verify_ssl
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e), "url": url}

    def start_container(self, endpoint_id, container_id):
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/start"

        try:
            r = requests.post(
                url,
                headers=self.headers,
                timeout=30,
                verify=self.verify_ssl
            )
            r.raise_for_status()
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e), "url": url}

    def get_images(self, endpoint_id, filters=None):
        """Lists images with optional filters."""
        f_param = f"?filters={filters}" if filters else ""
        url = f"/api/endpoints/{endpoint_id}/docker/images/json{f_param}"
        return self._get(url)

    def prune_images(self, endpoint_id, prune_all=False):
        """Prunes images on a specific endpoint. prune_all=True removes all unused images."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/prune"
        params = {"filters": '{"dangling": ["false"]}' if prune_all else '{"dangling": ["true"]}'}
        try:
            r = requests.post(
                url, 
                headers=self.headers, 
                params=params, 
                timeout=60, 
                verify=self.verify_ssl
            )
            if r.status_code == 200:
                return r.json()
            return {"error": "prune_failed", "status_code": r.status_code}
        except Exception as e:
            return {"error": str(e)}
