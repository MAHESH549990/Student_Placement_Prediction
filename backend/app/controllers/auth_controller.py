"""HTTP handlers for signup and login."""
from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import BadRequest

from ..extensions import limiter
from ..security import require_user
from ..services.auth_service import AuthService
from ..services.errors import StorageUnavailable, ValidationError

auth = Blueprint("auth", __name__, url_prefix="/api/auth")
service = AuthService()


def _payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Send a JSON object.")
    return data


@auth.post("/signup")
@limiter.limit("5 per hour")
def signup():
    try:
        return jsonify(service.signup(_payload())), 201
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except StorageUnavailable:
        raise


@auth.post("/login")
@limiter.limit("8 per minute")
def login():
    try:
        return jsonify(service.login(_payload()))
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except StorageUnavailable:
        raise


@auth.get("/me")
@require_user()
def me():
    from flask import g
    return jsonify({"user": g.user})
