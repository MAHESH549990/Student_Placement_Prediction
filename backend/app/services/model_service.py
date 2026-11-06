"""Machine-learning training, evaluation, and prediction."""
from datetime import datetime, timezone
import os
import threading

import joblib
import numpy as np
import pandas as pd
from flask import current_app
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from ..models.entities import Prediction
from .errors import ValidationError

FEATURES = ["cgpa", "tenth_percentage", "twelfth_percentage", "aptitude_score", "communication_score", "technical_skills", "projects", "internships", "backlogs", "degree"]
NUMERIC = FEATURES[:5] + FEATURES[6:9]
CATEGORICAL = ["technical_skills", "degree"]
_model_lock = threading.RLock()


def synthetic_demo_data(n=420, seed=21):
    """Reproducible synthetic data, clearly marked as illustrative."""
    rng = np.random.default_rng(seed)
    cgpa = np.clip(rng.normal(7.15, 1.0, n), 4, 10)
    tenth = np.clip(rng.normal(76, 11, n), 40, 100)
    twelfth = np.clip(rng.normal(73, 12, n), 40, 100)
    aptitude = np.clip(rng.normal(66, 17, n), 10, 100)
    communication = np.clip(rng.normal(68, 15, n), 15, 100)
    skills = rng.choice(["Python", "Java", "SQL", "JavaScript", "C++", "Data Science"], n)
    projects, internships = rng.integers(0, 6, n), rng.integers(0, 4, n)
    backlogs = rng.choice([0, 1, 2, 3], n, p=[.66, .20, .10, .04])
    degree = rng.choice(["Computer Science", "Information Technology", "Electronics", "Mechanical", "Business"], n)
    score = .68 * (cgpa - 6) + .018 * (aptitude - 50) + .012 * (communication - 50) + .32 * projects + .55 * internships + .008 * (tenth - 60) - .75 * backlogs + rng.normal(0, .8, n)
    return pd.DataFrame({"cgpa": cgpa, "tenth_percentage": tenth, "twelfth_percentage": twelfth, "aptitude_score": aptitude, "communication_score": communication, "technical_skills": skills, "projects": projects, "internships": internships, "backlogs": backlogs, "degree": degree, "placed": (score > 1.25).astype(int)})


def _target(values):
    mapping = {"1": 1, "true": 1, "yes": 1, "placed": 1, "0": 0, "false": 0, "no": 0, "not placed": 0, "not_placed": 0}
    return values.astype(str).str.strip().str.lower().map(mapping)


def _pipeline(estimator):
    transform = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler())]), NUMERIC),
        ("category", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL),
    ])
    return Pipeline([("preprocess", transform), ("model", estimator)])


class ModelService:
    def __init__(self, model_path=None):
        self.model_path = model_path

    def _path(self):
        return self.model_path or current_app.config["MODEL_PATH"]

    def train(self, frame, source):
        if "cgpa" not in frame.columns and "sgpa" in frame.columns:
            frame = frame.rename(columns={"sgpa": "cgpa"})
        target = _target(frame["placed"])
        valid = target.notna()
        frame, target = frame.loc[valid].copy(), target.loc[valid].astype(int)
        if len(frame) < 20 or target.nunique() != 2 or target.value_counts().min() < 2:
            raise ValidationError("Training requires at least 20 labeled rows and at least two examples of each outcome.")
        for column in FEATURES:
            if column not in frame:
                frame[column] = np.nan
        inputs = frame[FEATURES].copy()
        for column in NUMERIC:
            inputs[column] = pd.to_numeric(inputs[column], errors="coerce")
        x_train, x_test, y_train, y_test = train_test_split(inputs, target, test_size=.22, random_state=42, stratify=target)
        candidates = {
            "Logistic Regression": LogisticRegression(max_iter=1200, class_weight="balanced", random_state=42),
            "Decision Tree": DecisionTreeClassifier(max_depth=5, min_samples_leaf=4, class_weight="balanced", random_state=42),
        }
        scored = []
        for name, estimator in candidates.items():
            pipeline = _pipeline(estimator)
            pipeline.fit(x_train, y_train)
            prediction = pipeline.predict(x_test)
            f1 = f1_score(y_test, prediction, zero_division=0)
            metrics = {"accuracy": round(accuracy_score(y_test, prediction), 3), "precision": round(precision_score(y_test, prediction, zero_division=0), 3), "recall": round(recall_score(y_test, prediction, zero_division=0), 3), "f1": round(f1, 3)}
            scored.append((f1, name, pipeline, metrics))
        _, name, best, metrics = max(scored, key=lambda item: item[0])
        best.fit(inputs, target)
        artifact = {"pipeline": best, "name": name, "metrics": metrics, "trained_at": datetime.now(timezone.utc).isoformat(), "rows": int(len(frame)), "source": source, "placed_rate": round(float(target.mean()), 3)}
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        with _model_lock:
            joblib.dump(artifact, temp)
            os.replace(temp, path)
        return artifact

    def get_model(self):
        path = self._path()
        with _model_lock:
            if path.exists():
                return joblib.load(path)
        return self.train(synthetic_demo_data(), "Synthetic demo dataset")

    def predict(self, values):
        artifact = self.get_model()
        row = pd.DataFrame([values], columns=FEATURES)
        classes = list(artifact["pipeline"].classes_)
        probabilities = artifact["pipeline"].predict_proba(row)[0]
        placed_probability = float(probabilities[classes.index(1)])
        return Prediction("Placed" if placed_probability >= .5 else "Not Placed", round(placed_probability, 4), round(max(placed_probability, 1 - placed_probability), 4), artifact["name"], artifact["source"] == "Synthetic demo dataset")
