"""Administrator dashboard and model management HTTP handlers."""
from pathlib import Path

import pandas as pd
from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from ..extensions import limiter
from ..repositories.student_repository import StudentRepository
from ..security import require_user
from ..services.errors import ValidationError
from ..services.model_service import ModelService

admin = Blueprint("admin", __name__, url_prefix="/api")
models = ModelService()
students = StudentRepository()


@admin.get("/health")
@limiter.exempt
def health():
    model = models.get_model()
    return jsonify({"status": "ok", "model": model["name"], "source": model["source"]})


@admin.get("/overview")
@require_user("admin")
def overview():
    model, summary = models.get_model(), students.dashboard_summary()
    total, placed = summary["total"], summary["placed"]
    return jsonify({"total_students": total, "placed_count": placed, "not_placed_count": total - placed, "placed_rate": round(placed / total, 3) if total else 0, "model_accuracy": model["metrics"]["accuracy"], "students_scored": total, "recent": summary["recent"], "monthly": summary["monthly"], "source": model["source"], "training_rows": model["rows"]})


@admin.get("/model/metrics")
@require_user("admin")
def metrics():
    model = models.get_model()
    return jsonify({"name": model["name"], "metrics": model["metrics"], "trained_at": model["trained_at"], "rows": model["rows"], "source": model["source"]})


@admin.post("/data/upload")
@require_user("admin")
@limiter.limit("5 per hour")
def upload_dataset():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"error": "Choose a CSV file to upload."}), 400
    filename = secure_filename(Path(upload.filename).name)
    if not filename.lower().endswith(".csv"):
        return jsonify({"error": "Upload a .csv file."}), 400
    try:
        frame = pd.read_csv(upload.stream, nrows=10001)
        if len(frame) > 10000:
            return jsonify({"error": "CSV files are limited to 10,000 rows."}), 413
        if "placed" not in frame.columns:
            return jsonify({"error": "CSV needs a 'placed' target column."}), 400
        model = models.train(frame, f"Uploaded dataset ({filename[:80]})")
        return jsonify({"message": "Model retrained successfully.", "name": model["name"], "metrics": model["metrics"], "rows": model["rows"], "source": model["source"]})
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        return jsonify({"error": f"Could not read the CSV: {str(exc)[:200]}"}), 400
