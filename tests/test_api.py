from models import User, Task, Notification, FocusSession, StudyRoom
from werkzeug.security import generate_password_hash
from datetime import datetime

def test_log_session(auth_client):
    client, user = auth_client
    task = Task(title="Focus Task", user_id=user.id)
    from app import db
    db.session.add(task)
    db.session.commit()
    
    response = client.post('/api/log_session', json={
        'minutes': 25,
        'task_id': task.id
    })
    assert response.status_code == 200
    assert response.json['status'] == 'success'
    assert FocusSession.query.filter_by(task_id=task.id).first() is not None

def test_log_session_invalid(auth_client):
    client, _ = auth_client
    response = client.post('/api/log_session', json={})
    assert response.status_code == 400

def test_next_priority_task(auth_client):
    client, user = auth_client
    from app import db
    t1 = Task(title="Low", priority=1, user_id=user.id)
    t2 = Task(title="High", priority=3, user_id=user.id)
    db.session.add_all([t1, t2])
    db.session.commit()
    
    response = client.get('/api/next_priority_task')
    assert response.json['title'] == 'High'

def test_sync_presence(auth_client):
    client, user = auth_client
    response = client.post('/api/sync_presence', json={
        'status': 'running',
        'mode': 'focus',
        'seconds_left': 60
    })
    assert response.status_code == 200
    
    from app import db
    # Refresh user
    # user = User.query.get(user.id) # Use session get
    u = db.session.get(User, user.id)
    assert u.current_focus_mode == 'focus'
    assert u.current_focus_end is not None

def test_notifications(auth_client):
    client, user = auth_client
    from app import db
    notif = Notification(user_id=user.id, message="Test")
    db.session.add(notif)
    db.session.commit()
    
    response = client.get('/api/notifications')
    assert len(response.json) == 1
    assert response.json[0]['message'] == 'Test'
    
    client.post(f'/api/notifications/mark_read/{notif.id}')
    notif = db.session.get(Notification, notif.id)
    assert notif.is_read

    # Mark all read
    notif2 = Notification(user_id=user.id, message="Test 2")
    db.session.add(notif2)
    db.session.commit()
    
    client.post('/api/notifications/mark_all_read')
    notif2 = db.session.get(Notification, notif2.id)
    assert notif2.is_read

def test_update_settings(auth_client):
    client, user = auth_client
    response = client.post('/api/update_settings', json={
        'theme': 'dark',
        'focus_duration': 50,
        'enable_vim_mode': True
    })
    assert response.status_code == 200
    
    from app import db
    u = db.session.get(User, user.id)
    assert u.theme_preference == 'dark'
    assert u.focus_duration == 50
    assert u.enable_vim_mode is True
