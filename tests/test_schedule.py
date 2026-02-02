from models import Event
from datetime import datetime

def test_schedule_view(auth_client):
    client, user = auth_client
    response = client.get('/schedule/')
    assert response.status_code == 200

def test_add_event(auth_client):
    client, user = auth_client
    client.post('/schedule/add', data={
        'title': 'Test Event',
        'start_time': '2026-01-01T10:00',
        'end_time': '2026-01-01T11:00',
        'recurrence': 'daily'
    })
    assert Event.query.filter_by(title='Test Event').first() is not None

def test_edit_event(auth_client):
    client, user = auth_client
    from app import db
    event = Event(title="Old", start_time=datetime.now(), end_time=datetime.now(), user_id=user.id)
    db.session.add(event)
    db.session.commit()
    
    # Get edit form
    response = client.get(f'/schedule/event/{event.id}/edit')
    assert response.status_code == 200
    
    # Update
    client.post(f'/schedule/event/{event.id}/update', data={
        'title': 'New Title'
    })
    
    updated = db.session.get(Event, event.id)
    assert updated.title == 'New Title'

def test_delete_event(auth_client):
    client, user = auth_client
    from app import db
    event = Event(title="Delete Me", start_time=datetime.now(), end_time=datetime.now(), user_id=user.id)
    db.session.add(event)
    db.session.commit()
    
    client.post(f'/schedule/delete/{event.id}')
    assert db.session.get(Event, event.id) is None
