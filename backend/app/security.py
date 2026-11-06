"""Request authentication and JWT helpers."""
from datetime import datetime, timedelta, timezone
from functools import wraps
import uuid

import jwt
from flask import current_app, g, jsonify, request


def issue_access_token(user):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user["id"]), "email": user["email"], "name": user["name"], "role": user["role"],
        "iat": now, "nbf": now, "exp": now + timedelta(seconds=current_app.config["JWT_TTL_SECONDS"]),
        "iss": current_app.config["JWT_ISSUER"], "aud": current_app.config["JWT_AUDIENCE"], "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, current_app.config["SECRET_KEY"], algorithm="HS256")


def require_user(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            scheme, separator, token = header.partition(" ")
            if scheme.lower() != "bearer" or not separator or not token.strip():
                return jsonify({"error": "Sign in to continue."}), 401
            try:
                claims = jwt.decode(
                    token.strip(), current_app.config["SECRET_KEY"], algorithms=["HS256"],
                    issuer=current_app.config["JWT_ISSUER"], audience=current_app.config["JWT_AUDIENCE"],
                    options={"require": ["sub", "email", "name", "role", "iat", "exp", "jti"]}, leeway=5,
                )
                if claims["role"] not in {"student", "admin"}:
                    raise jwt.InvalidTokenError("Unknown role")
            except (jwt.InvalidTokenError, KeyError, TypeError):
                return jsonify({"error": "Your session is invalid or expired. Please sign in again."}), 401
            g.user = {"id": claims["sub"], "email": claims["email"], "name": claims["name"], "role": claims["role"]}
            if role and g.user["role"] != role:
                return jsonify({"error": "You do not have permission to access this resource."}), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator
