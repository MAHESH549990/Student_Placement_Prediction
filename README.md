# Student Placement Prediction System

A full-stack application for students to estimate placement readiness and for administrators to manage student predictions and train the model.

## Problem statement

Students often have limited, scattered feedback about how academics, skills, projects, internships, aptitude, and communication relate to placement readiness. Placement teams also need a consistent way to review student profiles and outcomes.

## Proposed solution

GradPath collects a student profile, estimates placement likelihood from a trained classification model, and presents practical next steps for improvement. Administrators can review saved estimates, model metrics, and retrain from labeled CSV data. Predictions are decision-support estimates, not guarantees of employment.

## Project objectives

- Give students a private place to check their placement readiness and see tailored improvement suggestions.
- Let administrators review saved student estimates and placement trends.
- Compare and evaluate machine-learning models using a consistent data-preparation workflow.
- Keep student and administrator access separate with authentication and role authorization.

## Overview

- **Student workspace:** Create an account, submit SGPA, 12th marks, aptitude, communication, technical skills, projects, internships, and backlogs. View an estimate and personalized recommendations in **Career plan**.
- **Admin workspace:** Review saved predictions and live outcome summaries, inspect model metrics, and upload a labeled CSV to retrain the model.
- **Machine learning:** Flask and scikit-learn compare Logistic Regression and Decision Tree models, evaluate them with accuracy, precision, recall, and F1, and calibrate prediction probabilities.
- **Storage and access:** MongoDB stores users and predictions when configured; local JSON is available for development. Passwords are hashed, and expiring JWTs and role-based authorization protect API routes.

The included `sample_synthetic_student_placement.csv` contains generated examples to try the upload flow. It is not real student history; predictions from it are illustrative and should not be used for placement decisions.

## Technology stack

| Layer | Technologies |
| --- | --- |
| Frontend | React, JavaScript, Vite, Lucide React, Recharts |
| Backend API | Python, Flask, Flask-CORS |
| Data and ML | Pandas, scikit-learn, joblib |
| Persistence | MongoDB with PyMongo; local JSON fallback for development |
| Security | PyJWT bearer tokens, Werkzeug password hashing, Flask-Limiter |
| Production server | Waitress; Redis-backed rate limiting is required in production |

## Model workflow

The API validates and cleans CSV data, imputes missing numeric and categorical features, scales numeric values, and one-hot encodes categories. It compares Logistic Regression and Decision Tree classifiers on a stratified holdout split, selects by F1 score, and calibrates the chosen model’s probabilities. Reported metrics include accuracy, precision, recall, and F1. Data quality and representative real outcomes matter more than model choice alone.

## Backend structure

The Flask API uses MVC-style layers: `app/routes.py` registers routes, `app/controllers/` handles HTTP, `app/services/` contains business and ML logic, `app/repositories/` handles persistence, `app/models/` defines domain entities, and `app/security.py` handles JWT authorization. Development uses Flask’s local server. Production mode uses Waitress and requires strong secrets plus a shared Redis rate-limit store.

## Run locally

Requirements: Python 3.10+, Node.js 18+.

```powershell
# Terminal 1 — API
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Replace the JWT_SECRET and ADMIN_BOOTSTRAP_KEY placeholders in backend/.env
python app.py

# Terminal 2 — web app
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally http://localhost:5173). The API defaults to http://localhost:5000. MongoDB connection settings and generated secrets are in `backend/.env`, which is excluded from Git. Student accounts can sign up directly. To create an administrator, expand **Administrator account setup** during signup and enter `ADMIN_BOOTSTRAP_KEY` from `backend/.env`; keep that code private. If MongoDB is unavailable, records use local JSON storage.

## CSV format

Required target column: `placed` (accepted values: `1/0`, `true/false`, `yes/no`, `placed/not placed`). Optional features: `cgpa`, `tenth_percentage`, `twelfth_percentage`, `aptitude_score`, `communication_score`, `technical_skills`, `projects`, `internships`, `backlogs`, and `degree`. Missing optional features are handled by the model pipeline. Upload at least 20 labeled records to retrain; the target column is never used as a prediction feature.

## API

- `POST /api/auth/signup`, `/api/auth/login`; authenticated `GET /api/auth/me`
- Admin-only: `GET /api/overview`, `/api/model/metrics`; `POST /api/data/upload`
- Authenticated: `GET /api/students`, `POST /api/predict`, `POST /api/students`
- Authenticated routes require `Authorization: Bearer <token>`.

## Future scope

- Validate predictions on larger, recent, real placement cohorts and monitor calibration and fairness across groups.
- Add explanations showing which profile factors contributed most to an estimate.
- Track student progress over time and refresh career recommendations as skills improve.
- Add dataset versioning, model comparison history, and placement-office reporting exports.

## Author

**Mahesh Bhatt**
