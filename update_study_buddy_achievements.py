from app import app
from models import User
from services.achievement_service import check_achievements

def update_buddy():
    with app.app_context():
        buddy = User.query.filter_by(username='study_buddy').first()
        if buddy:
            check_achievements(buddy)
            print(f"Achievements checked for {buddy.username}")

if __name__ == "__main__":
    update_buddy()
