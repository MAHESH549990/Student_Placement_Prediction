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
        return {"prediction": prediction.label, "probability": prediction.probability, "confidence": prediction.confidence, "model": prediction.model_name, "demo_model": prediction.demo_model, "recommendations": self.recommendations(features.values, prediction.probability)}

    @staticmethod
    def recommendations(values, probability=None):
        items = []
        cgpa = values.get("cgpa")
        if isinstance(cgpa, (int, float)) and not math.isnan(cgpa) and cgpa < 7:
            items.append({"category": "Academics", "priority": "High", "title": "Strengthen your academic record", "detail": "Set weekly revision targets for core subjects and ask a faculty mentor to help you focus on the topics where you lose marks. Check the eligibility cutoffs for the roles you want."})
        projects = values.get("projects")
        if isinstance(projects, (int, float)) and not math.isnan(projects) and projects < 2:
            items.append({"category": "Projects", "priority": "High", "title": "Build a portfolio project", "detail": "Create one complete project that solves a practical problem. Publish the code, add a clear README, and prepare a short demo you can discuss in interviews."})
        internships = values.get("internships")
        if isinstance(internships, (int, float)) and not math.isnan(internships) and internships < 1:
            items.append({"category": "Experience", "priority": "High", "title": "Add practical experience", "detail": "Apply for internships, campus projects, or supervised client work. Describe your own contribution and the outcome, even if the work is small."})
        aptitude = values.get("aptitude_score")
        if isinstance(aptitude, (int, float)) and not math.isnan(aptitude) and aptitude < 70:
            items.append({"category": "Aptitude", "priority": "Medium", "title": "Practice aptitude a little each day", "detail": "Use short timed practice for quantitative, logical, and verbal questions. Review every mistake and repeat a weekly mock test to track progress."})
        communication = values.get("communication_score")
        if isinstance(communication, (int, float)) and not math.isnan(communication) and communication < 70:
            items.append({"category": "Communication", "priority": "Medium", "title": "Rehearse interview answers", "detail": "Practice a concise introduction and project walkthrough. Record a mock interview, then ask a peer or mentor for feedback on clarity and structure."})
        backlogs = values.get("backlogs")
        if isinstance(backlogs, (int, float)) and not math.isnan(backlogs) and backlogs > 0:
            items.append({"category": "Academics", "priority": "High", "title": "Make a backlog clearing plan", "detail": "List exam dates and topics, schedule study blocks, and meet your academic advisor early. Clearing pending papers can widen eligibility for campus roles."})
        skill = values.get("technical_skills")
        if not isinstance(skill, str) or not skill.strip():
            items.append({"category": "Skills", "priority": "Medium", "title": "Choose one role-focused technical skill", "detail": "Pick a skill that matches the roles you want, learn the fundamentals, and demonstrate it through a small working project."})
        if not items:
            if probability is not None and probability >= .8:
                items.append({"category": "Next steps", "priority": "Maintain", "title": "Turn your readiness into interviews", "detail": "Polish your resume, practice explaining your best project, and apply consistently to roles that match your skills."})
            else:
                items.append({"category": "Next steps", "priority": "Maintain", "title": "Keep building evidence of your skills", "detail": "Maintain your study routine, keep project work current, and practice interviews regularly. Recheck your profile as your experience grows."})
        return items[:5]

    def create_prediction(self, payload, user):
        features = self.validate_features(payload)
        prediction = self.models.predict(features.values)
        record = {
            "id": str(uuid.uuid4()), "user_id": user["id"], "email": user["email"], "name": user["name"],
            **{key: None if (isinstance(value, float) and math.isnan(value)) else value for key, value in features.values.items()},
            "prediction": prediction.label, "probability": prediction.probability, "model": prediction.model_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        record["recommendations"] = self.recommendations(features.values, prediction.probability)
        self.students.create(record)
        return record

    def list_predictions(self, user, limit):
        records = self.students.list_for_user(user, limit)
        for row in records:
            if not row.get("recommendations"):
                row["recommendations"] = self.recommendations(row, row.get("probability"))
        return records
