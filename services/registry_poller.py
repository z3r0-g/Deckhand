import requests
import re
from packaging import version
from cache import cache

from utils.versioning import version_delta


class RegistryPoller:
    """
    DIUN-style Registry Poller for Deckhand
    with:
    - v-prefixed semver support
    - Docker Hub pagination
    - GHCR support
    - lscr.io support (rolling-tag aware)
    - Private registry support
    - Digest comparison
    - 1-hour caching
    """

    OCI_ACCEPT = {
        "Accept": (
            "application/vnd.oci.image.index.v1+json, "
            "application/vnd.oci.image.manifest.v1+json, "
            "application/vnd.docker.distribution.manifest.v2+json"
        )
    }

    def __init__(self, ttl=3600):
        self.ttl = ttl
        self.semver_re = re.compile(r"^v?\d+\.\d+\.\d+([+-].*)?$")

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def poll_image(self, image_ref):
        repo, current_tag = self._split_image(image_ref)
        registry = self._detect_registry(repo)

        cache_key = f"registry:{repo}"
        cached = cache.get(cache_key)
        if cached:
            latest_tag = cached.get("latest_tag")
            digest_current = cached.get("digest_current")
            digest_latest = cached.get("digest_latest")
            update_available = latest_tag is not None and latest_tag != current_tag

            heat = self._compute_heat(
                current_tag=current_tag,
                latest_tag=latest_tag,
                digest_current=digest_current,
                digest_latest=digest_latest,
                update_available=update_available,
            )

            return {
                **cached,
                "repo": repo,
                "current_tag": current_tag,
                "heat": heat,
            }

        try:
            if registry == "dockerhub":
                result = self._poll_dockerhub(repo, current_tag)
            elif registry == "ghcr":
                result = self._poll_ghcr(repo, current_tag)
            elif registry == "lscr":
                result = self._poll_lscr(repo, current_tag)
            else:
                result = self._poll_private(registry, repo, current_tag)

            latest_tag = result.get("latest_tag")
            digest_current = result.get("digest_current")
            digest_latest = result.get("digest_latest")
            update_available = latest_tag is not None and latest_tag != current_tag

            heat = self._compute_heat(
                current_tag=current_tag,
                latest_tag=latest_tag,
                digest_current=digest_current,
                digest_latest=digest_latest,
                update_available=update_available,
            )

            result["repo"] = repo
            result["current_tag"] = current_tag
            result["heat"] = heat

            cache.set(cache_key, result, self.ttl)
            return result

        except Exception as e:
            return {
                "error": str(e),
                "image": image_ref,
                "repo": repo,
                "current_tag": current_tag,
                "latest_tag": None,
                "digest_current": None,
                "digest_latest": None,
                "version_delta": None,
                "heat": 0,
            }

    def _compute_heat(self, current_tag, latest_tag, digest_current, digest_latest, update_available):
        # No update → cool
        if not update_available:
            return 0

        # If registry doesn't expose tags → assume cool
        if latest_tag is None:
            return 0

        # Semver path
        delta = version_delta(current_tag, latest_tag)
        if delta is not None:
            # Your version_delta already encodes magnitude; map to 0–3
            if delta >= 100:
                return 3  # major
            if delta >= 10:
                return 2  # minor
            if delta >= 1:
                return 1  # patch
            return 0

        # Non-semver path
        # Digest mismatch → hot
        if digest_current and digest_latest and digest_current != digest_latest:
            return 2

        # Tag mismatch but no digest → hot
        if current_tag != latest_tag:
            return 2

        # Default
        return 0

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def _split_image(self, image_ref):
        if not image_ref:
            return None, None

        if "@" in image_ref:
            image_ref = image_ref.split("@", 1)[0]

        last_slash = image_ref.rfind("/")
        last_colon = image_ref.rfind(":")

        if last_colon > last_slash:
            repo = image_ref[:last_colon]
            tag = image_ref[last_colon + 1:]
        else:
            repo = image_ref
            tag = "latest"

        return repo, tag

    def _detect_registry(self, repo):
        if repo.startswith("ghcr.io/"):
            return "ghcr"

        if repo.startswith("lscr.io/"):
            return "lscr"

        if "." in repo.split("/")[0]:
            return repo.split("/")[0]

        return "dockerhub"

    def _normalize(self, tag):
        return tag[1:] if tag.startswith("v") else tag

    def _select_latest_semver(self, tags):
        semver_tags = [t for t in tags if self.semver_re.match(t)]
        if not semver_tags:
            return None
        semver_tags.sort(key=lambda x: version.parse(self._normalize(x)))
        return semver_tags[-1]

    def _compute_delta(self, current, latest):
        if not current or not latest:
            return None

        if not self.semver_re.match(current) or not self.semver_re.match(latest):
            return None

        try:
            c = version.parse(self._normalize(current))
            l = version.parse(self._normalize(latest))
            return (l.major - c.major) * 100 + (l.minor - c.minor) * 10 + (l.micro - c.micro)
        except Exception:
            return None

    # ---------------------------------------------------------
    # Docker Hub
    # ---------------------------------------------------------

    def _poll_dockerhub(self, repo, current_tag):
        tags = []
        url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags?page_size=100"

        while url:
            r = requests.get(url, timeout=5)
            if r.status_code != 200:
                break

            data = r.json()
            tags.extend([t["name"] for t in data.get("results", [])])
            url = data.get("next")

        latest = self._select_latest_semver(tags) or (
            "latest" if "latest" in tags else (tags[0] if tags else current_tag)
        )
        delta = self._compute_delta(current_tag, latest)

        digest_current = self._fetch_dockerhub_digest(repo, current_tag)
        digest_latest = self._fetch_dockerhub_digest(repo, latest)

        return {
            "registry": "dockerhub",
            "repo": repo,
            "current_tag": current_tag,
            "latest_tag": latest,
            "digest_current": digest_current,
            "digest_latest": digest_latest,
            "version_delta": delta,
        }

    def _fetch_dockerhub_digest(self, repo, tag):
        try:
            url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags/{tag}"
            r = requests.get(url, timeout=5)
            if r.status_code != 200:
                return None
            data = r.json()
            return data.get("images", [{}])[0].get("digest")
        except Exception:
            return None

    # ---------------------------------------------------------
    # GHCR
    # ---------------------------------------------------------

    def _poll_ghcr(self, repo, current_tag):
        repo_path = repo.replace("ghcr.io/", "")

        tags_url = f"https://ghcr.io/v2/{repo_path}/tags/list"
        tags = requests.get(tags_url).json().get("tags", [])

        latest = self._select_latest_semver(tags) or (
            "latest" if "latest" in tags else (tags[0] if tags else current_tag)
        )
        delta = self._compute_delta(current_tag, latest)

        digest_current = self._fetch_ghcr_digest(repo_path, current_tag)
        digest_latest = self._fetch_ghcr_digest(repo_path, latest)

        return {
            "registry": "ghcr",
            "repo": repo,
            "current_tag": current_tag,
            "latest_tag": latest,
            "digest_current": digest_current,
            "digest_latest": digest_latest,
            "version_delta": delta,
        }

    def _fetch_ghcr_digest(self, repo_path, tag):
        try:
            url = f"https://ghcr.io/v2/{repo_path}/manifests/{tag}"
            r = requests.get(url, headers=self.OCI_ACCEPT)
            return r.headers.get("Docker-Content-Digest")
        except Exception:
            return None

    # ---------------------------------------------------------
    # lscr.io (LinuxServer.io)
    # ---------------------------------------------------------

    def _poll_lscr(self, repo, current_tag):
        repo_path = repo.replace("lscr.io/", "")

        tags = []
        url = f"https://lscr.io/v2/{repo_path}/tags/list?n=100"

        headers = {"Accept": "application/json"}

        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            tags = r.json().get("tags", [])

        # Rolling-tag aware
        latest = (
            "latest"
            if "latest" in tags
            else (tags[0] if tags else current_tag)
        )

        digest_current = self._fetch_lscr_digest(repo_path, current_tag)
        digest_latest = self._fetch_lscr_digest(repo_path, latest)

        return {
            "registry": "lscr",
            "repo": repo,
            "current_tag": current_tag,
            "latest_tag": latest,
            "digest_current": digest_current,
            "digest_latest": digest_latest,
            "version_delta": None,  # rolling tags → no semver delta
        }

    def _fetch_lscr_digest(self, repo_path, tag):
        try:
            url = f"https://lscr.io/v2/{repo_path}/manifests/{tag}"
            r = requests.get(url, headers=self.OCI_ACCEPT, timeout=5)
            return r.headers.get("Docker-Content-Digest")
        except Exception:
            return None

    # ---------------------------------------------------------
    # Private Registry
    # ---------------------------------------------------------

    def _poll_private(self, registry, repo, current_tag):
        repo_path = repo.split("/", 1)[1]
        base = f"https://{registry}/v2/{repo_path}"

        tags_url = f"{base}/tags/list"
        tags = requests.get(tags_url, verify=False).json().get("tags", [])

        latest = self._select_latest_semver(tags) or (
            "latest" if "latest" in tags else (tags[0] if tags else current_tag)
        )
        delta = self._compute_delta(current_tag, latest)

        digest_current = self._fetch_private_digest(base, current_tag)
        digest_latest = self._fetch_private_digest(base, latest)

        return {
            "registry": registry,
            "repo": repo,
            "current_tag": current_tag,
            "latest_tag": latest,
            "digest_current": digest_current,
            "digest_latest": digest_latest,
            "version_delta": delta,
        }

    def _fetch_private_digest(self, base, tag):
        try:
            url = f"{base}/manifests/{tag}"
            r = requests.get(url, headers=self.OCI_ACCEPT, verify=False)
            return r.headers.get("Docker-Content-Digest")
        except Exception:
            return None
