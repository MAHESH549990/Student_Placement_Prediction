"""Student profile validation and prediction record use cases."""
from datetime import datetime, timezone
import math
import uuid

import numpy as np
from flask import current_app

from ..models.entities import StudentFeatures
from ..repositories.student_repository import StudentRepository
from .errors import ValidationError
from .model_service import FEATURES, NUMERIC, ModelService

BOUNDS = {"cgpa": (0, 10), "tenth_percentage": (0, 100), "twelfth_percentage": (0, 100), "aptitude_score": (0, 100), "communication_score": (0, 100), "projects": (0, 100), "internships": (0, 100), "backlogs": (0, 100)}
TEXT_LIMITS = {"technical_skills": 120, "degree": 120}


class StudentService:
    def __init__(self, students=None, models=None):
        self.students = students or StudentRepository()
        self.models = models or ModelService()

    def validate_features(self, payload):
        values = {}
        for key in FEATURES:
            raw = payload.get("sgpa", payload.get("cgpa")) if key == "cgpa" else payload.get(key)
            if raw in (None, ""):
                values[key] = np.nan
            elif key in NUMERIC:
                try:
                    number = float(raw)
                except (TypeError, ValueError) as exc:
                    raise ValidationError(f"{key} must be numeric.") from exc
                if not math.isfinite(number):
                    raise ValidationError(f"{key} must be a finite number.")
                low, high = BOUNDS[key]
                if not low <= number <= high:
                    raise ValidationError(f"{key} must be between {low} and {high}.")
                if key in {"projects", "internships", "backlogs"} and not number.is_integer():
                    raise ValidationError(f"{key} must be a whole number.")
                values[key] = number
            else:
                text = str(raw).strip()
                if len(text) > TEXT_LIMITS[key]:
                    raise ValidationError(f"{key} must be at most {TEXT_LIMITS[key]} characters.")
                values[key] = text or np.nan
        return StudentFeatures(values)

    def predict(self, payload):
        features = self.validate_features(payload)
        prediction = self.models.predict(features.values)
        return {"prediction": prediction.label, "probability": prediction.probability, "confidence": prediction.confidence, "model": prediction.model_name, "demo_model": prediction.demo_model}

    def create_prediction(self, payload, user):
        features = self.validate_features(payload)
        prediction = self.models.predict(features.values)
        record = {
            "id": str(uuid.uuid4()), "user_id": user["id"], "email": user["email"], "name": user["name"],
            **{key: None if (isinstance(value, float) and math.isnan(value)) else value for key, value in features.values.items()},
            "prediction": prediction.label, "probability": prediction.probability, "model": prediction.model_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.students.create(record)
        return record

    def list_predictions(self, user, limit):
        return self.students.list_for_user(user, limit)
