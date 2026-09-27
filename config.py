"""
FoundRisk Edge — configuration.

Phase 1 (Document Intelligence) only. No AI/ML model config lives here yet —
that arrives with the Phase 3 embedding/NPU work.
"""
import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _persistent_secret_key():
    """Prefer an environment secret; persist a local fallback across app restarts."""
    configured = os.environ.get("FOUNDRISK_SECRET_KEY") or os.environ.get("SECRET_KEY")
    if configured:
        return configured
    instance_dir = os.path.join(BASE_DIR, "instance")
    os.makedirs(instance_dir, exist_ok=True)
    key_path = os.path.join(instance_dir, ".secret_key")
    try:
        with open(key_path, "r", encoding="utf-8") as handle:
            existing = handle.read().strip()
        if existing:
            return existing
    except OSError:
        pass
    generated = secrets.token_urlsafe(48)
    try:
        with open(key_path, "x", encoding="utf-8") as handle:
            handle.write(generated)
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        return generated
    except FileExistsError:
        with open(key_path, "r", encoding="utf-8") as handle:
            return handle.read().strip()


class Config:
    SECRET_KEY = _persistent_secret_key()

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "FOUNDRISK_DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'foundrisk.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.environ.get("FOUNDRISK_UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
    ALLOWED_EXTENSIONS = {"pdf", "csv", "xlsx"}
    MAX_CONTENT_LENGTH = int(os.environ.get("FOUNDRISK_MAX_UPLOAD_MB", 20)) * 1024 * 1024  # 20 MB default


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "tests", "_tmp_uploads")
