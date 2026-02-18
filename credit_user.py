from app import app
from models import db, FocusSession, User

def credit_lost():
    with app.app_context():
        # Target user 'lost' or ID 1
        user = db.session.get(User, 1)
        if not user or user.username != 'lost':
            user = User.query.filter_by(username='lost').first()
        
        if user:
            # Create a manual session for 120 minutes
            new_session = FocusSession(minutes=120, user_id=user.id)
            db.session.add(new_session)
            db.session.commit()
            print(f"SUCCESS: 120 minutes added to {user.username}'s archive.")
        else:
            print("FAILURE: Subject 'lost' not found.")

if __name__ == "__main__":
    credit_lost()
