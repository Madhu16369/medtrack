from extensions import db, login_manager
from flask_login import UserMixin
from datetime import datetime
from datetime import date

DEPARTMENTS = ["Pharmacy", "Surgery", "Emergency", "ICU", "General Ward", "Radiology"]
SUPPLIERS = ["MedSupply Co.", "HealFast Pharma", "SafeHands Ltd.", "LifeLine Meds", "DiaCare Pharma", "OrthoTech Inc."]
STORAGE_LOCATIONS = {
    "Pharmacy": ["Shelf A1", "Shelf A2", "Shelf A3", "Fridge A"],
    "Surgery": ["Store Room 1", "Store Room 2", "Sterile Cabinet"],
    "Emergency": ["Emergency Cart", "Store Room 3"],
    "ICU": ["ICU Fridge", "ICU Cabinet"],
    "General Ward": ["Ward Shelf 1", "Ward Shelf 2"],
    "Radiology": ["Radiology Store"],
}


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # "Manager" or "Nurse"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    department = db.Column(db.String(80))  # used for Nurses to filter "my department" views

class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    batch_number = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    expiry_date = db.Column(db.Date, nullable=False)
    supplier = db.Column(db.String(120))
    storage_location = db.Column(db.String(120))
    department = db.Column(db.String(80))
    unit_price = db.Column(db.Float, default=0.0)
    min_stock_threshold = db.Column(db.Integer, default=10)
    qr_code_path = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StockMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    movement_type = db.Column(db.String(20))  # "Issue" or "Receive"
    quantity = db.Column(db.Integer)
    performed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship('InventoryItem', backref='movements')
    user = db.relationship('User', backref='movements')

def get_expiry_status(item):
    days_left = (item.expiry_date - date.today()).days
    if days_left < 0:
        return "Expired", "danger", days_left
    elif days_left <= 30:
        return "Critical", "danger", days_left
    elif days_left <= 60:
        return "Warning", "warning", days_left
    elif days_left <= 90:
        return "Notice", "info", days_left
    else:
        return "Safe", "success", days_left

def fefo_priority_score(item, avg_daily_issue):
    days_left = (item.expiry_date - date.today()).days
    days_left = max(days_left, 0.1)  # avoid divide-by-zero
    velocity = avg_daily_issue if avg_daily_issue > 0 else 0.1
    # Higher score = more urgent to use/transfer first
    score = (item.quantity / velocity) / days_left
    return round(score, 3)

