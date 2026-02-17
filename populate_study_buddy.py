from app import app
from models import db, User, FocusSession
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def populate_study_buddy():
    with app.app_context():
        # 1. Fetch Users
        study_buddy = User.query.filter_by(username='study_buddy').first()
        john = User.query.filter_by(username='john').first()
        
        if not study_buddy:
            print("Error: study_buddy user not found. Run create_test_account.py first.")
            return
        if not john:
            print("Error: john user not found.")
            return

        # 2. Add 5 hours sync time with John
        print("Adding 5 hours of sync time for study_buddy (with John)...")
        for i in range(5):
            session = FocusSession(
                minutes=60,
                user_id=study_buddy.id,
                partner_id=john.id,
                date=datetime.utcnow() - timedelta(days=i)
            )
            db.session.add(session)

        # 3. Add 5 hours solo time
        print("Adding 5 hours of solo study time for study_buddy...")
        for i in range(5):
            session = FocusSession(
                minutes=60,
                user_id=study_buddy.id,
                partner_id=None,
                date=datetime.utcnow() - timedelta(days=i+5)
            )
            db.session.add(session)

        db.session.commit()
        print(f"Test data for '{study_buddy.username}' populated successfully.")

if __name__ == "__main__":
    populate_study_buddy()
