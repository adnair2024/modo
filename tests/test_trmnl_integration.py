import pytest
from app import app as flask_app
from models import db, User, Task
from datetime import datetime, timezone
import os

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "TRMNL_API_KEY": "test-token-123"
    })
    
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def admin_user(app):
    with app.app_context():
        user = User(username="lost", password_hash="hash", is_admin=True)
        db.session.add(user)
        db.session.commit()
        return user.id

def test_trmnl_endpoint_auth(client, admin_user):
    # Test unauthorized
    response = client.get('/api/trmnl')
    assert response.status_code == 401
    
    # Test authorized with Bearer
    response = client.get('/api/trmnl', headers={"Authorization": "Bearer test-token-123"})
    assert response.status_code == 200

def test_trmnl_task_prioritization(client, admin_user, app):
    with app.app_context():
        # Create 10 tasks
        for i in range(10):
            t = Task(title=f"Task {i}", user_id=admin_user, priority=1)
            db.session.add(t)
        
        # Pin task 5 and 8
        task5 = Task.query.filter_by(title="Task 5").first()
        task8 = Task.query.filter_by(title="Task 8").first()
        task5.is_pinned_to_trmnl = True
        task8.is_pinned_to_trmnl = True
        db.session.commit()

    # Call TRMNL API
    response = client.get('/api/trmnl', headers={"Authorization": "Bearer test-token-123"})
    data = response.get_json()
    
    assert data['status'] == 'OPERATIONAL'
    assert len(data['tasks']) == 5
    
    # Check that pinned tasks are first (order by pinned desc, created_at desc)
    # Task 8 was created after Task 5, so it should be first
    assert data['tasks'][0]['title'] == "Task 8"
    assert data['tasks'][1]['title'] == "Task 5"
    assert data['tasks'][0]['pinned'] is True

def test_trmnl_poll_tracking(client, admin_user, app):
    with app.app_context():
        user = db.session.get(User, admin_user)
        assert user.last_trmnl_poll is None
    
    client.get('/api/trmnl', headers={"Authorization": "Bearer test-token-123"})
    
    with app.app_context():
        user = db.session.get(User, admin_user)
        assert user.last_trmnl_poll is not None
        assert isinstance(user.last_trmnl_poll, datetime)

def test_toggle_trmnl_pin(client, admin_user, app):
    with app.app_context():
        user = db.session.get(User, admin_user)
        task = Task(title="Toggle Test", user_id=admin_user)
        db.session.add(task)
        db.session.commit()
        task_id = task.id

    # Mock login
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user)
        sess['_fresh'] = True

    # Toggle On
    response = client.post(f'/api/tasks/{task_id}/toggle_trmnl')
    assert response.status_code == 200
    assert response.get_json()['is_pinned'] is True
    
    # Toggle Off
    response = client.post(f'/api/tasks/{task_id}/toggle_trmnl')
    assert response.status_code == 200
    assert response.get_json()['is_pinned'] is False
