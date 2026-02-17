import pytest
from app import app
from models import db, User, FocusSession
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone

def test_profile_with_null_dates(client):
    # Create a user with some potentially problematic data
    user = User(
        username='Turtle', 
        password_hash=generate_password_hash('password', method='scrypt'),
    )
    db.session.add(user)
    db.session.commit()

    # Log in
    client.post('/login', data={'username': 'Turtle', 'password': 'password'})

    # Try to access profile
    response = client.get('/u/Turtle')
    assert response.status_code == 200

def test_profile_with_focus_sessions(client):
    user = User(
        username='FocusUser', 
        password_hash=generate_password_hash('password', method='scrypt')
    )
    db.session.add(user)
    db.session.commit()

    session = FocusSession(user_id=user.id, minutes=25, date=datetime.now(timezone.utc))
    db.session.add(session)
    db.session.commit()

    client.post('/login', data={'username': 'FocusUser', 'password': 'password'})
    response = client.get('/u/FocusUser')
    assert response.status_code == 200
