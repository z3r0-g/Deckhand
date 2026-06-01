import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class ProviderHealth:
    """Tracks health status of a provider."""

    def __init__(self, provider_name, provider_type):
        self.provider_name = provider_name
        self.provider_type = provider_type
        self.last_success_time = None
        self.last_error_time = None
        self.last_error_message = None
        self.consecutive_failures = 0
        self.total_requests = 0
        self.successful_requests = 0

    def record_success(self):
        self.last_success_time = time.time()
        self.consecutive_failures = 0
        self.total_requests += 1
        self.successful_requests += 1

    def record_failure(self, error_message=None):
        self.last_error_time = time.time()
        self.last_error_message = error_message
        self.consecutive_failures += 1
        self.total_requests += 1

    def get_status(self):
        """Return status: healthy, degraded, or offline."""
        if self.consecutive_failures == 0:
            return "healthy"
        elif self.consecutive_failures <= 2:
            return "degraded"
        else:
            return "offline"

    def to_dict(self):
        return {
            "provider_name": self.provider_name,
            "provider_type": self.provider_type,
            "status": self.get_status(),
            "last_check": datetime.utcfromtimestamp(
                self.last_success_time or self.last_error_time or time.time()
            ).isoformat() + "Z" if self.last_success_time or self.last_error_time else None,
            "last_success": datetime.utcfromtimestamp(self.last_success_time).isoformat() + "Z"
            if self.last_success_time else None,
            "last_error": datetime.utcfromtimestamp(self.last_error_time).isoformat() + "Z"
            if self.last_error_time else None,
            "error_message": self.last_error_message,
            "consecutive_failures": self.consecutive_failures,
            "success_rate": (self.successful_requests / self.total_requests * 100)
            if self.total_requests > 0 else 0,
        }


class HealthMonitor:
    """Monitors health of all configured providers."""

    def __init__(self):
        self.providers = {}

    def register_provider(self, provider_name, provider_type):
        if provider_name not in self.providers:
            self.providers[provider_name] = ProviderHealth(provider_name, provider_type)

    def record_success(self, provider_name):
        if provider_name in self.providers:
            self.providers[provider_name].record_success()
            logger.debug(f"Provider {provider_name} health: success recorded")

    def record_failure(self, provider_name, error_message=None):
        if provider_name in self.providers:
            health = self.providers[provider_name]
            health.record_failure(error_message)
            status = health.get_status()
            logger.warning(
                f"Provider {provider_name} health: failure recorded (status={status}, "
                f"consecutive_failures={health.consecutive_failures}, error={error_message})"
            )

    def get_provider_status(self, provider_name):
        if provider_name in self.providers:
            return self.providers[provider_name].to_dict()
        return None

    def get_all_status(self):
        return {name: health.to_dict() for name, health in self.providers.items()}

    def is_healthy(self, provider_name):
        if provider_name in self.providers:
            return self.providers[provider_name].get_status() == "healthy"
        return False

    def get_healthy_providers(self):
        return [name for name, health in self.providers.items() if health.get_status() == "healthy"]

    def get_degraded_providers(self):
        return [name for name, health in self.providers.items() if health.get_status() == "degraded"]

    def get_offline_providers(self):
        return [name for name, health in self.providers.items() if health.get_status() == "offline"]


# Global health monitor instance
health_monitor = HealthMonitor()
