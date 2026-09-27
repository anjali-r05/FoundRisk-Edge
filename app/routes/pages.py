from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/overview")
def overview():
    return render_template("overview.html", active_page="overview")


@pages_bp.route("/documents")
def documents_page():
    return render_template("documents.html", active_page="documents")


@pages_bp.route("/analysis")
def analysis_page():
    return render_template("analysis.html", active_page="analysis")


@pages_bp.route("/contradictions")
def contradictions_page():
    return render_template("contradictions.html", active_page="contradictions")


@pages_bp.route("/evidence")
def evidence_page():
    return render_template("evidence.html", active_page="evidence")


@pages_bp.route("/risks")
def risks_page():
    return render_template("risks.html", active_page="risks")

@pages_bp.route("/copilot")
def copilot_page():
    return render_template("copilot.html", active_page="copilot")


@pages_bp.route("/benchmarks")
def benchmarks_page():
    return render_template("benchmarks.html", active_page="benchmarks")


@pages_bp.route("/settings")
def settings_page():
    return render_template("settings.html", active_page="settings")
