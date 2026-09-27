"""
FoundRisk Edge — Flask application factory.

Phase 1: Document Intelligence only. No auth, no queues, no external AI APIs.
"""
import logging
import os

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from app.models import db
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
                      PERMANENT_SESSION_LIFETIME=60 * 60 * 8)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.dirname(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")) or ".", exist_ok=True)

    db.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.health import health_bp
    from app.routes.projects import projects_bp
    from app.routes.documents import documents_bp
    from app.routes.evidence import evidence_bp
    from app.routes.analysis import analysis_bp
    from app.routes.pages import pages_bp
    from app.routes.intelligence import intelligence_bp
    from app.routes.runtime import runtime_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(evidence_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(intelligence_bp)
    app.register_blueprint(runtime_bp)

    register_error_handlers(app)

    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO)

    with app.app_context():
        db.create_all()
        # Lightweight SQLite migration for existing local installations.
        try:
            columns = {row[1] for row in db.session.execute(db.text("PRAGMA table_info(projects)")).fetchall()}
            if "owner_id" not in columns:
                db.session.execute(db.text("ALTER TABLE projects ADD COLUMN owner_id INTEGER"))
                db.session.commit()
        except Exception:
            db.session.rollback()

    return app


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad_request", "message": _message(e, "The request was malformed.")}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found", "message": _message(e, "The requested resource was not found.")}), 404

    @app.errorhandler(413)
    @app.errorhandler(RequestEntityTooLarge)
    def too_large(e):
        max_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return jsonify({
            "error": "file_too_large",
            "message": f"Uploaded file exceeds the {max_mb} MB limit."
        }), 413

    @app.errorhandler(422)
    def unprocessable(e):
        return jsonify({"error": "unprocessable", "message": _message(e, "The request could not be processed.")}), 422

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server error")
        return jsonify({"error": "server_error", "message": "An internal error occurred. Details were logged server-side."}), 500

    @app.errorhandler(Exception)
    def unhandled(e):
        if isinstance(e, HTTPException):
            return e
        app.logger.exception("Unhandled exception")
        return jsonify({"error": "server_error", "message": "An internal error occurred. Details were logged server-side."}), 500


def _message(e, default):
    desc = getattr(e, "description", None)
    return desc if desc else default
