from models import StudyRoom, User
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def test_sync_reject(auth_client):
    client, user = auth_client
    from app import db
    other = User(username='other', password_hash=generate_password_hash('pass', method='scrypt'))
    db.session.add(other)
    db.session.commit()
    
    client.post(f'/study/sync/request/{other.id}', data={'focus_duration': 25})
    room = StudyRoom.query.filter_by(host_id=user.id).first()
    
    client.get('/logout')
    client.post('/login', data={'username': 'other', 'password': 'pass'})
    
    client.post(f'/study/sync/reject/{room.id}')
    assert StudyRoom.query.get(room.id) is None

def test_study_state_timeout(auth_client):
    client, user = auth_client
    from app import db
    
    # Create stale room
    room = StudyRoom(host_id=user.id, guest_id=user.id, status='active')
    room.last_activity = datetime.utcnow() - timedelta(minutes=31)
    db.session.add(room)
    db.session.commit()
    
    # Trigger state check which should cleanup
    res = client.get(f'/study/state/{room.id}')
    assert res.json['status'] == 'finished'
    assert StudyRoom.query.get(room.id) is None

def test_leave_room(auth_client):
    client, user = auth_client
    from app import db
    room = StudyRoom(host_id=user.id, guest_id=user.id, status='active')
    db.session.add(room)
    db.session.commit()
    
    client.post(f'/study/leave/{room.id}')
    assert StudyRoom.query.get(room.id) is None

def test_join_room(auth_client):
    client, user = auth_client
    from app import db
    other = User(username='other', password_hash=generate_password_hash('pass', method='scrypt'))
    db.session.add(other)
    db.session.commit()
    
    room = StudyRoom(host_id=other.id, guest_id=user.id, status='waiting')
    db.session.add(room)
    db.session.commit()
    
    client.get(f'/study/join/{room.id}')
    assert StudyRoom.query.get(room.id).status == 'active'
