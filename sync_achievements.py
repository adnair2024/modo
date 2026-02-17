from app import app
from models import User, db
from services.achievement_service import check_achievements, seed_achievements
from datetime import datetime, timedelta

def sync():
    with app.app_context():
        print("Seeding achievements if missing...")
        seed_achievements()
        
        print("Checking achievements for active users (last 24h)...")
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        users = User.query.filter(User.last_seen >= yesterday).all()
        for user in users:
            old_count = len(user.achievements)
            check_achievements(user)
            new_count = len(user.achievements)
            if new_count > old_count:
                print(f"User {user.username}: Unlocked {new_count - old_count} new achievements (Total: {new_count})")
            else:
                print(f"User {user.username}: Checked (Total: {new_count})")
        
        db.session.commit()
        print(f"Sync complete for {len(users)} users.")

if __name__ == "__main__":
    sync()
