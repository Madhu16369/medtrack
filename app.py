from flask import Flask, render_template, request, redirect, flash
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models import User
import bcrypt

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

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)