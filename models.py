from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    tasks = db.relationship('Task', backref='author', lazy=True)
    focus_sessions = db.relationship('FocusSession', backref='user', lazy=True)
    theme_preference = db.Column(db.String(50), default='light')
    accent_color = db.Column(db.String(20), default='indigo')
    auto_start_break = db.Column(db.Boolean, default=False)
    auto_start_focus = db.Column(db.Boolean, default=False)
    auto_select_priority = db.Column(db.Boolean, default=False)
    focus_duration = db.Column(db.Integer, default=25)
    break_duration = db.Column(db.Integer, default=5)
    
    # Notification Settings
    notify_pomodoro = db.Column(db.Boolean, default=True)
    notify_event_start = db.Column(db.Boolean, default=True)
    event_notify_minutes = db.Column(db.Integer, default=30)
    
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade="all, delete-orphan")

task_tags = db.Table('task_tags',
    db.Column('task_id', db.Integer, db.ForeignKey('task.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='todo') # todo, in_progress, done
    priority = db.Column(db.Integer, default=1) # 1: Low, 2: Medium, 3: High
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=True)
    estimated_pomodoros = db.Column(db.Integer, default=1)
    completed_pomodoros = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subtasks = db.relationship('Subtask', backref='parent', lazy=True, cascade="all, delete-orphan")
    tags = db.relationship('Tag', secondary=task_tags, backref=db.backref('tasks', lazy='dynamic'))

class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

class FocusSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    minutes = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=True)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    # Recurrence: 'none', 'daily', 'weekly', 'monthly'
    recurrence = db.Column(db.String(20), default='none')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    type = db.Column(db.String(20), default='info')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True)

