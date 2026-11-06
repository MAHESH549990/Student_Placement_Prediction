"""Placement Prediction application package."""
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from .config import Settings
from .extensions import init_extensions
from .routes import register_routes
from .services.errors import StorageUnavailable


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Settings)
    if test_config:
        app.config.update(test_config)
    init_extensions(app)
    register_routes(app)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store" if request_is_sensitive(response) else "no-cache")
        if app.config.get("ENVIRONMENT") == "production" and request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.errorhandler(StorageUnavailable)
    def storage_unavailable(error):
        app.logger.exception("Configured storage is unavailable")
        return jsonify({"error": "Database is temporarily unavailable. Please try again shortly."}), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify({"error": error.description}), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Unhandled request error")
        return jsonify({"error": "An unexpected server error occurred."}), 500

    return app


def request_is_sensitive(response):
    return response.mimetype == "application/json" and (response.status_code < 400)
