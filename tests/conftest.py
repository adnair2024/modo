import pytest
from app import app
from models import db, User, Task, Project, StudyRoom, Event
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for easier testing

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()

@pytest.fixture
def auth_client(client):
    user = User(username='testuser', password_hash=generate_password_hash('password', method='scrypt'))
    db.session.add(user)
    db.session.commit()

    client.post('/login', data={'username': 'testuser', 'password': 'password'})
    return client, user

@pytest.fixture
def runner(client):
    return app.test_cli_runner()
