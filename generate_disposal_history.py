import random
from datetime import datetime, timedelta
from app import app
from extensions import db
from models import InventoryItem, RemovedItem, User

random.seed(7)

sample_names = [
    ("Paracetamol 500mg", "PARA-2025-11"), ("Amoxicillin 250mg", "AMOX-2025-09"),
    ("Surgical Gloves (Box)", "SG-2025-14"), ("IV Saline 500ml", "IV-2025-22"),
    ("Insulin Syringes", "SYR-2025-08"), ("Suture Kit", "SUT-2025-05"),
]

with app.app_context():
    manager = User.query.filter_by(role="Manager").first()
    if not manager:
        print("Add at least one Manager account before running this.")
        exit()

    today = datetime.today()
    count = 0
    for months_ago in range(1, 6):  # last 5 months, leaving the current month as-is
        month_date = today.replace(day=1) - timedelta(days=1)
        for _ in range(months_ago):
            month_date = month_date.replace(day=1) - timedelta(days=1)
        removal_date = month_date.replace(day=random.randint(1, 25))

        for _ in range(random.randint(2, 4)):  # a few disposals per month
            name, batch = random.choice(sample_names)
            qty = random.randint(5, 40)
            price = round(random.uniform(2, 50), 2)
            record = RemovedItem(
                name=name, batch_number=batch, quantity=qty,
                expiry_date=removal_date.date(), department="Pharmacy",
                unit_price=price, removed_by=manager.id,
                removed_at=removal_date, reason="Expired - physically discarded"
            )
            db.session.add(record)
            count += 1

    db.session.commit()
    print(f"Inserted {count} sample disposal records across the last 5 months.")