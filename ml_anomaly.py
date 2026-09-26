import pandas as pd
from sklearn.ensemble import IsolationForest
from models import StockMovement, InventoryItem

def detect_anomalies():
    movements = StockMovement.query.all()
    if len(movements) < 20:
        return []

    rows = [{
        "id": m.id, "item_id": m.item_id, "quantity": m.quantity,
        "movement_type": m.movement_type, "timestamp": m.timestamp
    } for m in movements]
    df = pd.DataFrame(rows)

    df["is_issue"] = (df["movement_type"] == "Issue").astype(int)
    features = df[["quantity", "is_issue"]]

    model = IsolationForest(contamination=0.03, random_state=42)
    df["anomaly_flag"] = model.fit_predict(features)  # -1 = anomaly, 1 = normal

    anomalies = df[df["anomaly_flag"] == -1]
    results = []
    for _, row in anomalies.iterrows():
        item = InventoryItem.query.get(row["item_id"])
        if item:
            results.append({
                "item_name": item.name,
                "quantity": row["quantity"],
                "movement_type": row["movement_type"],
                "timestamp": row["timestamp"]
            })
    return results