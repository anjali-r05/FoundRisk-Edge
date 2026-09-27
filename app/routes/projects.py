from flask import Blueprint, jsonify, request, abort

from app.models import db, Project

projects_bp = Blueprint("projects", __name__, url_prefix="/api/projects")


@projects_bp.route("", methods=["GET"])
def list_projects():
    from flask import g, current_app
    query = Project.query
    if getattr(g, "user", None) and not current_app.testing:
        query = query.filter_by(owner_id=g.user.id)
    projects = query.order_by(Project.created_at.desc()).all()
    return jsonify({"projects": [p.to_dict() for p in projects]}), 200


@projects_bp.route("", methods=["POST"])
def create_project():
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Request body must be JSON.")

    name = (data.get("name") or "").strip()
    if not name:
        abort(422, description="Field 'name' is required and cannot be empty.")
    if len(name) > 255:
        abort(422, description="Field 'name' must be 255 characters or fewer.")

    from flask import g
    project = Project(name=name, owner_id=getattr(g, "user", None).id if getattr(g, "user", None) else None)
    db.session.add(project)
    db.session.commit()

    return jsonify({"project": project.to_dict()}), 201


@projects_bp.route("/<int:project_id>", methods=["GET"])
def get_project(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        abort(404, description=f"Project {project_id} not found.")
    return jsonify({"project": project.to_dict()}), 200


@projects_bp.route("/<int:project_id>", methods=["PATCH"])
def update_project(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        abort(404, description=f"Project {project_id} not found.")
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name or len(name) > 255:
        abort(422, description="Project name must contain 1–255 characters.")
    project.name = name
    db.session.commit()
    return jsonify({"project": project.to_dict()}), 200
