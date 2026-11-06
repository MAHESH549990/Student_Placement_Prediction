"""User persistence with unique email semantics."""
from pymongo.errors import PyMongoError
from flask import current_app
from threading import RLock

from ..extensions import mongo_database, mongo_configured
from ..services.errors import StorageUnavailable
from .json_store import read_list, write_list


class UserRepository:
    _index_ready = False
    _write_lock = RLock()

    def _db(self):
        if not mongo_configured():
            return None
        try:
            db = mongo_database()
            if not self._index_ready:
                db.users.create_index("email", unique=True)
                db.users.create_index("role", unique=True, partialFilterExpression={"role": "admin"}, name="single_admin_role")
                self.__class__._index_ready = True
            return db
        except PyMongoError as exc:
            raise StorageUnavailable() from exc

    def find_by_email(self, email):
        db = self._db()
        if db is not None:
            return db.users.find_one({"email": email})
        return next((row for row in read_list(current_app.config["USERS_PATH"]) if row.get("email") == email), None)

    def admin_exists(self):
        db = self._db()
        if db is not None:
            return db.users.count_documents({"role": "admin"}, limit=1) > 0
        return any(row.get("role") == "admin" for row in read_list(current_app.config["USERS_PATH"]))

    def create(self, user):
        db = self._db()
        if db is not None:
            try:
                db.users.insert_one(user)
            except PyMongoError as exc:
                if getattr(exc, "code", None) == 11000:
                    return False
                raise StorageUnavailable() from exc
            return True
        path = current_app.config["USERS_PATH"]
        with self._write_lock:
            users = read_list(path)
            if any(row.get("email") == user["email"] for row in users):
                return False
            if user.get("role") == "admin" and any(row.get("role") == "admin" for row in users):
                return False
            users.append(user)
            write_list(path, users)
            return True
