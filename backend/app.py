import os

from flask import Flask, send_from_directory

from db import init_db
from routes.demand import bp as demand_bp
from seed import seed_if_empty

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")


def create_app():
    app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path="")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

    init_db(app)
    app.register_blueprint(demand_bp)

    with app.app_context():
        seed_if_empty()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    # Serve the built frontend (Vite `dist/`) in production. In dev, the Vite dev server
    # handles the UI and proxies /api/* to this Flask process instead.
    @app.get("/")
    @app.get("/<path:path>")
    def serve_frontend(path=""):
        if path and os.path.exists(os.path.join(FRONTEND_DIST, path)):
            return send_from_directory(FRONTEND_DIST, path)
        index_path = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(FRONTEND_DIST, "index.html")
        return (
            "Good Plan backend is running, but no built frontend was found at "
            f"{FRONTEND_DIST}. Run `npm run build` in frontend/, or use `npm run dev` "
            "for local development (Vite dev server on its own port).",
            200,
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8093, debug=True)
