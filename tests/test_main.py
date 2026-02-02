from models import Task, Habit, Event, EventCompletion
from datetime import datetime, date

def test_index(auth_client):
    client, user = auth_client
    response = client.get('/')
    assert response.status_code == 200
    assert b'My Tasks' in response.data

def test_add_task(auth_client):
    client, user = auth_client
    response = client.post('/add_task', data={
        'title': 'Test Task',
        'description': 'Desc',
        'priority': 2
    })
    assert response.status_code == 200
    assert b'Test Task' in response.data
    assert Task.query.filter_by(title='Test Task').first() is not None

def test_add_task_invalid(auth_client):
    client, _ = auth_client
    response = client.post('/add_task', data={})
    assert response.status_code == 400

def test_delete_task(auth_client):
    client, user = auth_client
    task = Task(title="Delete Me", user_id=user.id)
    from app import db
    db.session.add(task)
    db.session.commit()
    
    response = client.delete(f'/delete_task/{task.id}')
    assert response.status_code == 200
    assert Task.query.get(task.id) is None

def test_toggle_task(auth_client):
    client, user = auth_client
    task = Task(title="Toggle Me", user_id=user.id, status='todo')
    from app import db
    db.session.add(task)
    db.session.commit()
    
    response = client.post(f'/toggle_task/{task.id}')
    assert response.status_code == 200
    assert Task.query.get(task.id).status == 'done'
    
    response = client.post(f'/toggle_task/{task.id}')
    assert Task.query.get(task.id).status == 'todo'

def test_habits(auth_client):
    client, user = auth_client
    response = client.get('/habits')
    assert response.status_code == 200

def test_add_habit(auth_client):
    client, user = auth_client
    client.post('/habits/add', data={'title': 'Drink Water'})
    assert Habit.query.filter_by(title='Drink Water').first() is not None

def test_toggle_habit(auth_client):
    client, user = auth_client
    habit = Habit(title="Run", user_id=user.id)
    from app import db
    db.session.add(habit)
    db.session.commit()
    
    today_str = date.today().strftime('%Y-%m-%d')
    client.post(f'/habits/toggle/{habit.id}?date={today_str}')
    assert len(habit.completions) == 1
    
    client.post(f'/habits/toggle/{habit.id}?date={today_str}')
    assert len(habit.completions) == 0

def test_toggle_event(auth_client):
    client, user = auth_client
    event = Event(title="Meeting", start_time=datetime.now(), end_time=datetime.now(), user_id=user.id)
    from app import db
    db.session.add(event)
    db.session.commit()
    
    today_str = date.today().strftime('%Y-%m-%d')
    client.post(f'/toggle_event/{event.id}?date={today_str}')
    assert EventCompletion.query.filter_by(event_id=event.id).count() == 1
    
    client.post(f'/toggle_event/{event.id}?date={today_str}')
    assert EventCompletion.query.filter_by(event_id=event.id).count() == 0
