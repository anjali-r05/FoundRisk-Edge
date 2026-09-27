import os
import time
import uuid

from flask import Blueprint, current_app, jsonify, request, abort
from werkzeug.utils import secure_filename

from app.models import db, Project, Document, Claim, Evidence, Metric
from app.services import document_parser
from app.services import evidence_service

documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def _allowed_file(filename):
    if "." not in filename:
        return False, None
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_EXTENSIONS"], ext


@documents_bp.route("", methods=["GET"])
def list_documents():
    project_id = request.args.get("project_id", type=int)
    query = Document.query
    if project_id is not None:
        if not db.session.get(Project, project_id):
            abort(404, description=f"Project {project_id} not found.")
        query = query.filter_by(project_id=project_id)
    documents = query.order_by(Document.created_at.desc()).all()
    return jsonify({"documents": [d.to_dict() for d in documents]}), 200


@documents_bp.route("", methods=["POST"])
def upload_document():
    project_id = request.form.get("project_id", type=int)
    if not project_id:
        abort(400, description="Form field 'project_id' is required.")

    project = db.session.get(Project, project_id)
    if not project:
        abort(404, description=f"Project {project_id} not found.")

    if "file" not in request.files:
        abort(400, description="No file part in the request.")

    file = request.files["file"]
    if file.filename == "":
        abort(400, description="No file selected.")

    allowed, ext = _allowed_file(file.filename)
    if not allowed:
        abort(422, description=f"Unsupported file type '{ext or 'unknown'}'. Supported: pdf, csv, xlsx.")

    safe_name = secure_filename(file.filename)
    if not safe_name:
        abort(422, description="Filename is invalid.")

    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    stored_path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name)

    try:
        file.save(stored_path)
    except Exception as exc:
        current_app.logger.exception("Failed to save uploaded file")
        abort(500, description="Could not save the uploaded file.")

    document = Document(
        project_id=project_id,
        filename=safe_name,
        stored_path=stored_path,
        file_type=ext,
        status="uploaded",
    )
    db.session.add(document)
    db.session.commit()

    return jsonify({"document": document.to_dict()}), 201


@documents_bp.route("/<int:document_id>", methods=["GET"])
def get_document(document_id):
    document = db.session.get(Document, document_id)
    if not document:
        abort(404, description=f"Document {document_id} not found.")
    return jsonify({"document": document.to_dict()}), 200


@documents_bp.route("/<int:document_id>/process", methods=["POST"])
def process_document(document_id):
    document = db.session.get(Document, document_id)
    if not document:
        abort(404, description=f"Document {document_id} not found.")

    if not os.path.exists(document.stored_path):
        document.status = "failed"
        document.status_detail = "Stored file is missing on disk."
        db.session.commit()
        abort(422, description="Stored file is missing on disk.")

    start = time.monotonic()
    document.status = "parsing"
    db.session.commit()

    try:
        result = document_parser.parse_document(document.stored_path, document.file_type)
    except Exception as exc:
        current_app.logger.exception("Parsing failed for document %s", document_id)
        document.status = "failed"
        document.status_detail = "Unexpected error during parsing. Details were logged server-side."
        db.session.commit()
        abort(500, description="Unexpected error during document processing.")

    document.page_count = result.page_count

    if result.status == "failed":
        document.status = "failed"
        document.status_detail = result.status_detail
        db.session.commit()
        return jsonify({"document": document.to_dict(), "message": result.status_detail}), 200

    if result.status == "empty":
        document.status = "empty"
        document.status_detail = result.status_detail
        db.session.commit()
        return jsonify({"document": document.to_dict(), "message": result.status_detail}), 200

    document.status = "extracting"
    db.session.commit()

    document.status = "normalizing"
    db.session.commit()

    document.status = "indexing"
    db.session.commit()

    # Re-processing must replace the document's previous extraction output.
    # This makes fixes to deterministic extraction immediately testable without
    # accumulating stale evidence records.
    old_claims = Claim.query.filter_by(document_id=document.id).all()
    for old_claim in old_claims:
        db.session.delete(old_claim)
    db.session.flush()

    counts = evidence_service.persist_candidates(document, result.claims)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    document.processing_time_ms = elapsed_ms
    document.status = "ready"
    document.status_detail = result.status_detail
    from datetime import datetime, timezone
    document.processed_at = datetime.now(timezone.utc)
    db.session.commit()

    # Refresh the risk queue immediately after a successful processing run.
    # The Risks page also refreshes on demand, but this keeps persisted findings
    # and Copilot context synchronized with the latest extracted claims.
    try:
        from app.services.risk_engine import refresh_findings
        refresh_findings(document.project_id)
    except Exception:
        current_app.logger.exception("Risk finding refresh failed for document %s", document_id)

    response = document.to_dict()
    response.update(counts)
    response["ocr_pages"] = getattr(result, "ocr_pages", 0)
    return jsonify({"document": response}), 200
