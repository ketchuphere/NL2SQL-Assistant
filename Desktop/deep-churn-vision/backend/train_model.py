"""
Customer Churn Prediction - Model Training Script
Dataset: Churn_Modelling.csv (Bank Customer Churn)
Model: Deep Neural Network using sklearn MLPClassifier
"""

import numpy as np
import pandas as pd
import joblib
import json
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import (
    accuracy_score, classification_report,
    confusion_matrix, roc_auc_score
)


# 1. LOAD & PREPROCESS DATA
print("=" * 60)
print("  CUSTOMER CHURN PREDICTION - TRAINING PIPELINE")
print("=" * 60)

csv_path = os.path.join(os.path.dirname(__file__), "Churn_Modelling.csv")
df = pd.read_csv(csv_path)
print(f"\n[1] Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns")

# Drop non-feature columns
df.drop(columns=["RowNumber", "CustomerId", "Surname"], inplace=True)

# One-hot encode categorical features (drop_first to avoid multicollinearity)
df = pd.get_dummies(df, columns=["Geography", "Gender"], drop_first=True)

print(f"    Features after encoding: {list(df.columns)}")

# Features & target
FEATURE_COLS = [c for c in df.columns if c != "Exited"]
X = df[FEATURE_COLS].values
y = df["Exited"].values

print(f"\n[2] Class distribution → Stayed: {(y==0).sum()}  Churned: {(y==1).sum()}")

# 2. TRAIN / TEST SPLIT
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"\n[3] Train size: {X_train.shape[0]}  |  Test size: {X_test.shape[0]}")


# 3. SCALE FEATURES
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s  = scaler.transform(X_test)


# 4. BUILD & TRAIN DEEP NEURAL NETWORK
print("\n[4] Training Deep Neural Network ...")
model = MLPClassifier(
    hidden_layer_sizes=(128, 64, 32),   # 3 hidden layers
    activation="relu",
    solver="adam",
    alpha=1e-4,                          # L2 regularisation
    batch_size=64,
    learning_rate="adaptive",
    learning_rate_init=0.001,
    max_iter=300,
    early_stopping=True,
    validation_fraction=0.1,
    n_iter_no_change=20,
    random_state=42,
    verbose=False,
)
model.fit(X_train_s, y_train)
print(f"    Training stopped at iteration: {model.n_iter_}")

# 5. EVALUATE
y_pred      = model.predict(X_test_s)
y_pred_prob = model.predict_proba(X_test_s)[:, 1]

acc    = accuracy_score(y_test, y_pred)
auc    = roc_auc_score(y_test, y_pred_prob)
report = classification_report(y_test, y_pred, target_names=["Stayed", "Churned"])
cm     = confusion_matrix(y_test, y_pred)

print("\n[5] EVALUATION RESULTS")
print(f"    Accuracy : {acc:.4f}  ({acc*100:.2f}%)")
print(f"    ROC-AUC  : {auc:.4f}")
print(f"\n{report}")
print(f"    Confusion Matrix:\n{cm}")


# 6. SAVE ARTIFACTS
os.makedirs(os.path.join(os.path.dirname(__file__), "artifacts"), exist_ok=True)
artifacts_dir = os.path.join(os.path.dirname(__file__), "artifacts")

joblib.dump(model,  os.path.join(artifacts_dir, "churn_model.pkl"))
joblib.dump(scaler, os.path.join(artifacts_dir, "scaler.pkl"))

# Save feature names & model metadata
metadata = {
    "feature_cols": FEATURE_COLS,
    "accuracy": round(acc, 4),
    "roc_auc":  round(auc, 4),
    "n_iter":   model.n_iter_,
    "architecture": list(model.hidden_layer_sizes),
    "class_names": ["Stayed", "Churned"],
    "train_size": int(X_train.shape[0]),
    "test_size":  int(X_test.shape[0]),
}
with open(os.path.join(artifacts_dir, "metadata.json"), "w") as f:
    json.dump(metadata, f, indent=2)

print(f"\n[6] Artifacts saved to → {artifacts_dir}/")
print("    ✓ churn_model.pkl")
print("    ✓ scaler.pkl")
print("    ✓ metadata.json")
print("\n✅ Training complete!\n")