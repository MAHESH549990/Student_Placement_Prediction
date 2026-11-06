# Student Placement Prediction

A student placement system with separate student and administrator workspaces, backed by Flask and scikit-learn. Students can create accounts, enter SGPA, marks, skills, projects, internships and aptitude details, and view their private saved estimates. Administrators see live totals calculated from saved predictions and can upload datasets to train the model. MongoDB is configured in `backend/.env`; local JSON is used as a storage fallback. Without a supplied dataset, model metrics and predictions use a reproducible **synthetic demo dataset** and are illustrative, not validated for real placement decisions.

## Run locally

Requirements: Python 3.10+, Node.js 18+.

```powershell
# Terminal 1 — API
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
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
