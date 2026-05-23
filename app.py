from flask import Flask, send_from_directory, render_template
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# Blueprint
from api.routes import api_blueprint

# DB + Scheduler
from db.database import init_db
from scheduler.scheduler import init_scheduler

#Deckhand Flask Application Factory
def create_app():
    # Load environment variables from .env file for local development
    load_dotenv()

    # Point template_folder to "web" so we can render deckhand.html and beszel.html
    app = Flask(__name__, template_folder="web")

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

    # Normalize and Validate Portainer URL
    p_url = app.config.get("PORTAINER_URL", "").strip()
    
    # Auto-prepend http:// if a scheme is missing (standard for homelabs)
    if p_url and "://" not in p_url:
        p_url = f"http://{p_url}"

    p_url = p_url.rstrip("/")
    parsed = urlparse(p_url)

    if p_url and not parsed.netloc:
        app.logger.warning(f"PORTAINER_URL '{p_url}' seems to be missing a hostname. Connectivity may fail.")
        app.config["PORTAINER_URL"] = ""
    else:
        app.config["PORTAINER_URL"] = p_url

    # Initialize SQLite database
    init_db(app)

    # Initialize APScheduler
    init_scheduler(app)

    # Register API routes
    app.register_blueprint(api_blueprint, url_prefix="/api")

    #Health check
    @app.get("/health")
    def health():
        return {"status": "ok", "service": "deckhand"}
    
    @app.get("/")
    def deckhand_ui():
        ui_mode = app.config.get("UI_MODE", "fun")
        return render_template("deckhand.html", ui_mode=ui_mode)

    @app.get("/web/<path:filename>")
    def deckhand_static(filename):
        web_root = os.path.join(app.root_path, "web")
        return send_from_directory(web_root, filename)

    @app.get("/beszel")
    def beszel_ui():
        beszel_url = os.getenv("BESZEL_URL", "http://beszel:8090")
        return render_template("beszel.html", beszel_url=beszel_url)

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
