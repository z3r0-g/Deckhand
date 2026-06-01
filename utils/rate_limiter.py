import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Per-registry rate limiting with exponential backoff.
    Tracks 429 responses and implements backoff strategy.
    """

    def __init__(self, max_backoff_seconds=60, recovery_minutes=60):
        self.max_backoff_seconds = max_backoff_seconds
        self.recovery_minutes = recovery_minutes
        self.registries = {}  # registry -> {"backoff_level": int, "last_429": time, "last_success": time}

    def _get_backoff_seconds(self, backoff_level):
        """Calculate backoff time for given level: 1s, 2s, 4s, 8s, etc."""
        seconds = min(2 ** backoff_level, self.max_backoff_seconds)
        return seconds

    def should_limit(self, registry_host):
        """Check if we should rate limit this registry."""
        if registry_host not in self.registries:
            return False

        state = self.registries[registry_host]
        backoff_level = state.get("backoff_level", 0)

        if backoff_level == 0:
            return False

        last_429 = state.get("last_429", 0)
        now = time.time()
        backoff_seconds = self._get_backoff_seconds(backoff_level)

        # Check if we're still in backoff window
        if (now - last_429) < backoff_seconds:
            return True

        # Check if we should reset backoff after recovery window
        last_success = state.get("last_success", 0)
        recovery_seconds = self.recovery_minutes * 60
        if last_success and (now - last_success) > recovery_seconds:
            logger.info(f"Rate limit recovery window expired for {registry_host}, resetting backoff")
            state["backoff_level"] = 0
            return False

        return True

    def get_wait_time(self, registry_host):
        """Get remaining wait time in seconds for this registry (0 if no limit)."""
        if registry_host not in self.registries:
            return 0

        state = self.registries[registry_host]
        backoff_level = state.get("backoff_level", 0)

        if backoff_level == 0:
            return 0

        last_429 = state.get("last_429", 0)
        now = time.time()
        backoff_seconds = self._get_backoff_seconds(backoff_level)
        wait_time = max(0, backoff_seconds - (now - last_429))

        return round(wait_time, 1)

    def record_429(self, registry_host):
        """Record a 429 rate limit response from registry."""
        if registry_host not in self.registries:
            self.registries[registry_host] = {
                "backoff_level": 0,
                "last_429": None,
                "last_success": None
            }

        state = self.registries[registry_host]
        state["last_429"] = time.time()
        state["backoff_level"] = min(state.get("backoff_level", 0) + 1, 6)  # Cap at 2^6 = 64s

        backoff_seconds = self._get_backoff_seconds(state["backoff_level"])
        logger.warning(
            f"Rate limited by {registry_host}: backoff_level={state['backoff_level']}, "
            f"waiting {backoff_seconds}s before retry"
        )

    def record_success(self, registry_host):
        """Record a successful request to registry."""
        if registry_host not in self.registries:
            self.registries[registry_host] = {
                "backoff_level": 0,
                "last_429": None,
                "last_success": None
            }

        state = self.registries[registry_host]
        state["last_success"] = time.time()

        # Decrement backoff level if not at zero
        if state.get("backoff_level", 0) > 0:
            state["backoff_level"] -= 1
            logger.debug(f"Registry {registry_host} success: backoff_level reduced to {state['backoff_level']}")

    def get_status(self, registry_host):
        """Get current status of a registry."""
        if registry_host not in self.registries:
            return {"status": "normal", "backoff_level": 0, "wait_time": 0}

        state = self.registries[registry_host]
        backoff_level = state.get("backoff_level", 0)

        if backoff_level == 0:
            status = "normal"
        elif backoff_level <= 2:
            status = "degraded"
        else:
            status = "severely_limited"

        return {
            "status": status,
            "backoff_level": backoff_level,
            "wait_time": self.get_wait_time(registry_host),
            "last_429": state.get("last_429"),
            "last_success": state.get("last_success")
        }

    def get_all_status(self):
        """Get status of all tracked registries."""
        return {host: self.get_status(host) for host in self.registries.keys()}


# Global rate limiter instance
rate_limiter = RateLimiter()
