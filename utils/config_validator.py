import os
import requests
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    pass


class ConfigValidator:
    def __init__(self):
        self.validation_results = {}
        self.provider_configs = self._collect_provider_configs()

    def _collect_provider_configs(self):
        """Collect all provider configurations from environment variables."""
        providers = {
            "portainer": {"env_url": "PORTAINER_URL", "env_key": "PORTAINER_API_KEY"},
            "dockge": {"env_url": "DOCKGE_URL", "env_key": "DOCKGE_API_KEY"},
            "docker": {"env_url": "DOCKER_HOST", "env_key": None},
            "arcane": {"env_url": "ARCANE_URL", "env_key": "ARCANE_API_KEY"},
            "dockhand": {"env_url": "DOCKHAND_URL", "env_key": "DOCKHAND_API_KEY"},
        }

        configs = {}
        for provider_name, keys in providers.items():
            for i in range(11):  # Support 0-10 numbered instances
                if i == 0:
                    url_key = keys["env_url"]
                    key_key = keys["env_key"]
                else:
                    url_key = f"{keys['env_url'].split('_')[0]}_{i}_{keys['env_url'].split('_')[1]}"
                    key_key = f"{keys['env_key'].split('_')[0]}_{i}_{keys['env_key'].split('_')[1]}" if keys["env_key"] else None

                url = os.getenv(url_key, "").strip()
                if url:
                    instance_name = f"{provider_name}" if i == 0 else f"{provider_name}_{i}"
                    configs[instance_name] = {
                        "name": instance_name,
                        "provider": provider_name,
                        "url": url,
                        "api_key_env": key_key,
                        "api_key": os.getenv(key_key, "").strip() if key_key else None,
                    }

        return configs

    def validate_url(self, url):
        """Validate URL format."""
        try:
            result = urlparse(url)
            return result.scheme in ("http", "https") and result.netloc
        except Exception:
            return False

    def test_connectivity(self, provider_name, url, api_key=None):
        """Test provider connectivity with appropriate health endpoints."""
        timeout = 5
        headers = {}

        try:
            if provider_name == "portainer":
                if not api_key:
                    return False, "Missing API key"
                headers["X-API-Key"] = api_key
                test_url = f"{url}/api/status"

            elif provider_name == "dockge":
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                test_url = f"{url}/api/version"

            elif provider_name == "docker":
                # Skip connectivity test for Docker (might be socket)
                return True, "Docker socket/endpoint detected"

            elif provider_name == "arcane":
                if api_key:
                    headers["X-Arcane-Key"] = api_key
                test_url = f"{url}/health"

            elif provider_name == "dockhand":
                if api_key:
                    headers["X-Api-Key"] = api_key
                test_url = f"{url}/health"

            else:
                return False, f"Unknown provider: {provider_name}"

            response = requests.get(test_url, headers=headers, timeout=timeout, verify=False)
            if response.status_code in (200, 401, 403):
                return True, "Connected"
            else:
                return False, f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection refused"
        except Exception as e:
            return False, str(e)

    def validate(self):
        """Run all validations and return results."""
        self.validation_results = {
            "config_errors": [],
            "providers": {},
        }

        if not self.provider_configs:
            self.validation_results["config_errors"].append("No providers configured in environment variables")
            logger.warning("No container orchestration providers detected in environment variables")
            return self.validation_results

        # Validate each provider
        valid_count = 0
        for instance_name, config in self.provider_configs.items():
            provider = config["provider"]
            url = config["url"]
            api_key = config["api_key"]

            result = {
                "name": instance_name,
                "provider": provider,
                "url": url,
                "status": "error",
                "message": "",
            }

            # Check URL format
            if not self.validate_url(url):
                result["status"] = "error"
                result["message"] = "Invalid URL format"
                self.validation_results["providers"][instance_name] = result
                continue

            # Check API key if required
            if provider != "docker" and config["api_key_env"] and not api_key:
                result["status"] = "error"
                result["message"] = f"Missing API key ({config['api_key_env']})"
                self.validation_results["providers"][instance_name] = result
                continue

            # Test connectivity
            success, message = self.test_connectivity(provider, url, api_key)
            if success:
                result["status"] = "validated"
                result["message"] = message
                valid_count += 1
            else:
                result["status"] = "unreachable"
                result["message"] = message

            self.validation_results["providers"][instance_name] = result

        # Log summary
        total = len(self.provider_configs)
        logger.info(f"Configuration validation complete: {valid_count}/{total} providers available")

        for instance_name, result in self.validation_results["providers"].items():
            if result["status"] == "validated":
                logger.info(f"  ✓ {instance_name} ({result['provider']}) - {result['message']}")
            else:
                logger.warning(f"  ✗ {instance_name} ({result['provider']}) - {result['message']}")

        return self.validation_results

    def get_validated_providers(self):
        """Get list of successfully validated provider instances."""
        if not self.validation_results:
            self.validate()
        return [
            (name, config) for name, config in self.validation_results["providers"].items()
            if config["status"] == "validated"
        ]

    def has_valid_providers(self):
        """Check if at least one provider is validated."""
        return len(self.get_validated_providers()) > 0
