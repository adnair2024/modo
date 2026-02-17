from flask import render_template
from models import db, Notification, Event, EventCompletion
from datetime import datetime, timedelta, timezone

def format_minutes(minutes):
    if not minutes:
        return "0m"
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"

def get_pending_invite(project, user_id):
    from models import ProjectInvite
    return ProjectInvite.query.filter_by(project_id=project.id, recipient_id=user_id, status='pending').first()

def create_notification(user_id, message, type='info', event_id=None, project_id=None):
    n = Notification(user_id=user_id, message=message, type=type, event_id=event_id, project_id=project_id)
    db.session.add(n)
    db.session.commit()

class EventOccurrence:
    def __init__(self, event, start_time, is_completed):
        self.event = event
        self.id = event.id
        self.title = event.title
        self.description = event.description
        self.start_time = start_time
        self.end_time = start_time + (event.end_time - event.start_time)
        self.is_completed = is_completed

def expand_events(events, start_date, end_date):
    if not events:
        return []
    
    event_ids = [e.id for e in events]
    completions = EventCompletion.query.filter(
        EventCompletion.event_id.in_(event_ids),
        EventCompletion.date >= start_date,
        EventCompletion.date <= end_date
    ).all()
    
    comp_set = {(c.event_id, c.date) for c in completions}
    
    occurrences = []
    for event in events:
        current = event.start_time.replace(tzinfo=timezone.utc) if event.start_time.tzinfo is None else event.start_time
        
        if event.recurrence == 'none':
            if start_date <= current.date() <= end_date:
                is_done = (event.id, current.date()) in comp_set or event.is_completed
                occurrences.append(EventOccurrence(event, current, is_done))
        
        elif event.recurrence == 'daily':
            iter_date = max(current.date(), start_date)
            while iter_date <= end_date:
                occ_start = datetime.combine(iter_date, current.time()).replace(tzinfo=timezone.utc)
                is_done = (event.id, iter_date) in comp_set
                occurrences.append(EventOccurrence(event, occ_start, is_done))
                iter_date += timedelta(days=1)
                
    return occurrences

def log_project_action(project_id, action):
    from flask_login import current_user
    from models import ProjectActivity
    activity = ProjectActivity(project_id=project_id, user_id=current_user.id, action=action)
    db.session.add(activity)
    db.session.commit()

def check_task_access(task):
    from flask_login import current_user
    from models import ProjectMember
    if task.user_id == current_user.id:
        return True
    if task.section_id:
        # Check if user is member of project
        member = ProjectMember.query.filter_by(project_id=task.section.project_id, user_id=current_user.id).first()
        return member is not None
    return False

def check_event_notifications(user):
    from models import User, db
    if isinstance(user, int):
        user = db.session.get(User, user)
    
    if not user or not user.notify_event_start:
        return
        
    now = datetime.now(timezone.utc)
    # Check events starting in next X minutes
    events = Event.query.filter_by(user_id=user.id).all()
    for event in events:
        # Simplified: only check 'none' recurrence for now
        if event.recurrence == 'none':
            start = event.start_time.replace(tzinfo=timezone.utc) if event.start_time.tzinfo is None else event.start_time
            if now < start <= now + timedelta(minutes=user.event_notify_minutes or 30):
                # Check if already notified (prevent spam)
                existing = Notification.query.filter_by(user_id=user.id, event_id=event.id).first()
                if not existing:
                    create_notification(user.id, f"EVENT_STARTING: {event.title}", type='info', event_id=event.id)

def get_username_html(user):
    if user.is_verified:
        return f'{user.username} <svg class="inline w-3 h-3 text-accent fill-current" viewBox="0 0 24 24"><path d="M23 12l-2.44-2.79.34-3.69-3.61-.82-1.89-3.2L12 2.96 8.6 1.5 6.71 4.7l-3.61.81.34 3.7L1 12l2.44 2.79-.34 3.69 3.61.82 1.89 3.2L12 21.04l3.4 1.46 1.89-3.2 3.61-.82-.34-3.69L23 12zm-12.91 4.72l-3.8-3.81 1.48-1.48 2.32 2.33 5.85-5.87 1.48 1.48-7.33 7.35z"/></svg>'
    return user.username
