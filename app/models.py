"""
FoundRisk Edge — data model.

Exactly five entities in Phase 1, per spec: Project, Document, Claim, Metric, Evidence.
No contradiction/risk/copilot tables yet — those arrive in later phases and will
reference these by id, not modify them.
"""
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    documents = db.relationship("Document", backref="project", lazy="dynamic", cascade="all, delete-orphan")
    evidence_items = db.relationship("Evidence", backref="project", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "document_count": self.documents.count(),
        }


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)

    filename = db.Column(db.String(500), nullable=False)
    stored_path = db.Column(db.String(1000), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # pdf | csv | xlsx

    # uploaded -> parsing -> extracting -> normalizing -> indexing -> ready -> failed
    status = db.Column(db.String(30), nullable=False, default="uploaded")
    status_detail = db.Column(db.Text, nullable=True)  # human-readable error/info, e.g. "image-only PDF"

    page_count = db.Column(db.Integer, nullable=True)   # pages (PDF) or sheets (XLSX) or rows (CSV)
    processing_time_ms = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)

    claims = db.relationship("Claim", backref="document", lazy="dynamic", cascade="all, delete-orphan")
    evidence_items = db.relationship("Evidence", backref="document", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self, include_counts=True):
        data = {
            "id": self.id,
            "project_id": self.project_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "status": self.status,
            "status_detail": self.status_detail,
            "page_count": self.page_count,
            "processing_time_ms": self.processing_time_ms,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }
        if include_counts:
            data["claims_found"] = self.claims.count()
            data["metrics_found"] = Metric.query.join(Claim).filter(Claim.document_id == self.id).count()
            data["evidence_count"] = self.evidence_items.count()
        return data


class Claim(db.Model):
    """A candidate statement extracted from a document, before normalization."""
    __tablename__ = "claims"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)

    raw_text = db.Column(db.Text, nullable=False)          # the source sentence / cell / row text
    metric_type = db.Column(db.String(30), nullable=True)  # revenue | customer_count | market_size | None

    matched_keyword = db.Column(db.String(100), nullable=True)

    # extraction signal flags — the "why this was extracted" breakdown
    signal_keyword = db.Column(db.Boolean, default=False)
    signal_number = db.Column(db.Boolean, default=False)
    signal_unit = db.Column(db.Boolean, default=False)
    signal_period = db.Column(db.Boolean, default=False)

    confidence_score = db.Column(db.Float, nullable=False, default=0.0)   # 0.0 - 1.0, rule-based
    confidence_label = db.Column(db.String(10), nullable=False, default="Low")  # High | Medium | Low

    # provenance — never fabricated; see provenance.py
    source_page = db.Column(db.Integer, nullable=True)          # PDF page (1-indexed)
    source_sheet = db.Column(db.String(255), nullable=True)     # XLSX sheet name
    source_cell = db.Column(db.String(50), nullable=True)       # XLSX cell/range, e.g. "B14"
    source_row = db.Column(db.Integer, nullable=True)           # CSV row (1-indexed, incl. header)
    source_column = db.Column(db.String(100), nullable=True)    # CSV column name
    provenance_confidence = db.Column(db.String(10), nullable=False, default="high")  # high | low

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    metric = db.relationship("Metric", backref="claim", uselist=False, cascade="all, delete-orphan")
    evidence = db.relationship("Evidence", backref="claim", uselist=False, cascade="all, delete-orphan")

    def signals(self):
        return {
            "keyword": self.signal_keyword,
            "number": self.signal_number,
            "unit": self.signal_unit,
            "period": self.signal_period,
        }

    def source_location(self):
        """Human-readable source string — built only from fields actually captured."""
        if self.source_page is not None:
            return f"{self.document.filename}, page {self.source_page}"
        if self.source_sheet is not None:
            loc = f"{self.document.filename}, sheet: {self.source_sheet}"
            if self.source_cell:
                loc += f", cell: {self.source_cell}"
            return loc
        if self.source_row is not None:
            loc = f"{self.document.filename}, row {self.source_row}"
            if self.source_column:
                loc += f", column: {self.source_column}"
            return loc
        return f"{self.document.filename} (location unconfirmed)"

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "raw_text": self.raw_text,
            "metric_type": self.metric_type,
            "matched_keyword": self.matched_keyword,
            "signals": self.signals(),
            "confidence_score": round(self.confidence_score, 2),
            "confidence_label": self.confidence_label,
            "provenance_confidence": self.provenance_confidence,
            "source_location": self.source_location(),
            "source": {
                "page": self.source_page,
                "sheet": self.source_sheet,
                "cell": self.source_cell,
                "row": self.source_row,
                "column": self.source_column,
            },
        }


class Metric(db.Model):
    """The normalized numeric fact behind a Claim. One-to-one with Claim in Phase 1."""
    __tablename__ = "metrics"

    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claims.id"), nullable=False, unique=True)

    metric_type = db.Column(db.String(30), nullable=False)  # revenue | customer_count | market_size

    original_value = db.Column(db.String(50), nullable=False)   # as written, e.g. "4.2"
    original_unit = db.Column(db.String(20), nullable=True)     # "Cr", "Lakh", "M", "K", None
    normalized_value = db.Column(db.Float, nullable=False)      # absolute number, e.g. 42000000.0

    currency = db.Column(db.String(10), nullable=True)          # INR | USD | None (customer_count has none)
    period_raw = db.Column(db.String(50), nullable=True)        # "FY25", "Q1 2026", as written
    period_normalized = db.Column(db.String(20), nullable=True) # "FY2025" canonical form, if resolvable

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "metric_type": self.metric_type,
            "original_value": self.original_value,
            "original_unit": self.original_unit,
            "normalized_value": self.normalized_value,
            "currency": self.currency,
            "period_raw": self.period_raw,
            "period_normalized": self.period_normalized,
        }


class Evidence(db.Model):
    """Display/citation object surfaced in the Evidence Explorer and (later) Copilot."""
    __tablename__ = "evidence"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    claim_id = db.Column(db.Integer, db.ForeignKey("claims.id"), nullable=False, unique=True)
    metric_id = db.Column(db.Integer, db.ForeignKey("metrics.id"), nullable=True)

    evidence_text = db.Column(db.Text, nullable=False)       # short excerpt shown on the card
    source_location = db.Column(db.String(500), nullable=False)
    confidence_label = db.Column(db.String(10), nullable=False)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    metric = db.relationship("Metric", foreign_keys=[metric_id])

    def to_dict(self):
        metric = self.metric
        return {
            "id": self.id,
            "project_id": self.project_id,
            "document_id": self.document_id,
            "claim_id": self.claim_id,
            "metric_id": self.metric_id,
            "metric_type": metric.metric_type if metric else None,
            "value": metric.normalized_value if metric else None,
            "original_value": metric.original_value if metric else None,
            "original_unit": metric.original_unit if metric else None,
            "currency": metric.currency if metric else None,
            "period": metric.period_raw if metric else None,
            "evidence_text": self.evidence_text,
            "source_location": self.source_location,
            "document_filename": self.document.filename if self.document else None,
            "document_status": self.document.status if self.document else None,
            "claim_text": self.claim.raw_text if self.claim else None,
            "source": {
                "page": self.claim.source_page if self.claim else None,
                "sheet": self.claim.source_sheet if self.claim else None,
                "cell": self.claim.source_cell if self.claim else None,
                "row": self.claim.source_row if self.claim else None,
                "column": self.claim.source_column if self.claim else None,
                "provenance_confidence": self.claim.provenance_confidence if self.claim else None,
            },
            "confidence_label": self.confidence_label,
        }


class RiskFinding(db.Model):
    """Persistent, traceable rule-based due-diligence finding."""
    __tablename__ = "risk_findings"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    finding_key = db.Column(db.String(220), nullable=False)
    title = db.Column(db.String(220), nullable=False)
    category = db.Column(db.String(60), nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    impact = db.Column(db.Text, nullable=False)
    recommendation = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.String(20), nullable=False, default="Medium")
    status = db.Column(db.String(20), nullable=False, default="open")
    evidence_json = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("project_id", "finding_key", name="uq_project_finding_key"),)

    def to_dict(self):
        import json
        try: evidence = json.loads(self.evidence_json or "[]")
        except (TypeError, ValueError): evidence = []
        return {"id": self.id, "project_id": self.project_id, "finding_key": self.finding_key,
                "title": self.title, "category": self.category, "severity": self.severity,
                "summary": self.summary, "impact": self.impact, "recommendation": self.recommendation,
                "confidence": self.confidence, "status": self.status, "evidence": evidence,
                "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat()}
