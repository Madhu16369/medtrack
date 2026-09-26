from flask import Flask, render_template, request, redirect, flash, Response
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models import User, InventoryItem, StockMovement, get_expiry_status, DEPARTMENTS, SUPPLIERS, fefo_priority_score
from datetime import datetime
from functools import wraps
import bcrypt
import os
import pandas as pd
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont

from ml_risk import train_risk_model, predict_risk_for_item
from ml_forecast import smart_reorder_quantity
from ml_anomaly import detect_anomalies

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-to-something-random-later'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medtrack.db'

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'


def manager_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.role != "Manager":
            flash("This action is restricted to Inventory Managers.")
            return redirect("/dashboard")
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_alert_count():
    if current_user.is_authenticated:
        items = InventoryItem.query.all()
        count = sum(1 for item in items if get_expiry_status(item)[0] != "Safe")
        return dict(alert_count=count)
    return dict(alert_count=0)


def generate_barcode_image(item):
    code = barcode.get('code128', f"ITEM:{item.id}", writer=ImageWriter())
    temp_path = os.path.join("static", "barcodes", f"temp_{item.id}")
    saved_file = code.save(temp_path, options={"write_text": False, "quiet_zone": 2})

    barcode_img = Image.open(saved_file)
    label_height = 60
    canvas = Image.new("RGB", (barcode_img.width, barcode_img.height + label_height), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()

    draw.text((10, 5), item.name[:40], fill="black", font=font)
    draw.text((10, 30), f"Batch: {item.batch_number}", fill="black", font=font)
    canvas.paste(barcode_img, (0, label_height))

    final_path = os.path.join("static", "barcodes", f"item_{item.id}.png")
    canvas.save(final_path)
    os.remove(saved_file)
    return final_path


@app.route("/")
def home():
    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        existing = User.query.filter_by(username=username).first()
        if existing:
            flash("Username already exists. Try logging in.")
            return redirect("/register")

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        new_user = User(username=username, password_hash=hashed.decode('utf-8'), role=role)
        db.session.add(new_user)
        db.session.commit()
        flash("Account created! Please log in.")
        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            login_user(user)
            return redirect("/dashboard")
        else:
            flash("Invalid username or password.")
            return redirect("/login")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")


@app.route("/dashboard")
@login_required
def dashboard():
    items = InventoryItem.query.all()
    total_items = len(items)
    low_stock = [i for i in items if i.quantity < i.min_stock_threshold]
    near_expiry = [i for i in items if get_expiry_status(i)[0] in ("Critical", "Warning", "Notice")]
    expired = [i for i in items if get_expiry_status(i)[0] == "Expired"]

    reorder_suggestions = []
    for item in low_stock:
        suggested_qty = max(0, (item.min_stock_threshold * 2) - item.quantity)
        reorder_suggestions.append((item, suggested_qty))

    dept_totals = {}
    for item in items:
        dept = item.department or "Unassigned"
        dept_totals[dept] = dept_totals.get(dept, 0) + item.quantity

    return render_template(
        "dashboard.html",
        total_items=total_items,
        low_stock=low_stock,
        near_expiry=near_expiry,
        expired=expired,
        reorder_suggestions=reorder_suggestions,
        dept_labels=list(dept_totals.keys()),
        dept_values=list(dept_totals.values())
    )


@app.route("/inventory")
@login_required
def inventory_list():
    query = InventoryItem.query
    search_term = request.args.get("q", "").strip()
    department_filter = request.args.get("department", "").strip()

    if search_term:
        query = query.filter(InventoryItem.name.ilike(f"%{search_term}%"))
    if department_filter:
        query = query.filter(InventoryItem.department == department_filter)

    items = query.all()
    return render_template("inventory_list.html", items=items, departments=DEPARTMENTS)


@app.route("/inventory/add", methods=["GET", "POST"])
@login_required
@manager_required
def add_item():
    if request.method == "POST":
        new_item = InventoryItem(
            name=request.form["name"],
            batch_number=request.form["batch_number"],
            quantity=int(request.form["quantity"]),
            expiry_date=datetime.strptime(request.form["expiry_date"], "%Y-%m-%d").date(),
            supplier=request.form.get("supplier"),
            storage_location=request.form.get("storage_location"),
            department=request.form.get("department"),
            unit_price=float(request.form.get("unit_price") or 0),
            min_stock_threshold=int(request.form.get("min_stock_threshold") or 10),
        )
        db.session.add(new_item)
        db.session.flush()

        new_item.qr_code_path = generate_barcode_image(new_item)

        db.session.commit()
        flash("Item added successfully!")
        return redirect("/inventory")
    return render_template("add_item.html", departments=DEPARTMENTS, suppliers=SUPPLIERS)


@app.route("/inventory/edit/<int:item_id>", methods=["GET", "POST"])
@login_required
@manager_required
def edit_item(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    if request.method == "POST":
        item.name = request.form["name"]
        item.batch_number = request.form["batch_number"]
        item.quantity = int(request.form["quantity"])
        item.expiry_date = datetime.strptime(request.form["expiry_date"], "%Y-%m-%d").date()
        item.supplier = request.form.get("supplier")
        item.storage_location = request.form.get("storage_location")
        item.department = request.form.get("department")
        item.unit_price = float(request.form.get("unit_price") or 0)
        item.min_stock_threshold = int(request.form.get("min_stock_threshold") or 10)
        db.session.commit()
        flash("Item updated successfully!")
        return redirect("/inventory")
    return render_template("edit_item.html", item=item)


@app.route("/inventory/delete/<int:item_id>")
@login_required
@manager_required
def delete_item(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Item deleted.")
    return redirect("/inventory")


@app.route("/backfill-qr")
@login_required
@manager_required
def backfill_qr():
    items = InventoryItem.query.filter_by(qr_code_path=None).all()
    for item in items:
        item.qr_code_path = generate_barcode_image(item)
    db.session.commit()
    return "Backfilled barcodes for all items without one."


@app.route("/inventory/template.csv")
@login_required
def inventory_template():
    sample = pd.DataFrame([{
        "name": "Paracetamol 500mg", "batch_number": "B2026-01", "quantity": 100,
        "expiry_date": "2026-12-31", "supplier": "MedSupply Co.",
        "storage_location": "Shelf A1", "department": "Pharmacy",
        "unit_price": 2.5, "min_stock_threshold": 20
    }])
    return Response(sample.to_csv(index=False), mimetype="text/csv",
                     headers={"Content-Disposition": "attachment;filename=inventory_template.csv"})


@app.route("/inventory/upload", methods=["GET", "POST"])
@login_required
@manager_required
def upload_inventory():
    if request.method == "POST":
        file = request.files.get("excel_file")
        if not file:
            flash("No file selected.")
            return redirect("/inventory/upload")
        try:
            df = pd.read_excel(file)
        except Exception as e:
            flash(f"Could not read file: {e}")
            return redirect("/inventory/upload")

        required_cols = {"name", "batch_number", "quantity", "expiry_date"}
        if not required_cols.issubset(set(df.columns)):
            flash(f"Missing required columns. Need at least: {', '.join(required_cols)}")
            return redirect("/inventory/upload")

        added, skipped = 0, 0
        for _, row in df.iterrows():
            try:
                new_item = InventoryItem(
                    name=str(row["name"]),
                    batch_number=str(row["batch_number"]),
                    quantity=int(row["quantity"]),
                    expiry_date=pd.to_datetime(row["expiry_date"]).date(),
                    supplier=str(row.get("supplier", "")),
                    storage_location=str(row.get("storage_location", "")),
                    department=str(row.get("department", "")),
                    unit_price=float(row.get("unit_price", 0) or 0),
                    min_stock_threshold=int(row.get("min_stock_threshold", 10) or 10),
                )
                db.session.add(new_item)
                db.session.flush()
                new_item.qr_code_path = generate_barcode_image(new_item)
                added += 1
            except Exception:
                skipped += 1
        db.session.commit()
        flash(f"Import complete: {added} items added, {skipped} rows skipped due to errors.")
        return redirect("/inventory")

    return render_template("upload_inventory.html")


@app.route("/scan")
@login_required
def scan():
    return render_template("scan.html")


@app.route("/scan/lookup")
@login_required
def scan_lookup():
    code = request.args.get("code", "")
    if code.startswith("ITEM:"):
        item_id = int(code.replace("ITEM:", ""))
        item = InventoryItem.query.get_or_404(item_id)
        return render_template("scan_result.html", item=item)
    flash("Barcode not recognized.")
    return redirect("/scan")


@app.route("/scan/update/<int:item_id>", methods=["POST"])
@login_required
def scan_update(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    movement_type = request.form["movement_type"]
    qty = int(request.form["quantity"])

    if movement_type == "Issue":
        item.quantity = max(0, item.quantity - qty)
    else:
        item.quantity += qty

    movement = StockMovement(
        item_id=item.id,
        movement_type=movement_type,
        quantity=qty,
        performed_by=current_user.id
    )
    db.session.add(movement)
    db.session.commit()
    flash(f"Stock updated: {movement_type} of {qty} for {item.name}.")
    return redirect("/inventory")


@app.route("/alerts")
@login_required
def alerts():
    items = InventoryItem.query.order_by(InventoryItem.expiry_date).all()
    alerts_data = []
    for item in items:
        status, color, days_left = get_expiry_status(item)
        if status != "Safe":
            alerts_data.append((item, status, color, days_left))
    return render_template("alerts.html", alerts=alerts_data)


@app.route("/reports")
@login_required
@manager_required
def reports():
    return render_template("reports.html")


def items_to_dataframe(items):
    rows = []
    for i in items:
        status, color, days_left = get_expiry_status(i)
        rows.append({
            "Name": i.name, "Batch": i.batch_number, "Quantity": i.quantity,
            "Expiry Date": i.expiry_date, "Days Left": days_left, "Status": status,
            "Department": i.department, "Supplier": i.supplier
        })
    return pd.DataFrame(rows)


@app.route("/reports/expired.csv")
@login_required
@manager_required
def report_expired():
    items = [i for i in InventoryItem.query.all() if get_expiry_status(i)[0] == "Expired"]
    df = items_to_dataframe(items)
    return Response(df.to_csv(index=False), mimetype="text/csv",
                     headers={"Content-Disposition": "attachment;filename=expired_items.csv"})


@app.route("/reports/low-stock.csv")
@login_required
@manager_required
def report_low_stock():
    items = [i for i in InventoryItem.query.all() if i.quantity < i.min_stock_threshold]
    df = items_to_dataframe(items)
    return Response(df.to_csv(index=False), mimetype="text/csv",
                     headers={"Content-Disposition": "attachment;filename=low_stock_items.csv"})


@app.route("/reports/full-inventory.csv")
@login_required
@manager_required
def report_full():
    items = InventoryItem.query.all()
    df = items_to_dataframe(items)
    return Response(df.to_csv(index=False), mimetype="text/csv",
                     headers={"Content-Disposition": "attachment;filename=full_inventory.csv"})


@app.route("/ml/risk")
@login_required
@manager_required
def ml_risk_dashboard():
    model, feature_cols, metrics = train_risk_model()
    if model is None:
        flash(metrics)
        return redirect("/dashboard")

    items = InventoryItem.query.all()
    results = []
    for item in items:
        risk, probability, action = predict_risk_for_item(model, feature_cols, item)
        results.append((item, risk, probability, action))

    return render_template("ml_risk.html", results=results, metrics=metrics)


@app.route("/ml/forecast")
@login_required
@manager_required
def ml_forecast_dashboard():
    items = InventoryItem.query.all()
    results = []
    for item in items:
        forecast_14d, safety_stock, suggested = smart_reorder_quantity(item)
        results.append((item, forecast_14d, safety_stock, suggested))
    return render_template("ml_forecast.html", results=results)


@app.route("/fefo")
@login_required
def fefo_priority_list():
    items = InventoryItem.query.all()
    ranked = []
    for item in items:
        status, color, days_left = get_expiry_status(item)
        if status == "Safe":
            continue
        movements = StockMovement.query.filter_by(item_id=item.id, movement_type="Issue").all()
        total_issued = sum(m.quantity for m in movements)
        avg_daily_issue = total_issued / 180 if total_issued else 0
        score = fefo_priority_score(item, avg_daily_issue)
        ranked.append((item, days_left, score))

    ranked.sort(key=lambda x: -x[2])
    return render_template("fefo.html", ranked=ranked)


@app.route("/ml/anomalies")
@login_required
@manager_required
def ml_anomalies():
    anomalies = detect_anomalies()
    return render_template("ml_anomalies.html", anomalies=anomalies)


@app.route("/suppliers")
@login_required
@manager_required
def supplier_scoring():
    items = InventoryItem.query.all()
    supplier_stats = {}
    for item in items:
        supplier = item.supplier or "Unknown"
        status, color, days_left = get_expiry_status(item)
        if supplier not in supplier_stats:
            supplier_stats[supplier] = {"total_items": 0, "expired_items": 0, "total_value": 0}
        supplier_stats[supplier]["total_items"] += 1
        supplier_stats[supplier]["total_value"] += item.quantity * item.unit_price
        if status == "Expired":
            supplier_stats[supplier]["expired_items"] += 1

    results = []
    for supplier, stats in supplier_stats.items():
        expiry_rate = (stats["expired_items"] / stats["total_items"]) * 100 if stats["total_items"] else 0
        if expiry_rate >= 20:
            badge = "High Risk"
        elif expiry_rate >= 5:
            badge = "Medium Risk"
        else:
            badge = "Low Risk"
        results.append((supplier, stats["total_items"], stats["expired_items"],
                         round(expiry_rate, 1), round(stats["total_value"], 2), badge))

    results.sort(key=lambda x: -x[3])
    return render_template("suppliers.html", results=results)

@app.route("/regenerate-all-barcodes")
@login_required
@manager_required
def regenerate_all_barcodes():
    items = InventoryItem.query.all()
    for item in items:
        item.qr_code_path = generate_barcode_image(item)
    db.session.commit()
    return f"Regenerated barcodes for {len(items)} items."

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)