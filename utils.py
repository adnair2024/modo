from datetime import datetime, timedelta
from flask import current_app
from flask_login import current_user
from models import db, ProjectActivity, ProjectInvite, Notification, Event, ProjectMember, EventCompletion

class EventOccurrence:
    def __init__(self, event, start_datetime, is_completed):
        self.id = event.id
        self.title = event.title
        self.start_time = start_datetime
        self.is_completed = is_completed
        self.event_obj = event
        self.date_str = start_datetime.strftime('%Y-%m-%d')

def expand_events(events, start_date, end_date):
    occurrences = []
    event_ids = [e.id for e in events]
    completions = EventCompletion.query.filter(EventCompletion.event_id.in_(event_ids)).all()
    completion_map = {(c.event_id, c.date): True for c in completions}

    for event in events:
        event_start_date = event.start_time.date()
        current_date = max(start_date, event_start_date)
        
        while current_date <= end_date:
            match = False
            
            if event.recurrence == 'none':
                if current_date == event_start_date:
                    match = True
                if current_date > event_start_date:
                    break
            
            elif event.recurrence == 'daily':
                match = True
                
            elif event.recurrence == 'weekly':
                if current_date.weekday() == event.start_time.weekday():
                    match = True
                    
            elif event.recurrence == 'monthly':
                if current_date.day == event.start_time.day:
                    match = True
                    
            elif event.recurrence == 'custom':
                if event.recurrence_days:
                    days = [int(d) for d in event.recurrence_days.split(',') if d.strip()]
                    if current_date.weekday() in days:
                        match = True

            if match:
                occ_start = datetime.combine(current_date, event.start_time.time())
                is_done = False
                if event.recurrence == 'none':
                    is_done = event.is_completed
                
                if (event.id, current_date) in completion_map:
                    is_done = True
                
                occurrences.append(EventOccurrence(event, occ_start, is_done))

            current_date += timedelta(days=1)
            
    return occurrences

def log_project_action(project_id, action):
    activity = ProjectActivity(project_id=project_id, user_id=current_user.id, action=action)
    db.session.add(activity)

def get_pending_invite(user_id, project_id):
    return ProjectInvite.query.filter_by(recipient_id=user_id, project_id=project_id, status='pending').first()

def format_minutes(value):
    if not value:
        return "0mins"
    value = int(value)
    hours = value // 60
    minutes = value % 60
    if hours > 0:
        return f"{hours}hrs {minutes}mins"
    return f"{minutes}mins"

def get_username_html(user):
    badge = ""
    if user.is_verified:
        badge = '<svg class="w-4 h-4 text-blue-500 inline-block align-middle ml-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>'
    return f"<strong>{user.username}</strong>{badge}"

def create_notification(user_id, message, type='info', event_id=None, project_id=None):
    notif = Notification(user_id=user_id, message=message, type=type, event_id=event_id, project_id=project_id)
    db.session.add(notif)
    db.session.commit()

def check_event_notifications(user):
    if not user.notify_event_start:
        return

    notify_window = user.event_notify_minutes or 30
    limit = datetime.now() + timedelta(minutes=notify_window)
    
    events = Event.query.filter_by(user_id=user.id)\
        .filter(Event.start_time >= datetime.now())\
        .filter(Event.start_time <= limit)\
        .all()
        
    for event in events:
        existing = Notification.query.filter_by(user_id=user.id, event_id=event.id).first()
        if not existing:
            create_notification(
                user.id, 
                f"Upcoming Event: {event.title} starts in less than {notify_window} minutes.", 
                type='warning',
                event_id=event.id
            )

def check_task_access(task):
    if task.user_id == current_user.id:
        return True
    if task.section_id:
        project_id = task.section.project_id
        is_member = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
        if is_member:
            return True
    return False
