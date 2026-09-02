from flask import Flask, render_template, request, redirect, flash
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models import User
import bcrypt
from models import User, InventoryItem
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-to-something-random-later'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medtrack.db'

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

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

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

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

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)