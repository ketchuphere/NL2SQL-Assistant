"""
Customer Churn Prediction API
FastAPI Backend — serves the React frontend + prediction API
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, validator
import numpy as np
import joblib
import json
import os

# Load model artifacts
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")

model  = joblib.load(os.path.join(ARTIFACTS_DIR, "churn_model.pkl"))
scaler = joblib.load(os.path.join(ARTIFACTS_DIR, "scaler.pkl"))
with open(os.path.join(ARTIFACTS_DIR, "metadata.json")) as f:
    metadata = json.load(f)

FEATURE_COLS = metadata["feature_cols"]


# FastAPI app
app = FastAPI(
    title="Customer Churn Prediction API",
    description="Deep Neural Network model to predict bank customer churn",
    version="1.0.0",
)

# Allow all origins (covers Vite dev server on :8080 + any other client)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Schemas
class CustomerInput(BaseModel):
    credit_score:     int   = Field(..., ge=300, le=900)
    geography:        str
    gender:           str
    age:              int   = Field(..., ge=18, le=100)
    tenure:           int   = Field(..., ge=0,  le=10)
    balance:          float = Field(..., ge=0)
    num_of_products:  int   = Field(..., ge=1,  le=4)
    has_cr_card:      int   = Field(..., ge=0,  le=1)
    is_active_member: int   = Field(..., ge=0,  le=1)
    estimated_salary: float = Field(..., ge=0)

    @validator("geography")
    def validate_geography(cls, v):
        if v not in {"France", "Germany", "Spain"}:
            raise ValueError("geography must be France, Germany or Spain")
        return v

    @validator("gender")
    def validate_gender(cls, v):
        if v not in {"Male", "Female"}:
            raise ValueError("gender must be Male or Female")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "credit_score": 619, "geography": "France", "gender": "Female",
                "age": 42, "tenure": 2, "balance": 0.0, "num_of_products": 1,
                "has_cr_card": 1, "is_active_member": 1, "estimated_salary": 101348.88,
            }
        }


class PredictionResponse(BaseModel):
    churn_probability: float
    prediction:        str
    risk_level:        str
    confidence:        float
    key_factors:       list[str]
    model_accuracy:    float
    model_roc_auc:     float


# Helpers
def build_feature_vector(inp: CustomerInput) -> np.ndarray:
    raw = {
        "CreditScore":       inp.credit_score,
        "Age":               inp.age,
        "Tenure":            inp.tenure,
        "Balance":           inp.balance,
        "NumOfProducts":     inp.num_of_products,
        "HasCrCard":         inp.has_cr_card,
        "IsActiveMember":    inp.is_active_member,
        "EstimatedSalary":   inp.estimated_salary,
        "Geography_Germany": 1 if inp.geography == "Germany" else 0,
        "Geography_Spain":   1 if inp.geography == "Spain"   else 0,
        "Gender_Male":       1 if inp.gender    == "Male"    else 0,
    }
    return np.array([raw[c] for c in FEATURE_COLS], dtype=float).reshape(1, -1)


def get_risk_level(prob: float) -> str:
    if prob < 0.3:  return "Low"
    if prob < 0.65: return "Medium"
    return "High"


def get_key_factors(inp: CustomerInput, prob: float) -> list[str]:
    factors = []
    if inp.is_active_member == 0:
        factors.append("Inactive member — high churn indicator")
    if inp.num_of_products >= 3:
        factors.append("3+ products linked — unusual, often churns")
    if inp.balance > 100_000:
        factors.append("Balance over €100k — higher churn tendency")
    if inp.geography == "Germany":
        factors.append("Germany geography has higher churn rate")
    if inp.credit_score < 500:
        factors.append("Low credit score increases churn likelihood")
    if inp.age > 50:
        factors.append("Age above 50 increases churn risk")
    if inp.tenure <= 1:
        factors.append("Very short tenure — customer still settling")
    # Protective signals
    if inp.is_active_member == 1 and inp.tenure >= 5:
        factors.append("Active member with long tenure — loyal customer")
    if inp.credit_score >= 750:
        factors.append("High credit score — financially stable customer")
    if inp.num_of_products == 2:
        factors.append("2 products — optimal engagement level")
    if inp.geography == "Spain":
        factors.append("Spain geography shows strong retention rate")
    return factors[:4] if factors else ["No significant risk factors identified"]



# API Routes  (declared BEFORE static mount)
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": "Deep Neural Network (MLP 128→64→32)",
        "accuracy": metadata["accuracy"],
        "roc_auc":  metadata["roc_auc"],
    }


@app.get("/model-info")
async def model_info():
    return {
        "model_type":   "Multi-Layer Perceptron (Deep Neural Network)",
        "architecture": metadata["architecture"],
        "performance":  {"accuracy": metadata["accuracy"], "roc_auc": metadata["roc_auc"]},
        "features":     FEATURE_COLS,
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict(customer: CustomerInput):
    try:
        X        = build_feature_vector(customer)
        X_scaled = scaler.transform(X)
        probs    = model.predict_proba(X_scaled)[0]
        churn_p  = float(probs[1])
        stay_p   = float(probs[0])

        return PredictionResponse(
            churn_probability = round(churn_p, 4),
            prediction        = "Churn" if churn_p >= 0.5 else "Stay",
            risk_level        = get_risk_level(churn_p),
            confidence        = round(max(churn_p, stay_p), 4),
            key_factors       = get_key_factors(customer, churn_p),
            model_accuracy    = metadata["accuracy"],
            model_roc_auc     = metadata["roc_auc"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/batch")
async def predict_batch(customers: list[CustomerInput]):
    if len(customers) > 100:
        raise HTTPException(status_code=400, detail="Batch limit is 100")
    results = []
    for c in customers:
        X    = build_feature_vector(c)
        prob = float(model.predict_proba(scaler.transform(X))[0][1])
        results.append({
            "churn_probability": round(prob, 4),
            "prediction":  "Churn" if prob >= 0.5 else "Stay",
            "risk_level":  get_risk_level(prob),
        })
    return {"count": len(results), "results": results}


# Serve built React frontend (production mode)
#
# After cloning, run inside the frontend/ folder:
#   npm install && npm run build
# This creates frontend/dist/ which FastAPI then serves.
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    # Serve /assets/* (Vite output: JS bundles, CSS, images)
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    # Catch-all: serve index.html for any path so React Router works
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        candidate = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

else:
    @app.get("/")
    async def root():
        return {
            "message": "ChurnScope API is running.",
            "docs": "/docs",
            "predict_endpoint": "POST /predict",
            "note": (
                "To serve the UI, run `npm install && npm run build` "
                "inside the frontend/ folder, then restart this server."
            ),
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
