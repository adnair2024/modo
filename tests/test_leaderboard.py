import pytest
from models import User, FocusSession, Habit, HabitCompletion
from datetime import datetime, timedelta

def test_leaderboard_focus(auth_client):
    client, user = auth_client
    # Create some focus sessions
    from app import db
    s1 = FocusSession(minutes=30, user_id=user.id, date=datetime.now())
    db.session.add(s1)
    db.session.commit()
    
    response = client.get('/leaderboard?category=focus')
    assert response.status_code == 200
    assert user.username.encode() in response.data
    assert b'30m' in response.data

def test_leaderboard_habits(auth_client):
    client, user = auth_client
    from app import db
    habit = Habit(title="Test Habit", user_id=user.id)
    db.session.add(habit)
    db.session.commit()
    
    comp = HabitCompletion(habit_id=habit.id, date=datetime.now().date())
    db.session.add(comp)
    db.session.commit()
    
    response = client.get('/leaderboard?category=habits')
    assert response.status_code == 200
    assert user.username.encode() in response.data
    assert b'1' in response.data

def test_leaderboard_sync(auth_client):
    client, user = auth_client
    from app import db
    # Create another user for sync
    other = User(username='partner', password_hash='hash')
    db.session.add(other)
    db.session.commit()
    
    # Create sync session
    s1 = FocusSession(minutes=45, user_id=user.id, partner_id=other.id, date=datetime.now())
    db.session.add(s1)
    db.session.commit()
    
    response = client.get('/leaderboard?category=sync')
    assert response.status_code == 200
    assert user.username.encode() in response.data
    assert b'45m' in response.data
