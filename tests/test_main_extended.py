from models import Task, Event, EventCompletion, Habit, HabitCompletion
from datetime import datetime, timedelta, date

def test_index_filters(auth_client):
    client, user = auth_client
    from app import db
    t1 = Task(title="Task A", user_id=user.id, created_at=datetime.now())
    t2 = Task(title="Task B", user_id=user.id, created_at=datetime.now() - timedelta(days=1))
    db.session.add_all([t1, t2])
    db.session.commit()
    
    # Search (HTMX to verify filtered list isolation)
    res = client.get('/?q=Task A', headers={'HX-Request': 'true'})
    assert b'Task A' in res.data
    assert b'Task B' not in res.data
    
    # Sort
    res = client.get('/?sort_by=created_at')
    assert res.status_code == 200

def test_update_task(auth_client):
    client, user = auth_client
    from app import db
    task = Task(title="Old Title", user_id=user.id)
    db.session.add(task)
    db.session.commit()
    
    client.post(f'/task/{task.id}', data={'title': 'New Title', 'priority': 3})
    assert Task.query.get(task.id).title == 'New Title'
    assert Task.query.get(task.id).priority == 3

def test_leaderboard(auth_client):
    client, user = auth_client
    res = client.get('/leaderboard')
    assert res.status_code == 200
    res = client.get('/leaderboard?category=habits')
    assert res.status_code == 200
    res = client.get('/leaderboard?category=sync')
    assert res.status_code == 200

def test_personal_stats(auth_client):
    client, user = auth_client
    res = client.get('/stats')
    assert res.status_code == 200

def test_badges(auth_client):
    client, user = auth_client
    res = client.get('/badges')
    assert res.status_code == 200

def test_habit_delete(auth_client):
    client, user = auth_client
    from app import db
    habit = Habit(title="Delete Habit", user_id=user.id)
    db.session.add(habit)
    db.session.commit()
    
    client.post(f'/habits/delete/{habit.id}')
    assert Habit.query.get(habit.id) is None
