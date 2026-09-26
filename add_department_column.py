from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as conn:
        conn.execute(text("ALTER TABLE user ADD COLUMN department VARCHAR(80)"))
        conn.commit()

print("Done — department column added.")