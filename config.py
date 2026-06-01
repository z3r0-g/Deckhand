#========================================
#Environment Variable Configuration
#========================================
#All configuration is loaded from environment variables.
#See .env.example for reference and copy to .env with your values.

# Dependencies
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

# Application Version
VERSION = os.getenv("APP_VERSION", "0.dev")

# Portainer Configuration (Optional if using Docker Socket)
PORTAINER_URL = os.getenv("PORTAINER_URL", "").rstrip("/")
PORTAINER_API_KEY = os.getenv("PORTAINER_API_KEY", "")

#UI Mode (Optional - Set to 'fun' by Default with Optional 'minimal' mode)
UI_MODE = os.getenv("DECKHAND_UI_MODE", "fun").lower()

# Database Path (Optional - Set to 'deckhand.db' by Default)
DATABASE_PATH = os.getenv("DATABASE_PATH", "deckhand.db")

# Session Secret Key (Optional - Randomly Generated if Not Set)
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
