import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from datetime import date, timedelta
from models import InventoryItem, StockMovement

def get_daily_issue_series(item_id, days=180):
    start = date.today() - timedelta(days=days)
    movements = StockMovement.query.filter_by(item_id=item_id, movement_type="Issue").all()
    daily = {start + timedelta(days=i): 0 for i in range(days)}
    for m in movements:
        d = m.timestamp.date()
        if d in daily:
            daily[d] += m.quantity
    series = pd.Series(daily).sort_index()
    return series

def forecast_demand(item_id, horizon_days=14):
    series = get_daily_issue_series(item_id)
    if series.sum() == 0:
        return 0  # no history yet, no forecast possible

    # Build lagged features: predict day t from days t-1..t-7
    df = pd.DataFrame({"y": series.values})
    for lag in range(1, 8):
        df[f"lag_{lag}"] = df["y"].shift(lag)
    df = df.dropna()

    if len(df) < 20:
        return round(series.mean() * horizon_days, 1)  # fallback: simple average

    X = df[[f"lag_{i}" for i in range(1, 8)]]
    y = df["y"]
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)

    last_values = list(series.values[-7:])
    predictions = []
    for _ in range(horizon_days):
        x_input = pd.DataFrame([last_values[-7:][::-1]], columns=[f"lag_{i}" for i in range(1, 8)])
        pred = max(0, model.predict(x_input)[0])
        predictions.append(pred)
        last_values.append(pred)

    return round(sum(predictions), 1)

def smart_reorder_quantity(item, safety_stock_days=7):
    forecast_14d = forecast_demand(item.id, horizon_days=14)
    daily_rate = forecast_14d / 14 if forecast_14d else 0
    safety_stock = daily_rate * safety_stock_days
    suggested = max(0, round(forecast_14d + safety_stock - item.quantity))
    return forecast_14d, round(safety_stock, 1), suggested