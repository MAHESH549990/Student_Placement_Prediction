"""Small domain entities used across controllers and repositories."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    email: str
    password_hash: str
    role: str

    def public_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "role": self.role}


@dataclass(frozen=True)
class StudentFeatures:
    values: dict[str, Any]


@dataclass(frozen=True)
class Prediction:
    label: str
    probability: float
    confidence: float
    model_name: str
    demo_model: bool
