from flask import Flask, send_from_directory, render_template
import os
from dotenv import load_dotenv
# Load environment variables early so they are available to all modules
load_dotenv()

from urllib.parse import urlparse
import time

# Blueprint
from api.routes import api_blueprint

# DB + Scheduler
from services.database import init_db
from scheduler.scheduler import init_scheduler
from services.integrations import manager

# Deckhand Flask Application Factory
def create_app():
    # Use standard Flask directories: templates/ and static/
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Load config.py if present
    config_path = os.path.join(os.path.dirname(__file__), "config.py")
    if os.path.exists(config_path):
        app.config.from_pyfile("config.py")
    else:
        # Safe defaults + Environment Variables
        app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-change-in-production")
        app.config["DATABASE_PATH"] = os.getenv("DATABASE_PATH", "deckhand.db")
        app.config["PORTAINER_URL"] = os.getenv("PORTAINER_URL", "")
        app.config["PORTAINER_API_KEY"] = os.getenv("PORTAINER_API_KEY", "")
        app.config["UI_MODE"] = os.getenv("DECKHAND_UI_MODE", "fun")

    # Validate Integrations
    if not manager.is_configured():
        app.logger.error("No container orchestration providers (Portainer, Dockge, or Docker Socket) detected. "
                         "Please check your environment variables.")

    # Initialize SQLite database
    init_db(app)

    # Initialize APScheduler
    init_scheduler(app)

    # Register API routes
    app.register_blueprint(api_blueprint, url_prefix="/api")

    # Prevent caching of static assets and HTML
    @app.after_request
    def set_cache_headers(response):
        if response.content_type and any(ct in response.content_type for ct in ['text/html', 'application/javascript', 'text/css']):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, public, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    # Health check
    @app.get("/health")
    def health():
        return {
            "status": "ok", 
            "service": "deckhand", 
            "version": app.config.get("VERSION", "unknown")
        }
    
    @app.get("/")
    def deckhand_ui():
        ui_mode = app.config.get("UI_MODE", "fun")
        cache_bust = int(time.time())
        return render_template("deckhand.html", ui_mode=ui_mode, cache_bust=cache_bust)
    
    return app

# Local development entrypoint
if __name__ == "__main__":
    app = create_app()
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=debug_mode
    )
