from app import app
from models import db, User, FocusSession
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def create_test_account():
    with app.app_context():
        # 1. Create John
        john = User.query.filter_by(username='john').first()
        if not john:
            john = User(
                username='john',
                password_hash=generate_password_hash('password123', method='scrypt')
            )
            db.session.add(john)
            db.session.commit()
            print("User 'john' created.")
        else:
            print("User 'john' already exists.")

        # 2. Create a partner for sync sessions if needed
        partner = User.query.filter(User.username != 'john').first()
        if not partner:
            partner = User(
                username='study_buddy',
                password_hash=generate_password_hash('password123', method='scrypt')
            )
            db.session.add(partner)
            db.session.commit()
            print("Partner user 'study_buddy' created.")

        # 3. Add Study Time
        # 20 hours sync time (1200 mins)
        # 30 hours solo time (1800 mins)
        # Total = 50 hours
        
        # Clear existing sessions for fresh start if you want, but I'll just add them
        
        print("Adding 20 hours of sync time...")
        # Add 20 sessions of 60 mins each
        for i in range(20):
            session = FocusSession(
                minutes=60,
                user_id=john.id,
                partner_id=partner.id,
                date=datetime.utcnow() - timedelta(days=i)
            )
            db.session.add(session)

        print("Adding 30 hours of solo study time...")
        for i in range(30):
            session = FocusSession(
                minutes=60,
                user_id=john.id,
                partner_id=None,
                date=datetime.utcnow() - timedelta(days=i+20)
            )
            db.session.add(session)

        db.session.commit()
        print("Test data populated successfully.")

if __name__ == "__main__":
    create_test_account()
