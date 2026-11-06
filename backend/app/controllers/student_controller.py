"""HTTP handlers for private student prediction records."""
from flask import Blueprint, g, jsonify, request

from ..extensions import limiter
from ..security import require_user
from ..services.errors import ValidationError
from ..services.student_service import StudentService

students = Blueprint("students", __name__, url_prefix="/api")
service = StudentService()


@students.get("/students")
@require_user()
@limiter.limit("120 per minute")
def list_students():
    try:
        limit = min(max(int(request.args.get("limit", 500)), 1), 5000)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    records = service.list_predictions(g.user, limit)
    return jsonify({"students": records, "total": len(records)})


@students.post("/predict")
@require_user()
@limiter.limit("60 per minute")
def predict():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send a JSON object containing student features."}), 400
    try:
        return jsonify(service.predict(payload))
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@students.post("/students")
@require_user()
@limiter.limit("30 per hour")
def create_student():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send a JSON object containing student features."}), 400
    try:
        return jsonify({"student": service.create_prediction(payload, g.user)}), 201
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
