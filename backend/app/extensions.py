"""Shared service extensions: Mongo connection pool, CORS and rate limiting."""
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient

limiter = Limiter(key_func=get_remote_address, default_limits=[], headers_enabled=True)
_mongo_client = None
_mongo_uri = ""
_mongo_lock = None


def init_extensions(app):
    global _mongo_uri, _mongo_lock
    app.config["DATA_DIR"].mkdir(parents=True, exist_ok=True)
    CORS(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGINS"], "allow_headers": ["Content-Type", "Authorization"], "methods": ["GET", "POST", "OPTIONS"]}})
    limiter.init_app(app)
    _mongo_uri = app.config["MONGO_URI"]
    if _mongo_lock is None:
        from threading import RLock
        _mongo_lock = RLock()


def mongo_configured():
    return bool(_mongo_uri)


def mongo_database():
    global _mongo_client
    if not _mongo_uri:
        return None
    # Defer DNS resolution and connection work until a storage route is used.
    from pymongo.errors import PyMongoError
    from .services.errors import StorageUnavailable
    with _mongo_lock:
        if _mongo_client is None:
            try:
                _mongo_client = MongoClient(_mongo_uri, serverSelectionTimeoutMS=2500, connectTimeoutMS=2500, maxPoolSize=40, minPoolSize=1, retryWrites=True, appname="GradPathPlacementAPI")
            except PyMongoError as exc:
                raise StorageUnavailable() from exc
    from flask import current_app
    return _mongo_client[current_app.config["MONGO_DB"]]
