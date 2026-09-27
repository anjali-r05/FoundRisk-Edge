import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Blueprint, current_app, render_template, request, redirect, url_for, session, flash, g, abort, jsonify
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db, User, Project, Document, Evidence, RiskFinding

auth_bp = Blueprint("auth", __name__)


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def csrf_ok(value):
    expected = session.get("csrf_token", "")
    return bool(expected and value and secrets.compare_digest(expected, value))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "user", None):
            if request.path.startswith("/api/"):
                return jsonify({"error": "authentication_required", "message": "Sign in to access your workspace."}), 401
            return redirect(url_for("auth.signin", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@auth_bp.app_context_processor
def inject_auth_globals():
    return {"csrf_token": csrf_token(), "current_user": getattr(g, "user", None)}


@auth_bp.before_app_request
def load_and_guard_user():
    g.user = None
    uid = session.get("user_id")
    if uid:
        g.user = db.session.get(User, uid)
        if g.user is None:
            session.clear()
    if current_app.testing and request.path.startswith("/api/"):
        return None
    endpoint = request.endpoint or ""
    public = endpoint in {"auth.landing", "auth.signup", "auth.signin", "auth.logout", "auth.csrf_refresh", "health.health", "static"}
    if not public and not g.user:
        if request.path.startswith("/api/"):
            return jsonify({"error": "authentication_required", "message": "Sign in to access your workspace."}), 401
        return redirect(url_for("auth.signin", next=request.path))
    if g.user and endpoint in {"auth.signin", "auth.signup"}:
        return redirect(url_for("pages.overview"))
    if request.method in {"POST", "PATCH", "PUT", "DELETE"} and request.path.startswith("/api/"):
        token = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
        if not csrf_ok(token):
            return jsonify({"error": "csrf_failed", "message": "Your security token is missing or out of date. The page will refresh its token and retry once."}), 400
    if g.user and request.path.startswith("/api/"):
        # Central ownership gate for any project/document/evidence/finding identifier.
        pid = request.view_args.get("project_id") if request.view_args else None
        pid = pid or request.args.get("project_id", type=int) or request.form.get("project_id", type=int)
        if pid is None and request.is_json:
            body = request.get_json(silent=True) or {}
            pid = body.get("project_id")
        if pid is not None:
            try: pid = int(pid)
            except (TypeError, ValueError): return jsonify({"error":"invalid_project_id","message":"Invalid project id."}), 400
            project = db.session.get(Project, pid)
            if not project or project.owner_id != g.user.id:
                return jsonify({"error":"not_found","message":"Project not found."}), 404
        args = request.view_args or {}
        if args.get("document_id") is not None:
            doc = db.session.get(Document, int(args["document_id"]))
            if not doc or not doc.project or doc.project.owner_id != g.user.id:
                return jsonify({"error":"not_found","message":"Document not found."}), 404
        if args.get("evidence_id") is not None:
            ev = db.session.get(Evidence, int(args["evidence_id"]))
            if not ev or not ev.project or ev.project.owner_id != g.user.id:
                return jsonify({"error":"not_found","message":"Evidence not found."}), 404
        if args.get("finding_id") is not None:
            finding = db.session.get(RiskFinding, int(args["finding_id"]))
            if not finding or not finding.project or finding.project.owner_id != g.user.id:
                return jsonify({"error":"not_found","message":"Finding not found."}), 404
        if args.get("snapshot_id") is not None:
            import json, os
            path = os.path.join(current_app.instance_path, "npu_snapshots", str(args["snapshot_id"]) + ".json")
            try:
                with open(path, encoding="utf-8") as f: snap = json.load(f)
                project = db.session.get(Project, int(snap.get("project_id", -1)))
            except (OSError, ValueError, TypeError):
                return jsonify({"error":"not_found","message":"Snapshot not found."}), 404
            if not project or project.owner_id != g.user.id:
                return jsonify({"error":"not_found","message":"Snapshot not found."}), 404


@auth_bp.get("/api/csrf-token")
def csrf_refresh():
    """Return the current session CSRF token so long-lived tabs can recover safely."""
    response = jsonify({"csrf_token": csrf_token(), "authenticated": bool(getattr(g, "user", None))})
    response.headers["Cache-Control"] = "no-store, private"
    return response, 200


@auth_bp.get("/")
def landing():
    return render_template("landing.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        if not csrf_ok(request.form.get("csrf_token")):
            flash("Your form session expired. Please try again.")
            return redirect(url_for("auth.signup"))
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not name or len(name) > 80 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
            flash("Enter a valid name and email address.")
        elif len(password) < 10 or len(password) > 256:
            flash("Use a password between 10 and 256 characters.")
        elif password != confirm:
            flash("Your passwords do not match.")
        elif User.query.filter(db.func.lower(User.email) == email).first():
            flash("An account with this email already exists. Please sign in.")
        else:
            user = User(name=name, email=email, password_hash=generate_password_hash(password))
            db.session.add(user); db.session.flush()
            # Preserve existing ownerless local projects for the first account only.
            if User.query.count() == 1:
                Project.query.filter(Project.owner_id.is_(None)).update({"owner_id": user.id})
            db.session.add(Project(name="My First Due Diligence", owner_id=user.id))
            db.session.commit()
            session.clear(); session["user_id"] = user.id; session["csrf_token"] = secrets.token_urlsafe(32); session.permanent = True
            flash("Your private workspace is ready.", "success")
            return redirect(url_for("pages.overview"))
    return render_template("auth_form.html", title="Create account", mode="signup", heading="Create your account", subheading="Set up your private FoundRisk Edge workspace.", side_title="Your diligence,<br><span>with clarity.</span>", side_copy="Create an account to organize evidence and review startup risk with greater transparency.")


@auth_bp.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        if not csrf_ok(request.form.get("csrf_token")):
            flash("Your form session expired. Please try again.")
            return redirect(url_for("auth.signin"))
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear(); session["user_id"] = user.id; session["csrf_token"] = secrets.token_urlsafe(32); session.permanent = True
            dest = request.args.get("next", "")
            if not dest.startswith("/") or dest.startswith("//"):
                dest = url_for("pages.overview")
            return redirect(dest)
        flash("Email or password is incorrect.")
    return render_template("auth_form.html", title="Sign in", mode="signin", heading="Welcome back", subheading="Sign in to continue to your workspace.", side_title="Good decisions<br>start with <span>good evidence.</span>", side_copy="Pick up your diligence workflow, review evidence trails, and keep your analysis organized in one private workspace.")


@auth_bp.post("/logout")
@login_required
def logout():
    if not csrf_ok(request.form.get("csrf_token")):
        flash("Your form session expired. Please try again.")
        return redirect(url_for("pages.overview"))
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.landing"))
