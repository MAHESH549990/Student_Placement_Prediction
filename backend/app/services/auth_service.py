"""Authentication use cases and account policy."""
import hmac
import re
import uuid
from datetime import datetime, timezone

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from ..repositories.user_repository import UserRepository
from ..security import issue_access_token
from .errors import ValidationError

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthService:
    def __init__(self, users=None):
        self.users = users or UserRepository()

    def signup(self, payload):
        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        if not name or len(name) > 100 or not EMAIL_RE.fullmatch(email) or len(email) > 254:
            raise ValidationError("Enter a valid name and email address.")
        if len(password) < 12 or len(password) > 128:
            raise ValidationError("Password must be between 12 and 128 characters.")
        if self.users.find_by_email(email):
            raise ValidationError("An account with this email already exists.", status_code=409)
        admin_code = str(payload.get("admin_code", ""))
        configured_key = current_app.config["ADMIN_BOOTSTRAP_KEY"]
        role = "student"
        if admin_code:
            if not configured_key or not hmac.compare_digest(admin_code, configured_key):
                raise ValidationError("The administrator setup code is invalid.", status_code=403)
            if self.users.admin_exists():
                raise ValidationError("Administrator setup has already been completed.", status_code=403)
            role = "admin"
        user = {"id": str(uuid.uuid4()), "name": name, "email": email, "password_hash": generate_password_hash(password, method="scrypt"), "role": role, "created_at": datetime.now(timezone.utc).isoformat()}
        if not self.users.create(user):
            raise ValidationError("An account with this email already exists.", status_code=409)
        return {"token": issue_access_token(user), "user": {k: user[k] for k in ("id", "name", "email", "role")}}

    def login(self, payload):
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        password_within_limit = len(password) <= 128
        if not password_within_limit:
            password = password[:128]
        # Perform a password hash even for unknown emails to reduce account-enumeration timing leaks.
        user = self.users.find_by_email(email) if EMAIL_RE.fullmatch(email) else None
        valid_hash = user.get("password_hash", "") if user else generate_password_hash("dummy-password-for-timing", method="scrypt")
        if not check_password_hash(valid_hash, password) or not user or not password_within_limit:
            raise ValidationError("Email or password is incorrect.", status_code=401)
        return {"token": issue_access_token(user), "user": {k: user[k] for k in ("id", "name", "email", "role")}}
