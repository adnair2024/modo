import os
import calendar
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, abort, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from flask_migrate import Migrate
from sqlalchemy import func, or_
from dotenv import load_dotenv
from models import db, User, Task, Subtask, FocusSession, Tag, Event, Notification, EventCompletion, Habit, HabitCompletion, Friendship, StudyRoom, Project, ProjectMember, ProjectSection, ProjectInvite, ProjectActivity
from auth import auth

load_dotenv()

app = Flask(__name__)

def log_project_action(project_id, action):
    activity = ProjectActivity(project_id=project_id, user_id=current_user.id, action=action)
    db.session.add(activity)

@app.template_filter('get_pending_invite')

def get_pending_invite(user_id, project_id):
    return ProjectInvite.query.filter_by(recipient_id=user_id, project_id=project_id, status='pending').first()
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_change_in_prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///db.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

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
    
    # Pre-fetch completions for these events in this range to avoid N+1
    # For simplicity, we might just fetch all completions for these events
    event_ids = [e.id for e in events]
    completions = EventCompletion.query.filter(EventCompletion.event_id.in_(event_ids)).all()
    completion_map = {(c.event_id, c.date): True for c in completions}

    for event in events:
        event_start_date = event.start_time.date()
        
        # Determine range intersection
        # We need to iterate from max(start_date, event_start_date) to end_date
        
        current_date = max(start_date, event_start_date)
        
        while current_date <= end_date:
            match = False
            
            if event.recurrence == 'none':
                if current_date == event_start_date:
                    match = True
                # Non-recurring only happens once, so we can break if we passed it
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
                # Calculate specific start datetime for this occurrence
                # Combine current_date with event.start_time time
                occ_start = datetime.combine(current_date, event.start_time.time())
                
                # Check completion
                # For non-recurring, we can check event.is_completed too for backward compatibility
                is_done = False
                if event.recurrence == 'none':
                    is_done = event.is_completed
                
                # Check specific completion record
                if (event.id, current_date) in completion_map:
                    is_done = True
                
                occurrences.append(EventOccurrence(event, occ_start, is_done))

            current_date += timedelta(days=1)
            
    return occurrences

@app.template_filter('format_minutes')
def format_minutes(value):
    if not value:
        return "0mins"
    value = int(value)
    hours = value // 60
    minutes = value % 60
    if hours > 0:
        return f"{hours}hrs {minutes}mins"
    return f"{minutes}mins"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_username_html(user):
    badge = ""
    if user.is_verified:
        badge = '<svg class="w-4 h-4 text-blue-500 inline-block align-middle ml-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>'
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
    
    # Find events starting between now and limit
    # This logic only finds BASE events. Ideally we should check expanded events.
    # For now, keeping as is for base non-recurring events or if recurrence matches today.
    events = Event.query.filter_by(user_id=user.id)\
        .filter(Event.start_time >= datetime.now())\
        .filter(Event.start_time <= limit)\
        .all()
        
    for event in events:
        # Check if notification already exists for this event
        existing = Notification.query.filter_by(user_id=user.id, event_id=event.id).first()
        if not existing:
            create_notification(
                user.id, 
                f"Upcoming Event: {event.title} starts in less than {notify_window} minutes.", 
                type='warning',
                event_id=event.id
            )

app.register_blueprint(auth)

@app.route('/')
@login_required
def index():
    query = Task.query.filter_by(user_id=current_user.id)

    # Search
    q = request.args.get('q')
    if q:
        query = query.filter(Task.title.ilike(f'%{q}%'))

    # Date Range
    date_start_str = request.args.get('date_start')
    date_end_str = request.args.get('date_end')
    
    if date_start_str:
        try:
            date_start = datetime.strptime(date_start_str, '%Y-%m-%d')
            query = query.filter(Task.due_date >= date_start)
        except ValueError:
            pass
            
    if date_end_str:
        try:
            date_end = datetime.strptime(date_end_str, '%Y-%m-%d')
            # Set to end of day
            date_end = date_end.replace(hour=23, minute=59, second=59)
            query = query.filter(Task.due_date <= date_end)
        except ValueError:
            pass

    # Tags
    tags = request.args.getlist('tags')
    if tags:
        query = query.join(Task.tags).filter(Tag.name.in_(tags)).distinct()
    
    # Sorting
    sort_by = request.args.get('sort_by', 'created_at')

    # If searching or filtering, show all matches sorted by status and date
    if q or date_start_str or date_end_str or tags:
        # For search results, we still want the "nag" logic if possible, but let's stick to the current pattern for simplicity
        # or better, apply the same sort logic.
        # Let's apply the uniform sort logic to everything.
        all_tasks = query.all()
        
        # Sort logic
        now = datetime.now()
        
        def get_sort_key(t):
            is_overdue = t.due_date and t.due_date < now and t.status != 'done'
            status_rank = 1 if t.status == 'done' else 0
            overdue_rank = 0 if is_overdue else 1 
            
            if sort_by == 'priority':
                 sort_val = -t.priority
            elif sort_by == 'due_date':
                 sort_val = t.due_date.timestamp() if t.due_date else 9999999999
            else: # created_at
                 sort_val = -t.created_at.timestamp()
            
            return (status_rank, overdue_rank, sort_val)

        all_tasks.sort(key=get_sort_key)
        tasks = all_tasks
        has_more_completed = False
    else:
        # Default view: All Todo, Limited Done
        todo_tasks = query.filter(Task.status != 'done').all()
        
        now = datetime.now()
        overdue = [t for t in todo_tasks if t.due_date and t.due_date < now]
        regular = [t for t in todo_tasks if t not in overdue]
        
        # Sort overdue: Priority DESC, then Due Date ASC
        overdue.sort(key=lambda t: (-t.priority, t.due_date if t.due_date else datetime.max))
        
        # Sort regular
        if sort_by == 'priority':
            regular.sort(key=lambda t: (-t.priority, t.created_at))
        elif sort_by == 'due_date':
            regular.sort(key=lambda t: (t.due_date if t.due_date else datetime.max))
        else: # created_at
            regular.sort(key=lambda t: t.created_at, reverse=True)
            
        todo_sorted = overdue + regular
        
        # Check if 'show_all_done' is in args
        show_all_done = request.args.get('show_all_done') == 'true'
        
        done_query = query.filter(Task.status == 'done').order_by(Task.created_at.desc())
        total_done = done_query.count()
        
        if show_all_done:
            done_tasks = done_query.all()
            has_more_completed = False
        else:
            done_tasks = done_query.limit(10).all()
            has_more_completed = total_done > 10
            
        tasks = todo_sorted + done_tasks

    all_tags = Tag.query.all()

    if request.headers.get('HX-Request'):
        return render_template('partials/task_list.html', tasks=tasks, has_more_completed=has_more_completed, now=datetime.now())

    # Upcoming Events Logic
    now = datetime.now()
    today_start = now.date()
    week_end = today_start + timedelta(days=7)
    
    # 1. Fetch all events that *could* be relevant. 
    #    This includes:
    #    - Non-recurring events starting in the range [today, week_end]
    #    - Recurring events starting BEFORE week_end (since they might repeat into the window)
    
    # Actually, simpler: just fetch ALL user events and let the python expander handle filtering efficiently
    # unless there are thousands. For a personal app, hundreds is fine.
    
    all_events = Event.query.filter_by(user_id=current_user.id).all()
    
    occurrences = expand_events(all_events, today_start, week_end)
    occurrences.sort(key=lambda x: x.start_time)

    grouped_events = {
        'Today': [],
        'Tomorrow': [],
        'This Week': []
    }
    
    tomorrow_start = datetime.combine(today_start + timedelta(days=1), datetime.min.time())
    week_end_dt = datetime.combine(today_start + timedelta(days=7), datetime.min.time())
    
    for occ in occurrences:
        if occ.start_time < tomorrow_start:
            grouped_events['Today'].append(occ)
        elif occ.start_time < tomorrow_start + timedelta(days=1):
            grouped_events['Tomorrow'].append(occ)
        elif occ.start_time < week_end_dt:
            grouped_events['This Week'].append(occ)
            
    # Daily Habits for Home Screen
    today = datetime.now().date()
    all_user_habits = Habit.query.filter_by(user_id=current_user.id).all()
    today_completions = HabitCompletion.query.filter(
        HabitCompletion.habit_id.in_([h.id for h in all_user_habits]),
        HabitCompletion.date == today
    ).all()
    today_comp_ids = {c.habit_id for c in today_completions}
    
    daily_habits = []
    for h in all_user_habits:
        daily_habits.append({
            'id': h.id,
            'title': h.title,
            'is_done': h.id in today_comp_ids
        })

    return render_template('index.html', 
                           tasks=tasks, 
                           all_tags=all_tags, 
                           has_more_completed=has_more_completed, 
                           now=datetime.now(), 
                           grouped_events=grouped_events,
                           daily_habits=daily_habits,
                           today_str=today.strftime('%Y-%m-%d'))

@app.route('/toggle_event/<int:event_id>', methods=['POST'])
@login_required
def toggle_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)
        
    date_str = request.args.get('date')
    if not date_str:
        # Fallback for old calls or simple non-recurring toggle without date
        # Just toggle the base event status
        event.is_completed = not event.is_completed
        db.session.commit()
        # Create a dummy occurrence for response
        occ = EventOccurrence(event, event.start_time, event.is_completed)
        return render_template('partials/event_item_small.html', event=occ)

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return '', 400

    # Check if completion exists
    completion = EventCompletion.query.filter_by(event_id=event.id, date=target_date).first()
    
    is_done = False
    if completion:
        db.session.delete(completion)
        is_done = False
    else:
        new_comp = EventCompletion(event_id=event.id, user_id=current_user.id, date=target_date)
        db.session.add(new_comp)
        is_done = True
        
    db.session.commit()
    
    # Construct occurrence object for re-rendering
    # We need the correct datetime.
    # We assume the time is same as base event.
    occ_start = datetime.combine(target_date, event.start_time.time())
    occ = EventOccurrence(event, occ_start, is_done)
    
    return render_template('partials/event_item_small.html', event=occ)

@app.route('/timer')
@login_required
def timer():
    tasks = Task.query.filter_by(user_id=current_user.id).filter(Task.status != 'done').order_by(Task.created_at.desc()).all()
    return render_template('timer.html', tasks=tasks)

@app.route('/leaderboard')
@login_required
def leaderboard():
    from sqlalchemy import func
    
    filter_type = request.args.get('filter', 'all')
    category = request.args.get('category', 'focus')
    
    now = datetime.now()
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)

    if category == 'habits':
        query = db.session.query(
            User,
            func.count(HabitCompletion.id).label('score')
        ).join(Habit, User.id == Habit.user_id)\
         .join(HabitCompletion, Habit.id == HabitCompletion.habit_id)\
         .group_by(User.id)\
         .order_by(func.count(HabitCompletion.id).desc())
        
        if filter_type == 'weekly':
            query = query.filter(HabitCompletion.date >= start_of_week.date(), HabitCompletion.date <= end_of_week.date())
            
    elif category == 'sync':
        query = db.session.query(
            User,
            func.sum(FocusSession.minutes).label('score')
        ).join(FocusSession, User.id == FocusSession.user_id)\
         .filter(FocusSession.partner_id.isnot(None))\
         .group_by(User.id)\
         .order_by(func.sum(FocusSession.minutes).desc())
        
        if filter_type == 'weekly':
            query = query.filter(FocusSession.date >= start_of_week, FocusSession.date <= end_of_week)
            
    else: # focus
        query = db.session.query(
            User,
            func.sum(FocusSession.minutes).label('score')
        ).join(FocusSession, User.id == FocusSession.user_id)\
         .group_by(User.id)\
         .order_by(func.sum(FocusSession.minutes).desc())

        if filter_type == 'weekly':
            query = query.filter(FocusSession.date >= start_of_week, FocusSession.date <= end_of_week)

    results = query.limit(10).all()
    
    return render_template('leaderboard.html', leaders=results, filter_type=filter_type, category=category)

@app.route('/api/log_session', methods=['POST'])
@login_required
def log_session():
    data = request.json
    minutes = data.get('minutes')
    task_id = data.get('task_id')
    room_id = data.get('room_id')
    
    if minutes:
        session = FocusSession(minutes=minutes, user_id=current_user.id, task_id=task_id)
        
        if room_id:
            room = StudyRoom.query.get(room_id)
            if room:
                # Identify partner
                partner_id = None
                if room.host_id == current_user.id:
                    partner_id = room.guest_id
                elif room.guest_id == current_user.id:
                    partner_id = room.host_id
                
                session.partner_id = partner_id

        db.session.add(session)
        
        if task_id:
            task = Task.query.get(task_id)
            if task and check_task_access(task):
                task.completed_pomodoros += 1
                if task.completed_pomodoros >= task.estimated_pomodoros:
                    task.status = 'done'
        
        if current_user.notify_pomodoro:
            create_notification(current_user.id, f"Focus session of {minutes} mins completed!", type='success')

        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 400

# HTMX endpoints
@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    title = request.form.get('title')
    description = request.form.get('description')
    due_date_str = request.form.get('due_date')
    est_pomodoros = request.form.get('estimated_pomodoros', type=int, default=1)
    priority = request.form.get('priority', type=int, default=1)
    tags_str = request.form.get('tags')

    if title:
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass

        new_task = Task(
            title=title, 
            description=description,
            due_date=due_date,
            estimated_pomodoros=est_pomodoros,
            priority=priority,
            user_id=current_user.id
        )

        if tags_str:
            tag_names = [t.strip() for t in tags_str.split(',') if t.strip()]
            for name in tag_names:
                tag = Tag.query.filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name)
                    db.session.add(tag)
                new_task.tags.append(tag)

        db.session.add(new_task)
        db.session.commit()
        return render_template('partials/task_item.html', task=new_task, now=datetime.now())
    return '', 400

def check_task_access(task):
    if task.user_id == current_user.id:
        return True
    if task.section_id:
        # Check if user is a member of the project this section belongs to
        project_id = task.section.project_id
        is_member = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
        if is_member:
            return True
    return False

@app.route('/delete_task/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not check_task_access(task):
        abort(403)
    
    if task.section_id:
        log_project_action(task.section.project_id, f"Deleted task: {task.title}")

    # Decouple dependencies to prevent Foreign Key errors
    # 1. Unset current_task for any user (specifically current_user, but safely check all)
    User.query.filter_by(current_task_id=task.id).update({'current_task_id': None})
    
    # 2. Unset task_id for any linked focus sessions
    FocusSession.query.filter_by(task_id=task.id).update({'task_id': None})

    db.session.delete(task)
    db.session.commit()
    return ''

@app.route('/toggle_task/<int:task_id>', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not check_task_access(task):
        abort(403)
    
    if task.status == 'done':
        task.status = 'todo'
        if task.section_id:
            log_project_action(task.section.project_id, f"Reopened task: {task.title}")
    else:
        task.status = 'done'
        if task.section_id:
            log_project_action(task.section.project_id, f"Completed task: {task.title}")
    
    db.session.commit()
    
    # If it's a project task, and we are not on the index page, we might want to just return the item
    # But for now, if the target is task-list, we do the full re-fetch.
    # If not, we can return just the item.
    if request.headers.get('HX-Target') != 'task-list':
        return render_template('partials/task_item.html', task=task, now=datetime.now())

    # Re-fetch with filters and pagination logic for index page
    query = Task.query.filter_by(user_id=current_user.id)

    # Search
    q = request.values.get('q')
    if q:
        query = query.filter(Task.title.ilike(f'%{q}%'))

    # Date Range
    date_start_str = request.values.get('date_start')
    date_end_str = request.values.get('date_end')
    
    if date_start_str:
        try:
            date_start = datetime.strptime(date_start_str, '%Y-%m-%d')
            query = query.filter(Task.due_date >= date_start)
        except ValueError:
            pass
            
    if date_end_str:
        try:
            date_end = datetime.strptime(date_end_str, '%Y-%m-%d')
            date_end = date_end.replace(hour=23, minute=59, second=59)
            query = query.filter(Task.due_date <= date_end)
        except ValueError:
            pass

    # Tags
    tags = request.values.getlist('tags')
    if tags:
        query = query.join(Task.tags).filter(Tag.name.in_(tags)).distinct()
    
    # Sorting
    sort_by = request.values.get('sort_by', 'created_at')

    if q or date_start_str or date_end_str or tags:
        all_tasks = query.all()
        now = datetime.now()
        
        def get_sort_key(t):
            is_overdue = t.due_date and t.due_date < now and t.status != 'done'
            status_rank = 1 if t.status == 'done' else 0
            overdue_rank = 0 if is_overdue else 1 
            
            if sort_by == 'priority':
                 sort_val = -t.priority
            elif sort_by == 'due_date':
                 sort_val = t.due_date.timestamp() if t.due_date else 9999999999
            else: # created_at
                 sort_val = -t.created_at.timestamp()
            
            return (status_rank, overdue_rank, sort_val)

        all_tasks.sort(key=get_sort_key)
        tasks = all_tasks
        has_more_completed = False
    else:
        todo_tasks = query.filter(Task.status != 'done').all()
        now = datetime.now()
        overdue = [t for t in todo_tasks if t.due_date and t.due_date < now]
        regular = [t for t in todo_tasks if t not in overdue]
        
        overdue.sort(key=lambda t: (-t.priority, t.due_date if t.due_date else datetime.max))
        
        if sort_by == 'priority':
            regular.sort(key=lambda t: (-t.priority, t.created_at))
        elif sort_by == 'due_date':
            regular.sort(key=lambda t: (t.due_date if t.due_date else datetime.max))
        else:
            regular.sort(key=lambda t: t.created_at, reverse=True)
            
        todo_sorted = overdue + regular
        
        show_all_done = request.values.get('show_all_done') == 'true'
        
        done_query = query.filter(Task.status == 'done').order_by(Task.created_at.desc())
        total_done = done_query.count()
        
        if show_all_done:
            done_tasks = done_query.all()
            has_more_completed = False
        else:
            done_tasks = done_query.limit(10).all()
            has_more_completed = total_done > 10
            
        tasks = todo_sorted + done_tasks

    return render_template('partials/task_list.html', tasks=tasks, has_more_completed=has_more_completed, now=datetime.now())

@app.route('/task/<int:task_id>/edit', methods=['GET'])
@login_required
def get_edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not check_task_access(task):
        abort(403)
    return render_template('partials/task_edit.html', task=task)

@app.route('/task/<int:task_id>', methods=['PUT', 'POST'])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not check_task_access(task):
        abort(403)

    title = request.form.get('title')
    description = request.form.get('description')
    due_date_str = request.form.get('due_date')
    est_pomodoros = request.form.get('estimated_pomodoros', type=int)
    priority = request.form.get('priority', type=int)
    tags_str = request.form.get('tags')

    if title:
        task.title = title
        task.description = description
        if est_pomodoros:
            task.estimated_pomodoros = est_pomodoros
        if priority:
            task.priority = priority

        if due_date_str:
            try:
                task.due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        else:
            task.due_date = None

        if tags_str is not None:
            task.tags = []
            tag_names = [t.strip() for t in tags_str.split(',') if t.strip()]
            for name in tag_names:
                tag = Tag.query.filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name)
                    db.session.add(tag)
                task.tags.append(tag)

    db.session.commit()
    return render_template('partials/task_item.html', task=task, now=datetime.now())

@app.route('/task/<int:task_id>/item', methods=['GET'])
@login_required
def get_task_item(task_id):
    task = Task.query.get_or_404(task_id)
    if not check_task_access(task):
        abort(403)
    return render_template('partials/task_item.html', task=task, now=datetime.now())

@app.route('/api/next_priority_task', methods=['GET'])
@login_required
def get_next_priority_task():
    task = Task.query.filter_by(user_id=current_user.id, status='todo')\
        .order_by(Task.priority.desc(), Task.created_at.asc()).first()
    if task:
        return jsonify({'id': task.id, 'title': task.title})
    return jsonify({'id': None})

@app.route('/stats')
@login_required
def personal_stats():
    total_minutes = db.session.query(func.sum(FocusSession.minutes)).filter_by(user_id=current_user.id).scalar() or 0
    total_sessions = FocusSession.query.filter_by(user_id=current_user.id).count()
    
    # Sync Stats
    sync_sessions_query = FocusSession.query.filter_by(user_id=current_user.id).filter(FocusSession.partner_id.isnot(None))
    sync_sessions_count = sync_sessions_query.count()
    sync_minutes = db.session.query(func.sum(FocusSession.minutes))\
        .filter_by(user_id=current_user.id)\
        .filter(FocusSession.partner_id.isnot(None)).scalar() or 0
        
    # Top Partner
    top_partner = None
    if sync_sessions_count > 0:
        # Group by partner_id, count
        top_partner_id = db.session.query(FocusSession.partner_id, func.count(FocusSession.partner_id))\
            .filter_by(user_id=current_user.id)\
            .filter(FocusSession.partner_id.isnot(None))\
            .group_by(FocusSession.partner_id)\
            .order_by(func.count(FocusSession.partner_id).desc())\
            .first()
            
        if top_partner_id:
            top_partner = User.query.get(top_partner_id[0])

    # Weekly Stats
    now = datetime.now()
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    weekly_minutes = db.session.query(func.sum(FocusSession.minutes))\
        .filter_by(user_id=current_user.id)\
        .filter(FocusSession.date >= start_of_week).scalar() or 0

    # Define Year Boundaries
    current_year = now.year
    year_start = datetime(current_year, 1, 1).date()
    year_end = datetime(current_year, 12, 31).date()

    # Heatmap Data (Current Year)
    sessions = db.session.query(FocusSession.date, FocusSession.minutes)\
        .filter_by(user_id=current_user.id)\
        .filter(FocusSession.date >= year_start, FocusSession.date <= year_end).all()
    
    heatmap_data = {}
    for s in sessions:
        date_str = s.date.strftime('%Y-%m-%d')
        heatmap_data[date_str] = heatmap_data.get(date_str, 0) + s.minutes

    # Habit Heatmap (Current Year)
    habit_completions = HabitCompletion.query.join(Habit).filter(
        Habit.user_id == current_user.id,
        HabitCompletion.date >= year_start,
        HabitCompletion.date <= year_end
    ).all()
    
    habit_heatmap_data = {}
    for c in habit_completions:
        d_str = c.date.strftime('%Y-%m-%d')
        habit_heatmap_data[d_str] = habit_heatmap_data.get(d_str, 0) + 1

    return render_template('stats.html', 
                           total_minutes=total_minutes, 
                           total_sessions=total_sessions,
                           weekly_minutes=weekly_minutes,
                           sync_sessions_count=sync_sessions_count,
                           sync_minutes=sync_minutes,
                           top_partner=top_partner,
                           heatmap_data=heatmap_data,
                           habit_heatmap_data=habit_heatmap_data,
                           current_year=current_year)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/api/update_settings', methods=['POST'])
@login_required
def update_settings():
    data = request.json
    if 'theme' in data:
        current_user.theme_preference = data['theme']
    if 'accent_color' in data:
        current_user.accent_color = data['accent_color']
    if 'auto_start_break' in data:
        current_user.auto_start_break = data['auto_start_break']
    if 'auto_start_focus' in data:
        current_user.auto_start_focus = data['auto_start_focus']
    if 'auto_select_priority' in data:
        current_user.auto_select_priority = data['auto_select_priority']
    if 'focus_duration' in data:
        current_user.focus_duration = int(data['focus_duration'])
    if 'break_duration' in data:
        current_user.break_duration = int(data['break_duration'])
    if 'notify_pomodoro' in data:
        current_user.notify_pomodoro = data['notify_pomodoro']
    if 'notify_event_start' in data:
        current_user.notify_event_start = data['notify_event_start']
    if 'event_notify_minutes' in data:
        current_user.event_notify_minutes = int(data['event_notify_minutes'])
    if 'show_last_seen' in data:
        current_user.show_last_seen = data['show_last_seen']
        
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/notifications')
@login_required
def get_notifications():
    check_event_notifications(current_user)
    
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False)\
        .order_by(Notification.created_at.desc()).all()
        
    if request.headers.get('HX-Request'):
        return render_template('partials/notification_list.html', notifications=notifications)
    
    return jsonify([{
        'id': n.id, 
        'message': n.message, 
        'type': n.type,
        'created_at': n.created_at.isoformat()
    } for n in notifications])

@app.route('/api/notifications/mark_read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        abort(403)
    notif.is_read = True
    db.session.commit()
    return ''

@app.route('/api/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return ''

@app.route('/schedule')
@login_required
def schedule():
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    
    if month > 12:
        month = 1
        year += 1
    elif month < 1:
        month = 12
        year -= 1
        
    cal_matrix = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
    
    events = Event.query.filter_by(user_id=current_user.id).all()
    
    return render_template('schedule.html', 
                           year=year, month=month, month_name=month_name, 
                           calendar_matrix=cal_matrix, events=events)

@app.route('/schedule/add', methods=['POST'])
@login_required
def add_event():
    title = request.form.get('title')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    recurrence = request.form.get('recurrence', 'none')
    recurrence_days_list = request.form.getlist('recurrence_days')
    
    if title and start_time_str and end_time_str:
        try:
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            
            recurrence_days_str = ",".join(recurrence_days_list) if recurrence_days_list else None

            new_event = Event(
                title=title,
                start_time=start_time,
                end_time=end_time,
                recurrence=recurrence,
                recurrence_days=recurrence_days_str,
                user_id=current_user.id
            )
            db.session.add(new_event)
            db.session.commit()
        except ValueError:
            pass
            
    return redirect(url_for('schedule'))

@app.route('/schedule/event/<int:event_id>/edit', methods=['GET'])
@login_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)
    return render_template('partials/event_edit.html', event=event)

@app.route('/schedule/event/<int:event_id>/update', methods=['POST'])
@login_required
def update_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)

    title = request.form.get('title')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    recurrence = request.form.get('recurrence')
    recurrence_days_list = request.form.getlist('recurrence_days')

    if title: event.title = title
    if recurrence: event.recurrence = recurrence
    
    # Always update recurrence_days, even if empty (clearing it)
    event.recurrence_days = ",".join(recurrence_days_list) if recurrence_days_list else None

    if start_time_str:
        try:
            event.start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
            
    if end_time_str:
        try:
            event.end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass

    db.session.commit()
    return render_template('partials/event_item.html', event=event)

@app.route('/schedule/event/<int:event_id>/item', methods=['GET'])
@login_required
def get_event_item(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)
    return render_template('partials/event_item.html', event=event)

@app.route('/schedule/delete/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)
        
    # Decouple dependencies
    Notification.query.filter_by(event_id=event.id).update({'event_id': None})
    
    db.session.delete(event)
    db.session.commit()
    return redirect(url_for('schedule'))

@app.route('/habits')
@login_required
def habits():
    user_habits = Habit.query.filter_by(user_id=current_user.id).order_by(Habit.created_at.desc()).all()
    
    # Generate last 7 days (ending today)
    today = datetime.now().date()
    dates = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        dates.append(d)
        
    # Pre-fetch completions
    # We want completions for these habits in this date range
    start_date = dates[0]
    end_date = dates[-1]
    
    habit_ids = [h.id for h in user_habits]
    completions = HabitCompletion.query.filter(
        HabitCompletion.habit_id.in_(habit_ids),
        HabitCompletion.date >= start_date,
        HabitCompletion.date <= end_date
    ).all()
    
    # Map: (habit_id, date) -> True
    comp_map = {(c.habit_id, c.date): True for c in completions}
    
    habits_data = []
    for h in user_habits:
        status_list = []
        # Build grid data
        for d in dates:
            is_done = (h.id, d) in comp_map
            status_list.append({
                'date': d.strftime('%Y-%m-%d'),
                'is_done': is_done,
                'is_today': (d == today),
                'day_name': d.strftime('%a') # Mon, Tue...
            })
            
        habits_data.append({
            'habit': h,
            'days': status_list
        })

    # Year Heatmap Data
    current_year = today.year
    year_start = datetime(current_year, 1, 1).date()
    year_end = datetime(current_year, 12, 31).date()
    
    year_completions = HabitCompletion.query.filter(
        HabitCompletion.habit_id.in_(habit_ids),
        HabitCompletion.date >= year_start,
        HabitCompletion.date <= year_end
    ).all()
    
    heatmap_data = {}
    for c in year_completions:
        d_str = c.date.strftime('%Y-%m-%d')
        heatmap_data[d_str] = heatmap_data.get(d_str, 0) + 1
        
    return render_template('habits.html', habits=habits_data, dates=dates, heatmap_data=heatmap_data, current_year=current_year)

@app.route('/habits/add', methods=['POST'])
@login_required
def add_habit():
    title = request.form.get('title')
    if title:
        habit = Habit(title=title, user_id=current_user.id)
        db.session.add(habit)
        db.session.commit()
    return redirect(url_for('habits'))

@app.route('/habits/toggle/<int:habit_id>', methods=['POST'])
@login_required
def toggle_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        abort(403)
        
    date_str = request.args.get('date')
    if not date_str:
        target_date = datetime.now().date()
    else:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return '', 400
            
    completion = HabitCompletion.query.filter_by(habit_id=habit.id, date=target_date).first()
    
    is_done = False
    if completion:
        db.session.delete(completion)
        is_done = False
    else:
        new_comp = HabitCompletion(habit_id=habit.id, date=target_date)
        db.session.add(new_comp)
        is_done = True
        
    db.session.commit()
    
    # Return a partial for the cell if using HTMX, or the whole row.
    # For simplicity, returning a button state or we can just reload.
    # Let's try to return just the button/cell HTML.
    # We'll construct the button HTML manually or use a tiny template.
    # Actually, simpler to just return a JSON status or tiny HTML fragment.
    
    # UI Logic: The clicked element is the circle. We swap it.
    
    # Return the new state class/html
    if request.headers.get('HX-Request'):
        is_today = (target_date == datetime.now().date())
        day_data = {'date': target_date.strftime('%Y-%m-%d'), 'is_done': is_done, 'is_today': is_today}
        
        # Check if it's from the home screen pill or the habits grid
        target = request.headers.get('HX-Target', '')
        if target.startswith('habit-home-'):
            return render_template('partials/habit_item_home.html', habit=habit, day=day_data)
            
        return render_template('partials/habit_cell.html', habit=habit, day=day_data)

    return redirect(url_for('habits'))

@app.route('/habits/delete/<int:habit_id>', methods=['POST'])
@login_required
def delete_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        abort(403)
    db.session.delete(habit)
    db.session.commit()
    return redirect(url_for('habits'))

@app.route('/u/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    # Check friendship status
    friendship = Friendship.query.filter(
        or_(
            (Friendship.user_id == current_user.id) & (Friendship.friend_id == user.id),
            (Friendship.user_id == user.id) & (Friendship.friend_id == current_user.id)
        )
    ).first()
    
    status = 'none'
    if friendship:
        status = friendship.status
        if status == 'pending':
            if friendship.user_id == current_user.id:
                status = 'sent'
            else:
                status = 'received'

    # Stats
    total_minutes = db.session.query(func.sum(FocusSession.minutes)).filter_by(user_id=user.id).scalar() or 0
    total_sessions = FocusSession.query.filter_by(user_id=user.id).count()

    # Recent activity (simple log)
    recent_sessions = FocusSession.query.filter_by(user_id=user.id).order_by(FocusSession.date.desc()).limit(5).all()
    
    return render_template('profile.html', user=user, status=status, total_minutes=total_minutes, 
                           total_sessions=total_sessions, recent_sessions=recent_sessions, now=datetime.utcnow())

@app.route('/friend/request/<int:user_id>', methods=['POST'])
@login_required
def send_friend_request(user_id):
    target_user = User.query.get_or_404(user_id)
    if target_user.id == current_user.id:
        return '', 400
        
    existing = Friendship.query.filter(
        or_(
            (Friendship.user_id == current_user.id) & (Friendship.friend_id == target_user.id),
            (Friendship.user_id == target_user.id) & (Friendship.friend_id == current_user.id)
        )
    ).first()
    
    if not existing:
        friendship = Friendship(user_id=current_user.id, friend_id=target_user.id, status='pending')
        db.session.add(friendship)
        
        accept_url = url_for('respond_friend_request', user_id=current_user.id, action='accept')
        reject_url = url_for('respond_friend_request', user_id=current_user.id, action='reject')
        
        user_html = get_username_html(current_user)
        msg = f"""
        {user_html} sent you a friend request.<br>
        <div class='mt-2 flex gap-2'>
            <form action='{accept_url}' method='POST' style='display:inline'>
                <button class='bg-indigo-600 text-white px-3 py-1 rounded text-xs hover:bg-indigo-700'>Accept</button>
            </form>
            <form action='{reject_url}' method='POST' style='display:inline'>
                <button class='bg-gray-300 text-gray-700 px-3 py-1 rounded text-xs hover:bg-gray-400'>Decline</button>
            </form>
        </div>
        """
        
        create_notification(
            target_user.id,
            msg,
            type='friend_request'
        )
        
        db.session.commit()
        
    return redirect(url_for('profile', username=target_user.username))

@app.route('/friend/respond/<int:user_id>/<action>', methods=['POST'])
@login_required
def respond_friend_request(user_id, action):
    # Find the friendship where I am the friend_id and user_id is the requester
    friendship = Friendship.query.filter_by(user_id=user_id, friend_id=current_user.id, status='pending').first()
    
    if not friendship and action != 'remove':
        abort(404)
        
    if action == 'accept':
        friendship.status = 'accepted'
        create_notification(
            user_id,
            f"{get_username_html(current_user)} accepted your friend request!",
            type='success'
        )
    elif action == 'reject':
        db.session.delete(friendship)
    elif action == 'remove':
        # Find any friendship between them
        friendship = Friendship.query.filter(
            or_(
                (Friendship.user_id == current_user.id) & (Friendship.friend_id == user_id),
                (Friendship.user_id == user_id) & (Friendship.friend_id == current_user.id)
            )
        ).first()
        if friendship:
            db.session.delete(friendship)
            
    db.session.commit()
    
    # Redirect back to where we came from if possible
    referrer = request.referrer
    if referrer and 'friends' in referrer:
        return redirect(url_for('friends_list'))
        
    target_user = User.query.get(user_id)
    return redirect(url_for('profile', username=target_user.username))

@app.route('/study/join/<int:room_id>')
@login_required
def join_study_room(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if room.guest_id != current_user.id:
        abort(403)
        
    if room.status == 'waiting':
        room.status = 'active'
        db.session.commit()
        
    return redirect(url_for('study_room', room_id=room.id))

@app.route('/study/room/<int:room_id>')
@login_required
def study_room(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if current_user.id not in [room.host_id, room.guest_id]:
        abort(403)
        
    other_user_id = room.guest_id if room.host_id == current_user.id else room.host_id
    other_user = User.query.get(other_user_id)
    
    return render_template('study_room.html', room=room, other_user=other_user)

@app.route('/study/room/<int:room_id>/poll')
@login_required
def study_room_poll(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    # Simple polling to update status
    if request.headers.get('HX-Request'):
        if room.status == 'active':
             return render_template('partials/study_active.html', room=room)
        return '' # No change
    return ''

@app.route('/api/study/control', methods=['POST'])
@login_required
def study_control():
    data = request.json
    room_id = data.get('room_id')
    action = data.get('action') # start, pause, reset, skip
    
    room = StudyRoom.query.get_or_404(room_id)
    if current_user.id not in [room.host_id, room.guest_id]:
        abort(403)
        
    duration = (room.focus_duration if room.active_mode == 'focus' else room.break_duration) * 60
        
    if action == 'start':
        if not room.active_start_time:
            # Starting (or Resuming)
            # If seconds_remaining is set (paused state), use it. Else full duration.
            if room.seconds_remaining is None:
                room.seconds_remaining = duration
                
            room.active_start_time = datetime.utcnow()
            
    elif action == 'pause':
        if room.active_start_time:
            # Calculate elapsed and save remaining
            elapsed = (datetime.utcnow() - room.active_start_time).total_seconds()
            current_rem = room.seconds_remaining if room.seconds_remaining is not None else duration
            room.seconds_remaining = max(0, int(current_rem - elapsed))
            room.active_start_time = None
        
    elif action == 'reset':
        room.active_start_time = None
        room.seconds_remaining = None # Will reset to full duration on next start
        room.active_mode = 'focus'
        
    elif action == 'skip':
        room.active_start_time = None
        room.seconds_remaining = None
        room.active_mode = 'break' if room.active_mode == 'focus' else 'focus'
        
    db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/api/study/state/<int:room_id>')
@login_required
def study_state(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if current_user.id not in [room.host_id, room.guest_id]:
        abort(403)
        
    duration = (room.focus_duration if room.active_mode == 'focus' else room.break_duration) * 60
    
    seconds_remaining = duration
    is_running = False
    
    if room.active_start_time:
        # Running
        elapsed = (datetime.utcnow() - room.active_start_time).total_seconds()
        start_rem = room.seconds_remaining if room.seconds_remaining is not None else duration
        seconds_remaining = max(0, start_rem - elapsed)
        is_running = True
    else:
        # Paused or Stopped
        if room.seconds_remaining is not None:
            seconds_remaining = room.seconds_remaining
        else:
            seconds_remaining = duration
            
    # Resolve Tasks
    host = User.query.get(room.host_id)
    guest = User.query.get(room.guest_id) if room.guest_id else None
    
    my_task = "No Task"
    other_task = "No Task"
    
    if current_user.id == room.host_id:
        if host.current_task: my_task = host.current_task.title
        if guest and guest.current_task: other_task = guest.current_task.title
    else:
        if guest and guest.current_task: my_task = guest.current_task.title
        if host.current_task: other_task = host.current_task.title

    return jsonify({
        'mode': room.active_mode,
        'is_running': is_running,
        'seconds_remaining': int(seconds_remaining),
        'duration': duration,
        'my_task': my_task,
        'other_task': other_task
    })

@app.route('/study/leave/<int:room_id>', methods=['POST'])
@login_required
def leave_study_room(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if current_user.id in [room.host_id, room.guest_id]:
        db.session.delete(room)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/api/sync_presence', methods=['POST'])
@login_required
def sync_presence():
    data = request.json
    status = data.get('status') # 'running', 'paused', 'stopped'
    mode = data.get('mode') # 'focus', 'break'
    seconds_left = data.get('seconds_left')
    task_id = data.get('task_id')
    
    current_user.last_seen = datetime.utcnow()
    current_user.current_focus_mode = mode
    
    if status == 'running' and seconds_left is not None:
        # Calculate expected end time
        current_user.current_focus_end = datetime.utcnow() + timedelta(seconds=int(seconds_left))
        # Start time is roughly now - (duration - seconds_left) but strictly we only care about end for countdown
        if not current_user.current_focus_start: 
             current_user.current_focus_start = datetime.utcnow() # Reset if new session
    else:
        current_user.current_focus_end = None # Not running
        
    if task_id:
        current_user.current_task_id = int(task_id)
    else:
        current_user.current_task_id = None
        
    db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/friends/search', methods=['POST'])
@login_required
def search_friends():
    query = request.form.get('username')
    if not query:
        return ''
        
    # Find users matching query, excluding self
    # Also ideally indicate if already friends/pending
    users = User.query.filter(User.username.ilike(f'%{query}%'), User.id != current_user.id).limit(5).all()
    
    results = []
    for u in users:
        # Check status
        friendship = Friendship.query.filter(
            or_(
                (Friendship.user_id == current_user.id) & (Friendship.friend_id == u.id),
                (Friendship.user_id == u.id) & (Friendship.friend_id == current_user.id)
            )
        ).first()
        
        status = 'none'
        if friendship:
            status = friendship.status
            if status == 'pending':
                status = 'sent' if friendship.user_id == current_user.id else 'received'
                
        results.append({'user': u, 'status': status})
        
    return render_template('partials/friend_search_results.html', results=results)

# --- PROJECTS ---

@app.route('/projects')
@login_required
def projects_list():
    # Projects I am a member of (includes owner)
    member_projects = Project.query.join(ProjectMember).filter(ProjectMember.user_id == current_user.id).all()
    # Find invites
    pending_invites = ProjectInvite.query.filter_by(recipient_id=current_user.id, status='pending').all()
    return render_template('projects.html', projects=member_projects, pending_invites=pending_invites)

@app.route('/projects/create', methods=['POST'])
@login_required
def create_project():
    name = request.form.get('name')
    description = request.form.get('description')
    if not name:
        return redirect(url_for('projects_list'))
    
    project = Project(name=name, description=description, owner_id=current_user.id)
    db.session.add(project)
    db.session.commit()
    
    # Add owner as member
    member = ProjectMember(project_id=project.id, user_id=current_user.id, role='owner')
    db.session.add(member)
    log_project_action(project.id, "Created the project")
    db.session.commit()
    
    return redirect(url_for('project_detail', project_id=project.id))

@app.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    # Check if user is a member
    member = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
    if not member:
        abort(403)
    
    # Get all project members for the invite modal/form
    members = ProjectMember.query.filter_by(project_id=project_id).all()
    member_ids = [m.user_id for m in members]
    
    return render_template('project_detail.html', project=project, member_ids=member_ids)

@app.route('/projects/<int:project_id>/sections', methods=['POST'])
@login_required
def add_project_section(project_id):
    project = Project.query.get_or_404(project_id)
    member = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
    if not member:
        abort(403)
    
    name = request.form.get('name')
    if name:
        order = len(project.sections)
        section = ProjectSection(project_id=project_id, name=name, order=order)
        db.session.add(section)
        log_project_action(project_id, f"Added section: {name}")
        db.session.commit()
    
    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/projects/sections/<int:section_id>/tasks', methods=['POST'])
@login_required
def add_project_task(section_id):
    section = ProjectSection.query.get_or_404(section_id)
    project = section.project
    member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
    if not member:
        abort(403)
    
    title = request.form.get('title')
    description = request.form.get('description')
    priority = request.form.get('priority', type=int, default=1)
    due_date_str = request.form.get('due_date')
    
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass

    if title:
        task = Task(title=title, description=description, section_id=section_id, user_id=current_user.id, priority=priority, due_date=due_date)
        db.session.add(task)
        log_project_action(project.id, f"Added task: {title}")
        db.session.commit()
    
    return redirect(url_for('project_detail', project_id=project.id))

@app.route('/projects/sections/<int:section_id>/edit', methods=['POST'])
@login_required
def edit_project_section(section_id):
    section = ProjectSection.query.get_or_404(section_id)
    project = section.project
    member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
    if not member:
        abort(403)
    
    name = request.form.get('name')
    if name:
        old_name = section.name
        section.name = name
        log_project_action(project.id, f"Renamed section '{old_name}' to '{name}'")
        db.session.commit()
        return "", 204
    
    return redirect(url_for('project_detail', project_id=project.id))

@app.route('/projects/sections/<int:section_id>/delete', methods=['POST'])
@login_required
def delete_project_section(section_id):
    section = ProjectSection.query.get_or_404(section_id)
    project = section.project
    member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
    if not member or project.owner_id != current_user.id:
        abort(403)
    
    # Move tasks to "General" or just delete?
    # Based on cascade="all, delete-orphan" in models.py, tasks will be deleted.
    # We should probably warn the user or just do it.
    name = section.name
    db.session.delete(section)
    log_project_action(project.id, f"Deleted section: {name}")
    db.session.commit()
    
    return redirect(url_for('project_detail', project_id=project.id))

@app.route('/projects/tasks/<int:task_id>/move', methods=['POST'])
@login_required
def move_project_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not task.section_id:
        abort(400)
    
    project = task.section.project
    member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
    if not member:
        abort(403)
    
    new_section_id = request.form.get('section_id', type=int)
    if new_section_id:
        new_section = ProjectSection.query.get_or_404(new_section_id)
        if new_section.project_id != project.id:
            abort(400)
        
        old_section_name = task.section.name
        task.section_id = new_section_id
        log_project_action(project.id, f"Moved task '{task.title}' from {old_section_name} to {new_section.name}")
        db.session.commit()
    
    return "", 204

@app.route('/projects/<int:project_id>/invite', methods=['POST'])
@login_required
def invite_to_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.owner_id != current_user.id:
        return jsonify({'error': 'Only the owner can invite others'}), 403
    
    # Check member limit (up to 5 OTHER users = 6 total)
    if ProjectMember.query.filter_by(project_id=project_id).count() >= 6:
        return jsonify({'error': 'Member limit reached (max 6 total)'}), 400
    
    username = request.form.get('username')
    target_user = User.query.filter_by(username=username).first()
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if already a member
    existing_member = ProjectMember.query.filter_by(project_id=project_id, user_id=target_user.id).first()
    if existing_member:
        return jsonify({'error': 'User is already a member'}), 400
        
    # Check if already invited
    existing_invite = ProjectInvite.query.filter_by(project_id=project_id, recipient_id=target_user.id, status='pending').first()
    if existing_invite:
        return jsonify({'error': 'Invite already sent'}), 400
    
    invite = ProjectInvite(project_id=project_id, sender_id=current_user.id, recipient_id=target_user.id)
    db.session.add(invite)
    
    # Create notification
    msg = f"{get_username_html(current_user)} invited you to project: <strong>{project.name}</strong>"
    create_notification(target_user.id, msg, type='project_invite', project_id=project.id)
    
    log_project_action(project_id, f"Invited {target_user.username}")
    db.session.commit()
    return jsonify({'message': 'Invite sent!'}), 200

@app.route('/projects/invite/respond/<int:invite_id>/<action>', methods=['POST'])
@login_required
def respond_project_invite(invite_id, action):
    invite = ProjectInvite.query.filter_by(id=invite_id, recipient_id=current_user.id, status='pending').first_or_404()
    
    if action == 'accept':
        # Check limit again
        if ProjectMember.query.filter_by(project_id=invite.project_id).count() >= 6:
            invite.status = 'declined'
            db.session.commit()
            return "Project is full", 400
            
        invite.status = 'accepted'
        member = ProjectMember(project_id=invite.project_id, user_id=current_user.id)
        db.session.add(member)
        
        # Notify sender
        msg = f"{get_username_html(current_user)} joined your project: <strong>{invite.project.name}</strong>"
        create_notification(invite.sender_id, msg, type='success', project_id=invite.project_id)
        log_project_action(invite.project_id, "Joined the project")
    else:
        invite.status = 'declined'
        
    db.session.commit()
    return redirect(url_for('projects_list'))

@app.route('/projects/<int:project_id>/kick/<int:user_id>', methods=['POST'])
@login_required
def kick_project_member(project_id, user_id):
    project = Project.query.get_or_404(project_id)
    if project.owner_id != current_user.id:
        abort(403)
    if user_id == project.owner_id:
        return "Cannot kick owner", 400
    member = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first_or_404()
    username = member.user.username
    db.session.delete(member)
    log_project_action(project_id, f"Kicked member: {username}")
    db.session.commit()
    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/friends')
@login_required
def friends_list():
    # Fetch friends
    friendships = Friendship.query.filter(
        or_(
            (Friendship.user_id == current_user.id),
            (Friendship.friend_id == current_user.id)
        ),
        Friendship.status == 'accepted'
    ).all()
    
    friend_ids = []
    for f in friendships:
        if f.user_id == current_user.id:
            friend_ids.append(f.friend_id)
        else:
            friend_ids.append(f.user_id)
            
    friends = User.query.filter(User.id.in_(friend_ids)).all()
    
    # Active Sync Status Map
    active_rooms = StudyRoom.query.filter(
        StudyRoom.status == 'active',
        or_(StudyRoom.host_id.in_(friend_ids), StudyRoom.guest_id.in_(friend_ids))
    ).all()
    
    sync_map = {}
    for room in active_rooms:
        if room.host_id in friend_ids:
            sync_map[room.host_id] = True
        if room.guest_id and room.guest_id in friend_ids:
            sync_map[room.guest_id] = True
    
    # Fetch Pending Requests (Received)
    pending_friendships = Friendship.query.filter_by(friend_id=current_user.id, status='pending').all()
    pending_ids = [f.user_id for f in pending_friendships]
    pending_requests = User.query.filter(User.id.in_(pending_ids)).all()
    
    suggested_users = []
    if not friends and not pending_requests:
        # Find random users who are not me and not already pending
        # Exclude existing requests (pending)
        all_related = Friendship.query.filter(
            or_(Friendship.user_id == current_user.id, Friendship.friend_id == current_user.id)
        ).all()
        exclude_ids = {current_user.id}
        for f in all_related:
            exclude_ids.add(f.user_id)
            exclude_ids.add(f.friend_id)
            
        suggested_users = User.query.filter(~User.id.in_(exclude_ids))\
            .order_by(func.random())\
            .limit(3).all()
    
    # Calculate statuses for display
    friends_data = []
    now = datetime.utcnow()
    
    for friend in friends:
        is_online = (now - friend.last_seen).total_seconds() < 300 # 5 minutes threshold
        is_syncing = sync_map.get(friend.id, False)
        
        status_msg = "Offline"
        if is_online:
            status_msg = "Online"
            
        timer_info = None
        if friend.current_focus_end and friend.current_focus_end > now:
            remaining = (friend.current_focus_end - now).total_seconds()
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            timer_info = {
                'mode': friend.current_focus_mode,
                'minutes': minutes,
                'seconds': seconds,
                'task': None
            }
            if friend.current_task_id:
                task = Task.query.get(friend.current_task_id)
                if task:
                    timer_info['task'] = task.title
        
        friends_data.append({
            'user': friend,
            'is_online': is_online,
            'is_syncing': is_syncing,
            'status_msg': status_msg,
            'timer': timer_info
        })
        
    return render_template('friends.html', friends=friends_data, suggested_users=suggested_users, pending_requests=pending_requests)

@app.route('/study/sync/request/<int:user_id>', methods=['POST'])
@login_required
def sync_request(user_id):
    target_user = User.query.get_or_404(user_id)
    
    focus_duration = request.form.get('focus_duration', type=int, default=25)
    break_duration = request.form.get('break_duration', type=int, default=5)
    sessions_count = request.form.get('sessions_count', type=int, default=1)
    
    # Create Room (Pending Sync)
    room = StudyRoom(
        host_id=current_user.id, 
        guest_id=target_user.id, 
        status='pending_sync',
        focus_duration=focus_duration,
        break_duration=break_duration,
        sessions_count=sessions_count
    )
    db.session.add(room)
    db.session.commit()
    
    # Notify Friend with Actionable Request
    accept_url = url_for('sync_accept', room_id=room.id)
    reject_url = url_for('sync_reject', room_id=room.id)
    
    user_html = get_username_html(current_user)
    msg = f"""
    {user_html} wants to sync study!<br>
    <span class='text-xs'>Focus: {focus_duration}m | Break: {break_duration}m | Sessions: {sessions_count}</span><br>
    <div class='mt-2 flex gap-2'>
        <button hx-post='{accept_url}' class='bg-green-500 text-white px-3 py-1 rounded text-xs'>Accept</button>
        <button hx-post='{reject_url}' class='bg-red-500 text-white px-3 py-1 rounded text-xs'>Decline</button>
    </div>
    """
    
    create_notification(target_user.id, msg, type='info') # Use info type but html content
    
    return '', 204 # No content, managed via modal/htmx

@app.route('/study/sync/accept/<int:room_id>', methods=['POST'])
@login_required
def sync_accept(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if room.guest_id != current_user.id:
        abort(403)
        
    # Check if already in active room? (Skipped for brevity, assume yes)
    
    room.status = 'active'
    db.session.commit()
    
    # Notify Host
    join_url = url_for('study_room', room_id=room.id)
    create_notification(
        room.host_id,
        f"{get_username_html(current_user)} accepted your sync request! <a href='{join_url}' class='underline font-bold'>Join Now</a>",
        type='success'
    )
    
    # Redirect Guest (Current User) to Room
    # HTMX can handle redirect via HX-Redirect header
    response = jsonify({'status': 'success'})
    response.headers['HX-Redirect'] = join_url
    return response

@app.route('/study/sync/reject/<int:room_id>', methods=['POST'])
@login_required
def sync_reject(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if room.guest_id != current_user.id:
        abort(403)
        
    db.session.delete(room)
    db.session.commit()
    
    create_notification(room.host_id, f"{current_user.username} declined your sync request.", type='warning')
    return '', 200

@app.context_processor
def inject_active_sync():
    if not current_user.is_authenticated:
        return {}
    # Check if user is in an active study room
    active_room = StudyRoom.query.filter(
        ((StudyRoom.host_id == current_user.id) | (StudyRoom.guest_id == current_user.id)),
        StudyRoom.status == 'active'
    ).first()
    return {
        'active_sync_room': active_room,
        'amoled_unlocked': current_user.total_focus_hours >= 10
    }

if __name__ == '__main__':    app.run(debug=True)
