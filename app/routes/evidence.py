from flask import Blueprint, jsonify, request, abort
from sqlalchemy import or_

from app.models import db, Project, Document, Evidence, Claim

evidence_bp = Blueprint("evidence", __name__, url_prefix="/api/evidence")


@evidence_bp.route("", methods=["GET"])
def list_evidence():
    project_id = request.args.get("project_id", type=int)
    metric_type = request.args.get("metric_type")  # revenue | customer_count | market_size
    confidence = request.args.get("confidence")     # High | Medium | Low
    search = request.args.get("q")

    if not project_id:
        abort(400, description="Query parameter 'project_id' is required.")
    if not db.session.get(Project, project_id):
        abort(404, description=f"Project {project_id} not found.")
    if metric_type and metric_type not in ("revenue", "customer_count", "market_size"):
        abort(422, description="Invalid metric_type. Must be one of: revenue, customer_count, market_size.")
    if confidence and confidence not in ("High", "Medium", "Low"):
        abort(422, description="Invalid confidence. Must be one of: High, Medium, Low.")

    query = (
        Evidence.query
        .join(Claim, Evidence.claim_id == Claim.id)
        .join(Document, Evidence.document_id == Document.id)
        .filter(Evidence.project_id == project_id)
    )

    if metric_type:
        query = query.filter(Claim.metric_type == metric_type)
    if confidence:
        query = query.filter(Evidence.confidence_label == confidence)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(or_(
            Evidence.evidence_text.ilike(like),
            Claim.raw_text.ilike(like),
            Document.filename.ilike(like),
            Claim.matched_keyword.ilike(like),
            Claim.metric_type.ilike(like),
            Claim.source_sheet.ilike(like),
            Claim.source_cell.ilike(like),
            Claim.source_column.ilike(like),
        ))

    items = query.order_by(Evidence.created_at.desc(), Evidence.id.desc()).all()
    return jsonify({"evidence": [e.to_dict() for e in items], "count": len(items)}), 200


@evidence_bp.route("/<int:evidence_id>", methods=["GET"])
def get_evidence(evidence_id):
    item = db.session.get(Evidence, evidence_id)
    if not item:
        abort(404, description=f"Evidence {evidence_id} not found.")

    claim = db.session.get(Claim, item.claim_id)
    data = item.to_dict()
    data["claim"] = claim.to_dict() if claim else None
    return jsonify({"evidence": data}), 200
