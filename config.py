import os

# ========================================
# Environment Variable Configuration
# ========================================
# All configuration is loaded from environment variables.
# See .env.example for reference and copy to .env with your values.

# UI Mode (optional)
UI_MODE = os.getenv("DECKHAND_UI_MODE", "fun").lower()

# Portainer Configuration (REQUIRED)
PORTAINER_URL = os.getenv("PORTAINER_URL", "")
PORTAINER_API_KEY = os.getenv("PORTAINER_API_KEY", "")

# Database Path (optional)
DATABASE_PATH = os.getenv("DATABASE_PATH", "deckhand.db")

# Flask Secret Key (optional, for security cookies)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production")

# Validate Required Configuration
if not PORTAINER_URL or not PORTAINER_API_KEY:
    import warnings
    warnings.warn(
        "PORTAINER_URL and PORTAINER_API_KEY must be set as environment variables. "
        "See .env.example for details.",
        RuntimeWarning
    )
