import os
import shutil

import pytest

from app import create_app
from app.models import db
from config import TestConfig


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        yield application
    upload_dir = application.config["UPLOAD_FOLDER"]
    if os.path.isdir(upload_dir):
        shutil.rmtree(upload_dir)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def project(app):
    from app.models import Project
    p = Project(name="Acme Technologies")
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture()
def sample_csv_path(tmp_path):
    path = tmp_path / "runtime_financials.csv"
    path.write_text(
        "Period,Revenue,Customers,Market Size\n"
        "FY2025,4.5 Cr,180,1200 Cr\n"
        "FY2026,8.2 Cr,340,1500 Cr\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture()
def sample_pdf_path(tmp_path):
    import fitz
    path = tmp_path / "runtime_pitch_deck.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "Acme Technologies — Investor Materials")
    page.insert_text((50, 105), "Revenue: ₹4.5 Cr in FY2025 and ₹8.2 Cr in FY2026")
    page.insert_text((50, 135), "Customer Count: 180 in FY2025 and 340 in FY2026")
    page.insert_text((50, 165), "Market Size: ₹1,200 Cr in FY2025 and ₹1,500 Cr in FY2026")
    doc.save(str(path))
    doc.close()
    return str(path)
