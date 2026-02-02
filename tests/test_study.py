from models import StudyRoom, ChatMessage, User
from werkzeug.security import generate_password_hash

def test_sync_request_flow(auth_client):
    client, user = auth_client
    from app import db
    
    other = User(username='friend', password_hash=generate_password_hash('pass', method='scrypt'))
    db.session.add(other)
    db.session.commit()
    
    # Send Request
    client.post(f'/study/sync/request/{other.id}', data={
        'focus_duration': 25
    })
    room = StudyRoom.query.filter_by(host_id=user.id).first()
    assert room is not None
    assert room.status == 'pending_sync'
    
    # Other accepts
    client.get('/logout')
    client.post('/login', data={'username': 'friend', 'password': 'pass'})
    
    client.post(f'/study/sync/accept/{room.id}')
    assert StudyRoom.query.get(room.id).status == 'active'

def test_study_control(auth_client):
    client, user = auth_client
    from app import db
    # Create active room (self-study hack or mock)
    room = StudyRoom(host_id=user.id, guest_id=user.id, status='active') # Self study
    db.session.add(room)
    db.session.commit()
    
    client.post('/study/control', json={'room_id': room.id, 'action': 'start'})
    assert StudyRoom.query.get(room.id).active_start_time is not None
    
    client.post('/study/control', json={'room_id': room.id, 'action': 'pause'})
    assert StudyRoom.query.get(room.id).active_start_time is None
    
def test_chat(auth_client):
    client, user = auth_client
    from app import db
    room = StudyRoom(host_id=user.id, guest_id=user.id, status='active')
    db.session.add(room)
    db.session.commit()
    
    client.post(f'/study/room/{room.id}/chat', data={'message': 'Hello'})
    assert ChatMessage.query.filter_by(message='Hello').first() is not None
    
    response = client.get(f'/study/room/{room.id}/chat')
    assert b'Hello' in response.data
