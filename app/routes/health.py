from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "FoundRisk Edge",
        "phase": "Phase 1 — Document Intelligence",
    }), 200
