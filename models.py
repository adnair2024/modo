from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Presence & Live Status
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    show_last_seen = db.Column(db.Boolean, default=True)
    current_focus_start = db.Column(db.DateTime, nullable=True) # When they started
    current_focus_end = db.Column(db.DateTime, nullable=True)   # When it will end
    current_focus_mode = db.Column(db.String(20), default='none') # none, focus, break
    current_task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=True)
    
    current_task = db.relationship('Task', foreign_keys=[current_task_id], backref='working_users', lazy=True)
    tasks = db.relationship('Task', backref='author', lazy=True, foreign_keys="[Task.user_id]")
    focus_sessions = db.relationship('FocusSession', backref='user', lazy=True, foreign_keys="[FocusSession.user_id]")
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
    
    is_verified = db.Column(db.Boolean, default=False)

    notifications = db.relationship('Notification', backref='user', lazy=True, cascade="all, delete-orphan")

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, accepted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'friend_id', name='_user_friend_uc'),)

class StudyRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    host_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    guest_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.String(20), default='waiting') # waiting, active, finished
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Sync Settings
    focus_duration = db.Column(db.Integer, default=25)
    break_duration = db.Column(db.Integer, default=5)
    sessions_count = db.Column(db.Integer, default=1)
    
    # Live State
    active_mode = db.Column(db.String(20), default='focus') # focus, break
    active_start_time = db.Column(db.DateTime, nullable=True) # If set, timer is running
    seconds_remaining = db.Column(db.Integer, nullable=True) # Snapshot when paused

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
    partner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    # Recurrence: 'none', 'daily', 'weekly', 'monthly', 'custom'
    recurrence = db.Column(db.String(20), default='none')
    # Stores comma-separated days for custom recurrence (0=Mon, 6=Sun) e.g., "0,2,4"
    recurrence_days = db.Column(db.String(50), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    completions = db.relationship('EventCompletion', backref='event', lazy=True, cascade="all, delete-orphan")

class EventCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False) # Stores the specific date of the occurrence
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('event_id', 'date', name='_event_date_uc'),)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    type = db.Column(db.String(20), default='info')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    completions = db.relationship('HabitCompletion', backref='habit', lazy=True, cascade="all, delete-orphan")

class HabitCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    date = db.Column(db.Date, nullable=False) # The date for which it counts
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('habit_id', 'date', name='_habit_date_uc'),)

