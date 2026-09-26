import random
from datetime import datetime, timedelta
from app import app
from extensions import db
from models import InventoryItem, StockMovement, User

random.seed(42)

with app.app_context():
    items = InventoryItem.query.all()
    users = User.query.all()
    if not items or not users:
        print("Add at least 1 user and a few inventory items before running this.")
        exit()

    user_ids = [u.id for u in users]
    start_date = datetime.today() - timedelta(days=180)

    count = 0
    for item in items:
        # Each item gets a randomly assigned "typical daily usage rate"
        daily_rate = random.uniform(0.5, 5.0)
        for day in range(180):
            current_date = start_date + timedelta(days=day)
            if random.random() < 0.3:  # not every item moves every day
                qty = max(1, int(random.gauss(daily_rate, daily_rate * 0.4)))
                movement_type = "Issue" if random.random() < 0.85 else "Receive"

                # Plant a few deliberate anomalies (unusually large movements)
                if random.random() < 0.02:
                    qty = qty * random.randint(8, 15)

                movement = StockMovement(
                    item_id=item.id,
                    movement_type=movement_type,
                    quantity=qty,
                    performed_by=random.choice(user_ids),
                    timestamp=current_date
                )
                db.session.add(movement)
                count += 1
    db.session.commit()
    print(f"Generated {count} synthetic stock movement records across {len(items)} items.")