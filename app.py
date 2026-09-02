from flask import Flask, render_template, request, redirect, flash, Response
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models import User, InventoryItem, StockMovement, get_expiry_status
from datetime import datetime
import bcrypt
import qrcode
import os
import pandas as pd

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-to-something-random-later'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medtrack.db'

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'


@app.context_processor
def inject_alert_count():
    if current_user.is_authenticated:
        items = InventoryItem.query.all()
        count = sum(1 for item in items if get_expiry_status(item)[0] != "Safe")
        return dict(alert_count=count)
    return dict(alert_count=0)


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
    items = InventoryItem.query.all()
    return render_template("inventory_list.html", items=items)


@app.route("/inventory/add", methods=["GET", "POST"])
@login_required
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

        qr_data = f"ITEM:{new_item.id}"
        qr_img = qrcode.make(qr_data)
        qr_filename = f"item_{new_item.id}.png"
        qr_path = os.path.join("static", "qrcodes", qr_filename)
        qr_img.save(qr_path)
        new_item.qr_code_path = qr_path

        db.session.commit()
        flash("Item added successfully!")
        return redirect("/inventory")
    return render_template("add_item.html")


@app.route("/inventory/edit/<int:item_id>", methods=["GET", "POST"])
@login_required
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
def delete_item(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Item deleted.")
    return redirect("/inventory")


@app.route("/backfill-qr")
@login_required
def backfill_qr():
    items = InventoryItem.query.filter_by(qr_code_path=None).all()
    for item in items:
        qr_data = f"ITEM:{item.id}"
        qr_img = qrcode.make(qr_data)
        qr_filename = f"item_{item.id}.png"
        qr_path = os.path.join("static", "qrcodes", qr_filename)
        qr_img.save(qr_path)
        item.qr_code_path = qr_path
    db.session.commit()
    return "Backfilled QR codes for all items without one."


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
    flash("QR code not recognized.")
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


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)