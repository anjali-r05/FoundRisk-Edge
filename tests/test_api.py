import io
import json

from app.models import db


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_create_and_list_projects(client):
    res = client.post("/api/projects", json={"name": "Beta Startup"})
    assert res.status_code == 201
    project_id = res.get_json()["project"]["id"]

    res = client.get("/api/projects")
    assert res.status_code == 200
    names = [p["name"] for p in res.get_json()["projects"]]
    assert "Beta Startup" in names

    res = client.get(f"/api/projects/{project_id}")
    assert res.status_code == 200


def test_create_project_missing_name_returns_422(client):
    res = client.post("/api/projects", json={})
    assert res.status_code == 422


def test_get_nonexistent_project_returns_404(client):
    res = client.get("/api/projects/999999")
    assert res.status_code == 404


def test_upload_requires_project_id(client):
    data = {"file": (io.BytesIO(b"a,b\n1,2\n"), "test.csv")}
    res = client.post("/api/documents", data=data, content_type="multipart/form-data")
    assert res.status_code == 400


def test_upload_rejects_unsupported_extension(client, project):
    data = {"project_id": str(project.id), "file": (io.BytesIO(b"not code"), "script.exe")}
    res = client.post("/api/documents", data=data, content_type="multipart/form-data")
    assert res.status_code == 422


def test_upload_to_nonexistent_project_returns_404(client):
    data = {"project_id": "999999", "file": (io.BytesIO(b"a,b\n1,2\n"), "test.csv")}
    res = client.post("/api/documents", data=data, content_type="multipart/form-data")
    assert res.status_code == 404


def test_upload_csv_and_process_full_pipeline(client, project, sample_csv_path):
    with open(sample_csv_path, "rb") as f:
        data = {"project_id": str(project.id), "file": (f, "demo_financials.csv")}
        res = client.post("/api/documents", data=data, content_type="multipart/form-data")
    assert res.status_code == 201
    document_id = res.get_json()["document"]["id"]
    assert res.get_json()["document"]["status"] == "uploaded"

    res = client.post(f"/api/documents/{document_id}/process")
    assert res.status_code == 200
    doc = res.get_json()["document"]
    assert doc["status"] == "ready"
    assert doc["claims_found"] > 0
    assert doc["evidence_count"] > 0

    res = client.get(f"/api/evidence?project_id={project.id}")
    assert res.status_code == 200
    evidence = res.get_json()["evidence"]
    assert len(evidence) > 0
    assert all(e["source_location"] for e in evidence)


def test_upload_pdf_and_process_full_pipeline(client, project, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        data = {"project_id": str(project.id), "file": (f, "demo_pitch_deck.pdf")}
        res = client.post("/api/documents", data=data, content_type="multipart/form-data")
    document_id = res.get_json()["document"]["id"]

    res = client.post(f"/api/documents/{document_id}/process")
    doc = res.get_json()["document"]
    assert doc["status"] == "ready"
    assert doc["claims_found"] > 0

    res = client.get(f"/api/evidence?project_id={project.id}&metric_type=revenue")
    assert res.status_code == 200
    evidence = res.get_json()["evidence"]
    assert all(e["metric_type"] == "revenue" for e in evidence)


def test_process_nonexistent_document_returns_404(client):
    res = client.post("/api/documents/999999/process")
    assert res.status_code == 404


def test_evidence_requires_project_id(client):
    res = client.get("/api/evidence")
    assert res.status_code == 400


def test_evidence_invalid_metric_type_returns_422(client, project):
    res = client.get(f"/api/evidence?project_id={project.id}&metric_type=not_a_real_metric")
    assert res.status_code == 422


def test_analysis_summary_requires_project_id(client):
    res = client.get("/api/analysis/summary")
    assert res.status_code == 400


def test_analysis_summary_shape(client, project):
    res = client.get(f"/api/analysis/summary?project_id={project.id}")
    assert res.status_code == 200
    body = res.get_json()
    assert set(body["metric_coverage"].keys()) == {"revenue", "customer_count", "market_size"}
    assert body["readiness"]["contradiction_engine"].startswith("implemented")
    assert body["readiness"]["risk_engine"].startswith("implemented")


def test_evidence_search_filters_by_text(client, project, sample_csv_path):
    with open(sample_csv_path, "rb") as f:
        data = {"project_id": str(project.id), "file": (f, "demo_financials.csv")}
        res = client.post("/api/documents", data=data, content_type="multipart/form-data")
    document_id = res.get_json()["document"]["id"]
    client.post(f"/api/documents/{document_id}/process")

    res = client.get(f"/api/evidence?project_id={project.id}&q=Revenue")
    assert res.status_code == 200
    evidence = res.get_json()["evidence"]
    assert len(evidence) > 0
    assert all(
        "Revenue" in (e.get("evidence_text") or "")
        or "Revenue" in (e.get("document_filename") or "")
        or "Revenue" in (e.get("claim_text") or "")
        or "revenue" in (e.get("metric_type") or "")
        for e in evidence
    )
    assert all("document_filename" in e and "source" in e for e in evidence)

    # Searching a source filename should return its evidence records too.
    by_filename = client.get(f"/api/evidence?project_id={project.id}&q=demo_financials.csv")
    assert by_filename.status_code == 200
    assert len(by_filename.get_json()["evidence"]) > 0


def test_get_evidence_detail_includes_claim_signals(client, project, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        data = {"project_id": str(project.id), "file": (f, "demo_pitch_deck.pdf")}
        res = client.post("/api/documents", data=data, content_type="multipart/form-data")
    document_id = res.get_json()["document"]["id"]
    client.post(f"/api/documents/{document_id}/process")

    res = client.get(f"/api/evidence?project_id={project.id}")
    evidence_id = res.get_json()["evidence"][0]["id"]

    res = client.get(f"/api/evidence/{evidence_id}")
    assert res.status_code == 200
    detail = res.get_json()["evidence"]
    assert "claim" in detail
    assert "signals" in detail["claim"]
    assert "source_location" in detail["claim"]
    assert detail.get("document_filename") == "demo_pitch_deck.pdf"
    assert "source" in detail and "claim_text" in detail



def test_csrf_refresh_endpoint_returns_current_session_token(client):
    response = client.get("/api/auth/csrf-token")
    assert response.status_code == 200
    body = response.get_json()
    assert body["csrf_token"]
    assert response.headers["Cache-Control"] == "no-store, private"


def test_risk_findings_refresh_returns_actionable_empty_workspace_finding(client, project):
    response = client.post(f"/api/intelligence/risks?project_id={project.id}", json={"project_id": project.id})
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] >= 1
    assert body["counts"]["open"] >= 1
    assert body["findings"][0]["title"]


def test_copilot_returns_project_state_instead_of_empty_response(client, project):
    response = client.post("/api/intelligence/copilot", json={"project_id": project.id, "question": "What revenue was found?"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["answer"]
    assert body["mode"] == "empty_project"
