from app import app
from models import User, db
from services.achievement_service import check_achievements, seed_achievements

def sync():
    with app.app_context():
        print("Seeding achievements if missing...")
        seed_achievements()
        
        print("Checking achievements for all users...")
        users = User.query.all()
        for user in users:
            old_count = len(user.achievements)
            check_achievements(user)
            new_count = len(user.achievements)
            if new_count > old_count:
                print(f"User {user.username}: Unlocked {new_count - old_count} new achievements (Total: {new_count})")
            else:
                print(f"User {user.username}: No new achievements (Total: {new_count})")
        
        db.session.commit()
        print("Sync complete.")

if __name__ == "__main__":
    sync()
