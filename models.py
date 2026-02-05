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
    last_focus_end = db.Column(db.DateTime, nullable=True)      # When they last finished
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
    
    # Vim Mode
    enable_vim_mode = db.Column(db.Boolean, default=False)
    
    profile_pic_url = db.Column(db.String(500), nullable=True)
    profile_pic_position = db.Column(db.String(20), default='center')
    bio = db.Column(db.String(255), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)

    notifications = db.relationship('Notification', backref='user', lazy=True, cascade="all, delete-orphan")

    @property
    def all_accessible_tasks(self):
        # Personal tasks
        personal_tasks = Task.query.filter_by(user_id=self.id, section_id=None).all()
        
        # Project tasks
        project_tasks = Task.query.join(ProjectSection).join(Project).join(ProjectMember).filter(ProjectMember.user_id == self.id).all()
        
        # Return unique tasks sorted by priority/creation
        all_tasks = list(set(personal_tasks + project_tasks))
        # Use (0, datetime.min) as fallback for None values
        all_tasks.sort(key=lambda t: (t.priority or 0, t.created_at or datetime.min), reverse=True)
        return all_tasks

    @property
    def total_focus_hours(self):
        return sum(session.minutes for session in self.focus_sessions) / 60

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
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)

    host = db.relationship('User', foreign_keys=[host_id], backref='hosted_rooms', lazy=True)
    guest = db.relationship('User', foreign_keys=[guest_id], backref='guest_rooms', lazy=True)

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
    section_id = db.Column(db.Integer, db.ForeignKey('project_section.id'), nullable=True)
    subtasks = db.relationship('Subtask', backref='parent', lazy=True, cascade="all, delete-orphan")
    tags = db.relationship('Tag', secondary=task_tags, backref=db.backref('tasks', lazy='dynamic'))

class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    members = db.relationship('ProjectMember', backref='project', lazy=True, cascade="all, delete-orphan")
    sections = db.relationship('ProjectSection', backref='project', lazy=True, cascade="all, delete-orphan", order_by="ProjectSection.order")

class ProjectMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), default='member') # owner, member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='project_memberships', lazy=True)

class ProjectSection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, default=0)
    tasks = db.relationship('Task', backref='section', lazy=True)

class ProjectInvite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, accepted, declined
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_invites', lazy=True)
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_invites', lazy=True)
    project = db.relationship('Project', backref='invites', lazy=True)

class ProjectActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='project_activities', lazy=True)
    project = db.relationship('Project', backref='activities', lazy=True, order_by="ProjectActivity.timestamp.desc()")

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
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True)

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

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(50), default='🏆') 
    criteria_type = db.Column(db.String(50), nullable=False) # 'total_focus_minutes'
    criteria_value = db.Column(db.Integer, nullable=False)
    
    user_achievements = db.relationship('UserAchievement', backref='achievement', lazy=True)

class UserAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='achievements', lazy=True)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('study_room.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='messages', lazy=True)
    room = db.relationship('StudyRoom', backref=db.backref('messages', cascade="all, delete-orphan"), lazy=True)


