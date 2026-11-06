"""Student placement prediction API with an auditable sklearn pipeline."""
from __future__ import annotations

import json
import hmac
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
import jwt
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask import g
from flask_cors import CORS
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
MODEL_PATH = DATA_DIR / "model.joblib"
STUDENTS_PATH = DATA_DIR / "students.json"
USERS_PATH = DATA_DIR / "users.json"
JWT_SECRET = os.getenv("JWT_SECRET", "development-only-change-this-secret")
FEATURES = ["cgpa", "tenth_percentage", "twelfth_percentage", "aptitude_score", "communication_score", "technical_skills", "projects", "internships", "backlogs", "degree"]
NUMERIC = FEATURES[:5] + FEATURES[6:9]
CATEGORICAL = ["technical_skills", "degree"]
LOCK = threading.RLock()
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")}})


def demo_data(n=420, seed=21):
    """Reproducible synthetic demo data; never presented as real student records."""
    rng = np.random.default_rng(seed)
    cgpa = np.clip(rng.normal(7.15, 1.0, n), 4, 10)
    tenth = np.clip(rng.normal(76, 11, n), 40, 100)
    twelfth = np.clip(rng.normal(73, 12, n), 40, 100)
    aptitude = np.clip(rng.normal(66, 17, n), 10, 100)
    communication = np.clip(rng.normal(68, 15, n), 15, 100)
    skills = rng.choice(["Python", "Java", "SQL", "JavaScript", "C++", "Data Science"], n)
    projects = rng.integers(0, 6, n)
    internships = rng.integers(0, 4, n)
    backlogs = rng.choice([0, 1, 2, 3], n, p=[.66, .20, .10, .04])
    degree = rng.choice(["Computer Science", "Information Technology", "Electronics", "Mechanical", "Business"], n)
    score = .68 * (cgpa - 6) + .018 * (aptitude - 50) + .012 * (communication - 50) + .32 * projects + .55 * internships + .008 * (tenth - 60) - .75 * backlogs + rng.normal(0, .8, n)
    return pd.DataFrame({"cgpa": cgpa, "tenth_percentage": tenth, "twelfth_percentage": twelfth, "aptitude_score": aptitude, "communication_score": communication, "technical_skills": skills, "projects": projects, "internships": internships, "backlogs": backlogs, "degree": degree, "placed": (score > 1.25).astype(int)})


def parse_target(series):
    mapping = {"1": 1, "true": 1, "yes": 1, "placed": 1, "0": 0, "false": 0, "no": 0, "not placed": 0, "not_placed": 0}
    return series.astype(str).str.strip().str.lower().map(mapping)


def make_pipeline(model):
    pre = ColumnTransformer([
        ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler())]), NUMERIC),
        ("category", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL),
    ])
    return Pipeline([("preprocess", pre), ("model", model)])


def train(df, source):
    if "cgpa" not in df and "sgpa" in df: df = df.rename(columns={"sgpa": "cgpa"})
    y = parse_target(df["placed"])
    valid = y.notna()
    df, y = df.loc[valid].copy(), y.loc[valid].astype(int)
    if len(df) < 20 or y.nunique() != 2:
        raise ValueError("Training requires at least 20 valid rows with both placed and not placed outcomes.")
    for c in FEATURES:
        if c not in df: df[c] = np.nan
    X = df[FEATURES].copy()
    for col in NUMERIC:
        X[col] = pd.to_numeric(X[col], errors="coerce")
    stratify = y if y.value_counts().min() >= 2 else None
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=.22, random_state=42, stratify=stratify)
    candidates = {"Logistic Regression": LogisticRegression(max_iter=1200, class_weight="balanced", random_state=42), "Decision Tree": DecisionTreeClassifier(max_depth=5, min_samples_leaf=4, class_weight="balanced", random_state=42)}
    scored = []
    for name, estimator in candidates.items():
        pipe = make_pipeline(estimator)
        pipe.fit(Xtr, ytr)
        pred = pipe.predict(Xte)
        scored.append((f1_score(yte, pred, zero_division=0), name, pipe, {"accuracy": round(accuracy_score(yte, pred), 3), "precision": round(precision_score(yte, pred, zero_division=0), 3), "recall": round(recall_score(yte, pred, zero_division=0), 3), "f1": round(f1_score(yte, pred, zero_division=0), 3)}))
    _, name, chosen, metrics = max(scored, key=lambda item: item[0])
    chosen.fit(X, y)
    artifact = {"pipeline": chosen, "name": name, "metrics": metrics, "trained_at": datetime.now(timezone.utc).isoformat(), "rows": int(len(df)), "source": source, "placed_rate": round(float(y.mean()), 3)}
    joblib.dump(artifact, MODEL_PATH)
    return artifact


def get_model():
    with LOCK:
        if MODEL_PATH.exists(): return joblib.load(MODEL_PATH)
        return train(demo_data(), "Synthetic demo dataset")


def clean_record(doc):
    doc = dict(doc)
    if "_id" in doc: doc["id"] = str(doc.pop("_id"))
    if isinstance(doc.get("created_at"), datetime): doc["created_at"] = doc["created_at"].isoformat()
    return doc


def mongo_collection():
    uri = os.getenv("MONGO_URI", "").strip()
    if not uri: return None
    from pymongo import MongoClient
    client = MongoClient(uri, serverSelectionTimeoutMS=1500)
    client.admin.command("ping")
    return client[os.getenv("MONGO_DB", "placement_prediction")]["students"]


def mongo_db():
    uri = os.getenv("MONGO_URI", "").strip()
    if not uri: return None
    from pymongo import MongoClient
    client = MongoClient(uri, serverSelectionTimeoutMS=1500)
    client.admin.command("ping")
    return client[os.getenv("MONGO_DB", "placement_prediction")]


def auth_required(role=None):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            token = header.removeprefix("Bearer ").strip()
            if not token: return jsonify({"error": "Sign in to continue."}), 401
            try:
                claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
                g.user = {"id": claims["sub"], "email": claims["email"], "name": claims["name"], "role": claims["role"]}
            except (jwt.InvalidTokenError, KeyError):
                return jsonify({"error": "Your session is invalid or expired. Please sign in again."}), 401
            if role and g.user["role"] != role:
                return jsonify({"error": "You do not have permission to access this resource."}), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorate


def find_user(email):
    try:
        db = mongo_db()
        if db is not None: return db.users.find_one({"email": email})
    except Exception as exc:
        app.logger.warning("MongoDB users unavailable; using local fallback: %s", exc)
    users = json.loads(USERS_PATH.read_text()) if USERS_PATH.exists() else []
    return next((u for u in users if u["email"] == email), None)


def create_user(user):
    try:
        db = mongo_db()
        if db is not None:
            db.users.insert_one(user)
            return
    except Exception as exc:
        app.logger.warning("MongoDB users unavailable; using local fallback: %s", exc)
    users = json.loads(USERS_PATH.read_text()) if USERS_PATH.exists() else []
    users.append(user)
    USERS_PATH.write_text(json.dumps(users, indent=2))


def token_for(user):
    return jwt.encode({"sub": str(user["id"]), "email": user["email"], "name": user["name"], "role": user["role"], "exp": int(datetime.now(timezone.utc).timestamp()) + 60 * 60 * 12}, JWT_SECRET, algorithm="HS256")


def save_student(record):
    try:
        collection = mongo_collection()
        if collection is not None:
            collection.insert_one(record)
            return
    except Exception as exc:
        app.logger.warning("MongoDB unavailable; saving locally: %s", exc)
    existing = json.loads(STUDENTS_PATH.read_text()) if STUDENTS_PATH.exists() else []
    existing.insert(0, record)
    STUDENTS_PATH.write_text(json.dumps(existing[:10000], indent=2))


def list_students(limit=10000):
    try:
        collection = mongo_collection()
        if collection is not None: return [clean_record(x) for x in collection.find().sort("created_at", -1).limit(limit)]
    except Exception as exc:
        app.logger.warning("MongoDB unavailable; reading local records: %s", exc)
    return json.loads(STUDENTS_PATH.read_text())[:limit] if STUDENTS_PATH.exists() else []


@app.get("/api/health")
def health():
    m = get_model()
    return jsonify({"status": "ok", "model": m["name"], "source": m["source"]})


@app.post("/api/auth/signup")
def signup():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()[:100]
    email = str(payload.get("email", "")).strip().lower()[:254]
    password = str(payload.get("password", ""))
    if not name or "@" not in email or len(password) < 8:
        return jsonify({"error": "Enter your name, a valid email, and a password with at least 8 characters."}), 400
    try:
        if find_user(email): return jsonify({"error": "An account with this email already exists."}), 409
    except Exception as exc:
        app.logger.error("Account lookup failed: %s", exc)
        return jsonify({"error": "Could not reach account storage. Check MongoDB configuration."}), 503
    admin_code = str(payload.get("admin_code", ""))
    configured_key = os.getenv("ADMIN_BOOTSTRAP_KEY", "")
    role = "admin" if configured_key and hmac.compare_digest(admin_code, configured_key) else "student"
    user = {"id": str(uuid.uuid4()), "name": name, "email": email, "password_hash": generate_password_hash(password), "role": role, "created_at": datetime.now(timezone.utc).isoformat()}
    try:
        create_user(user)
    except Exception as exc:
        app.logger.error("Account creation failed: %s", exc)
        return jsonify({"error": "Could not create account. Check database connection."}), 503
    return jsonify({"token": token_for(user), "user": {k: user[k] for k in ("id", "name", "email", "role")}}), 201


@app.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    try: user = find_user(email)
    except Exception as exc:
        app.logger.error("Login lookup failed: %s", exc)
        return jsonify({"error": "Could not reach account storage. Check MongoDB configuration."}), 503
    if not user or not check_password_hash(user.get("password_hash", ""), password):
        return jsonify({"error": "Email or password is incorrect."}), 401
    return jsonify({"token": token_for(user), "user": {k: user[k] for k in ("id", "name", "email", "role")}})


@app.get("/api/auth/me")
@auth_required()
def auth_me():
    return jsonify({"user": g.user})


@app.get("/api/overview")
@auth_required("admin")
def overview():
    m, records = get_model(), list_students(10000)
    actual = len(records)
    placed = sum(1 for r in records if r.get("prediction") == "Placed")
    month_buckets = {}
    for rec in records:
        try:
            stamp = datetime.fromisoformat(rec["created_at"].replace("Z", "+00:00"))
            key = stamp.strftime("%Y-%m")
            bucket = month_buckets.setdefault(key, {"month": stamp.strftime("%b"), "placed": 0, "total": 0})
            bucket["total"] += 1
            bucket["placed"] += rec.get("prediction") == "Placed"
        except (KeyError, ValueError, TypeError): pass
    return jsonify({"total_students": actual, "placed_count": placed, "not_placed_count": actual - placed, "placed_rate": round(placed / actual, 3) if actual else 0, "model_accuracy": m["metrics"]["accuracy"], "students_scored": actual, "recent": records[:5], "monthly": [month_buckets[k] for k in sorted(month_buckets)][-12:], "source": m["source"], "training_rows": m["rows"]})


@app.get("/api/model/metrics")
@auth_required("admin")
def metrics():
    m = get_model()
    return jsonify({"name": m["name"], "metrics": m["metrics"], "trained_at": m["trained_at"], "rows": m["rows"], "source": m["source"]})


@app.get("/api/students")
@auth_required()
def students():
    try: limit = min(max(int(request.args.get("limit", 500)), 1), 5000)
    except ValueError: return jsonify({"error": "limit must be an integer"}), 400
    records = list_students(limit)
    if g.user["role"] != "admin": records = [r for r in records if r.get("user_id") == g.user["id"] or r.get("email") == g.user["email"]]
    return jsonify({"students": records, "total": len(records)})


def predict_payload(payload):
    values = {}
    for key in FEATURES:
        val = payload.get("sgpa", payload.get("cgpa")) if key == "cgpa" else payload.get(key)
        if key in NUMERIC and val not in (None, ""):
            try: val = float(val)
            except (TypeError, ValueError): raise ValueError(f"{key} must be numeric.")
        elif key in NUMERIC: val = np.nan
        values[key] = val if val not in (None, "") else np.nan
    bounds = {"cgpa": (0, 10), "tenth_percentage": (0, 100), "twelfth_percentage": (0, 100), "aptitude_score": (0, 100), "communication_score": (0, 100), "projects": (0, 100), "internships": (0, 100), "backlogs": (0, 100)}
    for key, (lo, hi) in bounds.items():
        if not pd.isna(values[key]) and not lo <= values[key] <= hi: raise ValueError(f"{key} must be between {lo} and {hi}.")
    return values


@app.post("/api/predict")
@auth_required()
def predict():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict): return jsonify({"error": "Send a JSON object containing student features."}), 400
    try:
        values = predict_payload(payload)
        m = get_model()
        row = pd.DataFrame([values], columns=FEATURES)
        proba = float(m["pipeline"].predict_proba(row)[0][1])
        return jsonify({"prediction": "Placed" if proba >= .5 else "Not Placed", "probability": round(proba, 4), "confidence": round(max(proba, 1 - proba), 4), "model": m["name"], "demo_model": m["source"] == "Synthetic demo dataset"})
    except ValueError as exc: return jsonify({"error": str(exc)}), 400


@app.post("/api/students")
@auth_required()
def create_student():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict): return jsonify({"error": "Send a JSON object containing student features."}), 400
    try:
        values = predict_payload(payload)
        m = get_model()
        p = float(m["pipeline"].predict_proba(pd.DataFrame([values]))[0][1])
        record = {"id": str(uuid.uuid4()), "user_id": g.user["id"], "email": g.user["email"], "name": g.user["name"], **{k: (None if pd.isna(v) else v) for k, v in values.items()}, "prediction": "Placed" if p >= .5 else "Not Placed", "probability": round(p, 4), "model": m["name"], "created_at": datetime.now(timezone.utc).isoformat()}
        save_student(record)
        return jsonify({"student": record}), 201
    except ValueError as exc: return jsonify({"error": str(exc)}), 400


@app.post("/api/data/upload")
@auth_required("admin")
def upload_data():
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".csv"): return jsonify({"error": "Upload a .csv file."}), 400
    try:
        df = pd.read_csv(file, nrows=10000)
        if "placed" not in df: return jsonify({"error": "CSV needs a 'placed' target column."}), 400
        with LOCK: m = train(df, f"Uploaded dataset ({file.filename[:80]})")
        return jsonify({"message": "Model retrained successfully.", "name": m["name"], "metrics": m["metrics"], "rows": m["rows"], "source": m["source"]})
    except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc: return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Dataset upload failed")
        return jsonify({"error": "Could not process the CSV. Check that feature columns contain usable values."}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
