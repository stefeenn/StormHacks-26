"""View routes for rendering web interface pages."""

from flask import Blueprint, render_template

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
def index():
    """Render main application page."""
    return render_template("index.html")
