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

#UI Mode (Optional - Set to 'fun' by Default with Optional 'minimal' mode)
UI_MODE = os.getenv("DECKHAND_UI_MODE", "fun").lower()

# Database Path (Optional - Set to 'deckhand.db' by Default)
DATABASE_PATH = os.getenv("DATABASE_PATH", "deckhand.db")

# Session Secret Key (Optional - Randomly Generated if Not Set)
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

# TLS Verification (Optional - Set to 'false' by Default for Security)
SKIP_TLS_VERIFY = os.getenv("DECKHAND_SKIP_TLS_VERIFY", "false").lower() == "true"
