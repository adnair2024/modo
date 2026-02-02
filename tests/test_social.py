from models import User, Friendship, StudyRoom, Task, FocusSession
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def test_profile(auth_client):
    client, user = auth_client
    response = client.get(f'/u/{user.username}')
    assert response.status_code == 200
    assert user.username.encode() in response.data

def test_friends_list(auth_client):
    client, user = auth_client
    response = client.get('/friends')
    assert response.status_code == 200

def test_search_friends(auth_client):
    client, user = auth_client
    from app import db
    other = User(username='other', password_hash=generate_password_hash('pass', method='scrypt'))
    db.session.add(other)
    db.session.commit()
    
    response = client.post('/friends/search', data={'username': 'other'})
    assert response.status_code == 200
    assert b'other' in response.data

def test_friend_request_flow(auth_client):
    client, user = auth_client
    from app import db
    friend = User(username='friend', password_hash=generate_password_hash('pass', method='scrypt'))
    db.session.add(friend)
    db.session.commit()
    
    # Send Request
    client.post(f'/friend/request/{friend.id}')
    assert Friendship.query.filter_by(user_id=user.id, friend_id=friend.id).first().status == 'pending'
    
    # Login as friend
    client.get('/logout')
    client.post('/login', data={'username': 'friend', 'password': 'pass'})
    
    # Accept
    client.post(f'/friend/respond/{user.id}/accept')
    assert Friendship.query.filter_by(user_id=user.id, friend_id=friend.id).first().status == 'accepted'
    
    # Remove
    client.post(f'/friend/respond/{user.id}/remove')
    assert Friendship.query.filter_by(user_id=user.id, friend_id=friend.id).first() is None

def test_reject_friend_request(auth_client):
    client, user = auth_client
    from app import db
    friend = User(username='rejecter', password_hash=generate_password_hash('pass', method='scrypt'))
    db.session.add(friend)
    db.session.commit()
    
    # User requests Friend
    client.post(f'/friend/request/{friend.id}')
    
    # Friend rejects
    client.get('/logout')
    client.post('/login', data={'username': 'rejecter', 'password': 'pass'})
    
    client.post(f'/friend/respond/{user.id}/reject')
    assert Friendship.query.filter_by(user_id=user.id, friend_id=friend.id).first() is None
