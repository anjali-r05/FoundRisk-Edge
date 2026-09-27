from flask import Blueprint, jsonify, request, abort

from app.models import db, Project, Document, Claim, Metric
from app.services.contradiction_engine import detect_contradictions

analysis_bp = Blueprint("analysis", __name__, url_prefix="/api/analysis")

METRIC_TYPES = ["revenue", "customer_count", "market_size"]


@analysis_bp.route("/summary", methods=["GET"])
def analysis_summary():
    project_id = request.args.get("project_id", type=int)
    if not project_id:
        abort(400, description="Query parameter 'project_id' is required.")
    project = db.session.get(Project, project_id)
    if not project:
        abort(404, description=f"Project {project_id} not found.")

    coverage = {}
    for metric_type in METRIC_TYPES:
        claims = Claim.query.join(Document).filter(
            Document.project_id == project_id,
            Claim.metric_type == metric_type,
        ).all()
        document_ids = {c.document_id for c in claims}
        high_confidence = [c for c in claims if c.confidence_label == "High"]
        latest_claim = max(claims, key=lambda c: c.created_at) if claims else None
        latest_metric = latest_claim.metric if latest_claim else None
        latest = None
        if latest_metric:
            latest = {
                "value": latest_metric.normalized_value,
                "original_value": latest_metric.original_value,
                "original_unit": latest_metric.original_unit,
                "currency": latest_metric.currency,
                "period": latest_metric.period_raw,
                "period_normalized": latest_metric.period_normalized,
                "source_location": latest_claim.source_location(),
                "document_id": latest_claim.document_id,
                "confidence_label": latest_claim.confidence_label,
            }
        coverage[metric_type] = {
            "observations": len(claims),
            "documents": len(document_ids),
            "high_confidence_observations": len(high_confidence),
            "latest": latest,
        }

    documents = Document.query.filter_by(project_id=project_id).all()
    document_intelligence_ready = any(d.status == "ready" for d in documents)
    metric_extraction_ready = any(coverage[m]["observations"] > 0 for m in METRIC_TYPES)
    evidence_provenance_ready = metric_extraction_ready  # provenance is captured alongside every claim

    return jsonify({
        "project_id": project_id,
        "metric_coverage": coverage,
        "readiness": {
            "document_intelligence": document_intelligence_ready,
            "metric_extraction": metric_extraction_ready,
            "evidence_provenance": evidence_provenance_ready,
            "contradiction_engine": "implemented — deterministic discrepancy review",
            "risk_engine": "implemented — evidence-linked rule-based findings",
        },
    }), 200


@analysis_bp.route("/contradictions", methods=["GET"])
def analysis_contradictions():
    project_id = request.args.get("project_id", type=int)
    if not project_id:
        abort(400, description="Query parameter 'project_id' is required.")
    project = db.session.get(Project, project_id)
    if not project:
        abort(404, description=f"Project {project_id} not found.")

    claims = (
        Claim.query.join(Document).filter(
            Document.project_id == project_id,
            Document.status == "ready",
            Claim.metric_type.in_(METRIC_TYPES),
        ).all()
    )
    ready_document_count = Document.query.filter_by(project_id=project_id, status="ready").count()
    result = detect_contradictions(claims, ready_document_count=ready_document_count)
    result["project_id"] = project_id
    return jsonify(result), 200
