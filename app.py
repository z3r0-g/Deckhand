from flask import Flask, send_from_directory, render_template
import os

# Blueprint
from api.routes import api_blueprint

# DB + Scheduler
from db.database import init_db
from scheduler.scheduler import init_scheduler

#Deckhand Flask Application Factory
def create_app():
    # Point template_folder to "web" so we can render deckhand.html and beszel.html
    app = Flask(__name__, template_folder="web")

    # Load config.py if present
    config_path = os.path.join(os.path.dirname(__file__), "config.py")
    if os.path.exists(config_path):
        app.config.from_pyfile("config.py")
    else:
        # Safe defaults
        app.config["SECRET_KEY"] = "dev"
        app.config["DATABASE_PATH"] = "deckhand.db"
        app.config["PORTAINER_URL"] = ""
        app.config["PORTAINER_API_KEY"] = ""

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
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
