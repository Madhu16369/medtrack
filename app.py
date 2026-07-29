from flask import Flask
from extensions import db, login_manager
import models

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-to-something-random-later'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medtrack.db'

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

@app.route("/")
def home():
    return "<h1>Welcome to MedTrack 🏥</h1><p>Database is ready!</p>"

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)