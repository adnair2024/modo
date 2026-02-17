from app import app
from models import User
from services.achievement_service import check_achievements

def update_john():
    with app.app_context():
        john = User.query.filter_by(username='john').first()
        if john:
            check_achievements(john)
            print(f"Achievements checked for {john.username}")

if __name__ == "__main__":
    update_john()
