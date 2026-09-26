import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from datetime import date
from extensions import db
from models import InventoryItem, StockMovement

def build_training_dataframe():
    items = InventoryItem.query.all()
    rows = []
    for item in items:
        movements = StockMovement.query.filter_by(item_id=item.id).all()
        issues = [m for m in movements if m.movement_type == "Issue"]
        total_issued = sum(m.quantity for m in issues)
        reorder_count = len([m for m in movements if m.movement_type == "Receive"])
        avg_daily_issue = total_issued / 180 if total_issued else 0
        days_left = (item.expiry_date - date.today()).days

        # Derived label: risk of expiring unused, based on whether
        # projected consumption before expiry covers current stock
        projected_use = avg_daily_issue * max(days_left, 0)
        wasted = 1 if projected_use < item.quantity * 0.5 else 0

        rows.append({
            "item_id": item.id,
            "days_left": days_left,
            "quantity": item.quantity,
            "avg_daily_issue": avg_daily_issue,
            "reorder_count": reorder_count,
            "department": item.department or "Unknown",
            "wasted_label": wasted
        })
    return pd.DataFrame(rows)

def train_risk_model():
    df = build_training_dataframe()
    df = pd.get_dummies(df, columns=["department"])

    feature_cols = [c for c in df.columns if c not in ("item_id", "wasted_label")]
    X = df[feature_cols]
    y = df["wasted_label"]

    if len(df) < 10 or y.nunique() < 2:
        return None, None, "Not enough varied data to train yet. Add more items/history."

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    accuracy = accuracy_score(y_test, preds)
    report = classification_report(y_test, preds, zero_division=0)

    return model, feature_cols, {"accuracy": accuracy, "report": report}

def predict_risk_for_item(model, feature_cols, item):
    movements = StockMovement.query.filter_by(item_id=item.id).all()
    issues = [m for m in movements if m.movement_type == "Issue"]
    total_issued = sum(m.quantity for m in issues)
    reorder_count = len([m for m in movements if m.movement_type == "Receive"])
    avg_daily_issue = total_issued / 180 if total_issued else 0
    days_left = (item.expiry_date - date.today()).days

    row = {
        "days_left": days_left, "quantity": item.quantity,
        "avg_daily_issue": avg_daily_issue, "reorder_count": reorder_count
    }
    for col in feature_cols:
        if col.startswith("department_"):
            dept_name = col.replace("department_", "")
            row[col] = 1 if item.department == dept_name else 0
    input_df = pd.DataFrame([row])[feature_cols].fillna(0)

    probability = model.predict_proba(input_df)[0][1]  # probability of "wasted"
    if probability >= 0.66:
        risk, action = "High", "Transfer to another department or return to supplier"
    elif probability >= 0.33:
        risk, action = "Medium", "Prioritize using this batch soon"
    else:
        risk, action = "Low", "Use first per normal FEFO order"

    return risk, round(probability * 100, 1), action