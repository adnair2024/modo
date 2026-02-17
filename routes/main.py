from flask import render_template, request, jsonify, abort, redirect, url_for, make_response
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from . import main_bp
from models import db, Task, Subtask, Tag, Event, Habit, HabitCompletion, EventCompletion, FocusSession, User, Achievement, UserAchievement
from utils import expand_events, EventOccurrence, log_project_action, check_task_access
from extensions import cache

from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/admin')
@login_required
@admin_required
def admin():
    users = User.query.all()
    now = datetime.now(timezone.utc)
    online_count = User.query.filter(User.last_seen >= now - timedelta(minutes=5)).count()
    total_users = len(users)
    total_focus_minutes = db.session.query(func.sum(FocusSession.minutes)).scalar() or 0
    total_tasks_completed = Task.query.filter_by(status='done').count()
    new_users_7d = User.query.filter(User.date_joined >= now - timedelta(days=7)).count()
    
    return render_template('admin.html', 
                           users=users, 
                           online_count=online_count, 
                           total_users=total_users,
                           total_focus_hours=round(total_focus_minutes / 60, 1),
                           total_tasks_completed=total_tasks_completed,
                           new_users_7d=new_users_7d,
                           now=now)

@main_bp.route('/admin/user/<int:user_id>/ban', methods=['POST'])
@login_required
@admin_required
def admin_ban_user(user_id):
    user = db.session.get(User, user_id)
    if not user: abort(404)
    if user.username == 'lost':
        return "Cannot ban the owner", 400
    user.is_banned = not user.is_banned
    db.session.commit()
    return redirect(url_for('main.admin'))

@main_bp.route('/admin/user/<int:user_id>/logout', methods=['POST'])
@login_required
@admin_required
def admin_logout_user(user_id):
    user = db.session.get(User, user_id)
    if not user: abort(404)
    user.must_logout = True
    db.session.commit()
    return redirect(url_for('main.admin'))

@main_bp.route('/admin/user/<int:user_id>/toggle_admin', methods=['POST'])
@login_required
@admin_required
def admin_toggle_role(user_id):
    user = db.session.get(User, user_id)
    if not user: abort(404)
    if user.username == 'lost' and current_user.username != 'lost':
        return "Cannot demote the owner", 403
    if user.id == current_user.id and user.username == 'lost':
         return "Owner cannot demote themselves", 400
    user.is_admin = not user.is_admin
    db.session.commit()
    return redirect(url_for('main.admin'))

@main_bp.route('/admin/user/<int:user_id>/rename', methods=['POST'])
@login_required
@admin_required
def admin_rename_user(user_id):
    user = db.session.get(User, user_id)
    if not user: abort(404)
    new_username = request.form.get('username')
    if new_username:
        user.username = new_username
        db.session.commit()
    return redirect(url_for('main.admin'))

@main_bp.route('/admin/user/<int:user_id>/edit_timer', methods=['POST'])
@login_required
@admin_required
def admin_edit_timer(user_id):
    user = db.session.get(User, user_id)
    if not user: abort(404)
    focus = request.form.get('focus_duration', type=int)
    break_d = request.form.get('break_duration', type=int)
    if focus: user.focus_duration = focus
    if break_d: user.break_duration = break_d
    db.session.commit()
    return redirect(url_for('main.admin'))

@main_bp.route('/badges')
@login_required
def badges():
    all_achievements = Achievement.query.order_by(Achievement.criteria_value.asc()).all()
    earned_map = {ua.achievement_id: ua.earned_at for ua in current_user.achievements}
    return render_template('badges.html', achievements=all_achievements, earned_map=earned_map)

@main_bp.route('/')
@login_required
def index():
    query = Task.query.filter_by(user_id=current_user.id)
    q = request.args.get('q')
    if q: query = query.filter(Task.title.ilike(f'%{q}%'))
    date_start_str = request.args.get('date_start')
    date_end_str = request.args.get('date_end')
    if date_start_str:
        try:
            date_start = datetime.strptime(date_start_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(Task.due_date >= date_start)
        except ValueError: pass
    if date_end_str:
        try:
            date_end = datetime.strptime(date_end_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(Task.due_date <= date_end)
        except ValueError: pass
    sort_by = request.args.get('sort', 'created_at')
    if sort_by == 'priority': query = query.order_by(Task.priority.desc(), Task.created_at.desc())
    elif sort_by == 'due_date': query = query.order_by(Task.due_date.asc(), Task.created_at.desc())
    else: query = query.order_by(Task.created_at.desc())
    tasks = query.all()
    today = datetime.now(timezone.utc).date()
    
    # Optimized Habits Query
    habits_list = Habit.query.filter_by(user_id=current_user.id).all()
    habit_ids = [h.id for h in habits_list]
    completions = HabitCompletion.query.filter(HabitCompletion.habit_id.in_(habit_ids), HabitCompletion.date == today).all() if habit_ids else []
    comp_set = {c.habit_id for c in completions}
    
    habit_items = []
    for h in habits_list:
        habit_items.append({'habit': h, 'completed': h.id in comp_set})

    # Today's Events
    user_events = Event.query.filter_by(user_id=current_user.id).all()
    today_events = expand_events(user_events, today, today)
    today_events.sort(key=lambda x: x.start_time)

    # Stats Summary - Using optimized property
    total_focus = db.session.query(func.sum(FocusSession.minutes)).filter_by(user_id=current_user.id).scalar() or 0
    if request.headers.get('HX-Request'):
        return render_template('partials/task_list.html', tasks=tasks, now=datetime.now(timezone.utc))
    return render_template('index.html', tasks=tasks, habit_items=habit_items, today_events=today_events, total_focus=total_focus, now=datetime.now(timezone.utc))

@main_bp.route('/timer')
@login_required
def timer():
    tasks = [t for t in current_user.all_accessible_tasks if t.status != 'done']
    return render_template('timer.html', tasks=tasks)

@main_bp.route('/add_task', methods=['POST'])
@login_required
def add_task():
    title = request.form.get('title')
    description = request.form.get('description')
    due_date_str = request.form.get('due_date')
    est_pomodoros = request.form.get('estimated_pomodoros', type=int, default=1)
    priority = request.form.get('priority', type=int, default=1)
    tags_str = request.form.get('tags')
    if title:
        title = title[:200]
        if description: description = description[:2000]
        due_date = None
        if due_date_str:
            try: due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M').replace(tzinfo=timezone.utc)
            except ValueError: pass
        new_task = Task(title=title, description=description, due_date=due_date, estimated_pomodoros=est_pomodoros, priority=priority, user_id=current_user.id)
        if tags_str:
            tag_names = [t.strip() for t in tags_str.split(',') if t.strip()]
            for name in tag_names:
                tag = Tag.query.filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name); db.session.add(tag)
                new_task.tags.append(tag)
        db.session.add(new_task); db.session.commit()
        response = make_response(render_template('partials/task_item.html', task=new_task, now=datetime.now(timezone.utc)))
        response.headers['HX-Trigger'] = 'tasksChanged'
        return response
    return '', 400

@main_bp.route('/delete_task/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if not task: abort(404)
    if not check_task_access(task): abort(403)
    db.session.delete(task); db.session.commit()
    response = make_response(''); response.headers['HX-Trigger'] = 'tasksChanged'
    return response

@main_bp.route('/toggle_task/<int:task_id>', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = db.session.get(Task, task_id)
    if not task: abort(404)
    if not check_task_access(task): abort(403)
    task.status = 'todo' if task.status == 'done' else 'done'
    db.session.commit()
    response = make_response(render_template('partials/task_item.html', task=task, now=datetime.now(timezone.utc)))
    response.headers['HX-Trigger'] = 'tasksChanged'
    return response

@main_bp.route('/task/<int:task_id>/edit', methods=['GET'])
@login_required
def get_edit_task(task_id):
    task = db.session.get(Task, task_id)
    if not task: abort(404)
    if not check_task_access(task): abort(403)
    return render_template('partials/task_edit.html', task=task)

@main_bp.route('/task/<int:task_id>', methods=['PUT', 'POST'])
@login_required
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task: abort(404)
    if not check_task_access(task): abort(403)
    title = request.form.get('title')
    description = request.form.get('description')
    due_date_str = request.form.get('due_date')
    est_pomodoros = request.form.get('estimated_pomodoros', type=int)
    priority = request.form.get('priority', type=int)
    tags_str = request.form.get('tags')
    if title:
        task.title = title[:200]
        task.description = description[:2000] if description else None
        if est_pomodoros: task.estimated_pomodoros = est_pomodoros
        if priority: task.priority = priority
        if due_date_str:
            try: task.due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M').replace(tzinfo=timezone.utc)
            except ValueError: pass
        else: task.due_date = None
        if tags_str is not None:
            task.tags = []
            tag_names = [t.strip() for t in tags_str.split(',') if t.strip()]
            for name in tag_names:
                tag = Tag.query.filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name); db.session.add(tag)
                task.tags.append(tag)
    db.session.commit()
    return render_template('partials/task_item.html', task=task, now=datetime.now(timezone.utc))

@main_bp.route('/task/<int:task_id>/subtask', methods=['POST'])
@login_required
def add_subtask(task_id):
    task = db.session.get(Task, task_id)
    if not task: abort(404)
    if not check_task_access(task): abort(403)
    title = request.form.get('title')
    if title:
        new_subtask = Subtask(title=title[:200], task_id=task.id)
        db.session.add(new_subtask); db.session.commit()
    return render_template('partials/task_item.html', task=task, now=datetime.now(timezone.utc))

@main_bp.route('/subtask/<int:subtask_id>/toggle', methods=['POST'])
@login_required
def toggle_subtask(subtask_id):
    subtask = db.session.get(Subtask, subtask_id)
    if not subtask: abort(404)
    if not check_task_access(subtask.parent): abort(403)
    subtask.is_completed = not subtask.is_completed
    db.session.commit()
    return render_template('partials/task_item.html', task=subtask.parent, now=datetime.now(timezone.utc))

@main_bp.route('/subtask/<int:subtask_id>', methods=['DELETE'])
@login_required
def delete_subtask(subtask_id):
    subtask = db.session.get(Subtask, subtask_id)
    if not subtask: abort(404)
    task = subtask.parent
    if not check_task_access(task): abort(403)
    db.session.delete(subtask); db.session.commit()
    return render_template('partials/task_item.html', task=task, now=datetime.now(timezone.utc))

@main_bp.route('/subtask/<int:subtask_id>/edit', methods=['GET'])
@login_required
def get_edit_subtask(subtask_id):
    subtask = db.session.get(Subtask, subtask_id)
    if not subtask: abort(404)
    if not check_task_access(subtask.parent): abort(403)
    return render_template('partials/subtask_edit.html', subtask=subtask)

@main_bp.route('/subtask/<int:subtask_id>', methods=['PUT', 'POST'])
@login_required
def update_subtask(subtask_id):
    subtask = db.session.get(Subtask, subtask_id)
    if not subtask: abort(404)
    if not check_task_access(subtask.parent): abort(403)
    title = request.form.get('title')
    if title: subtask.title = title[:200]
    db.session.commit()
    return render_template('partials/task_item.html', task=subtask.parent, now=datetime.now(timezone.utc))

@main_bp.route('/task/<int:task_id>/item', methods=['GET'])
@login_required
def get_task_item(task_id):
    task = db.session.get(Task, task_id)
    if not task: abort(404)
    if not check_task_access(task): abort(403)
    return render_template('partials/task_item.html', task=task, now=datetime.now(timezone.utc))

@main_bp.route('/leaderboard')
@login_required
@cache.cached(timeout=60, query_string=True)
def leaderboard():
    filter_type = request.args.get('filter', 'all'); category = request.args.get('category', 'focus')
    now = datetime.now(timezone.utc)
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
    if category == 'habits':
        query = db.session.query(User, func.count(HabitCompletion.id).label('score')).select_from(User).join(Habit, User.id == Habit.user_id).join(HabitCompletion, Habit.id == HabitCompletion.habit_id).group_by(User.id).order_by(func.count(HabitCompletion.id).desc())
        if filter_type == 'weekly': query = query.filter(HabitCompletion.date >= start_of_week.date(), HabitCompletion.date <= end_of_week.date())
    elif category == 'sync':
        query = db.session.query(User, func.sum(FocusSession.minutes).label('score')).join(FocusSession, User.id == FocusSession.user_id).filter(FocusSession.partner_id.isnot(None)).group_by(User.id).order_by(func.sum(FocusSession.minutes).desc())
        if filter_type == 'weekly': query = query.filter(FocusSession.date >= start_of_week, FocusSession.date <= end_of_week)
    else:
        query = db.session.query(User, func.sum(FocusSession.minutes).label('score')).join(FocusSession, User.id == FocusSession.user_id).group_by(User.id).order_by(func.sum(FocusSession.minutes).desc())
        if filter_type == 'weekly': query = query.filter(FocusSession.date >= start_of_week, FocusSession.date <= end_of_week)
    results = query.limit(10).all()
    return render_template('leaderboard.html', leaders=results, filter_type=filter_type, category=category)

@main_bp.route('/stats')
@login_required
def personal_stats():
    now = datetime.now(timezone.utc)
    
    # Core Metrics
    total_minutes = db.session.query(func.sum(FocusSession.minutes)).filter_by(user_id=current_user.id).scalar() or 0
    total_sessions = FocusSession.query.filter_by(user_id=current_user.id).count()
    
    # Weekly Logic
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    weekly_minutes = db.session.query(func.sum(FocusSession.minutes)).filter(
        FocusSession.user_id == current_user.id,
        FocusSession.date >= start_of_week
    ).scalar() or 0
    
    # Sync Logic
    sync_sessions = FocusSession.query.filter(
        FocusSession.user_id == current_user.id,
        FocusSession.partner_id.isnot(None)
    ).all()
    sync_minutes = sum(s.minutes for s in sync_sessions)
    sync_sessions_count = len(sync_sessions)
    
    # Top Partner
    top_partner_data = db.session.query(
        FocusSession.partner_id, 
        func.count(FocusSession.id)
    ).filter(
        FocusSession.user_id == current_user.id,
        FocusSession.partner_id.isnot(None)
    ).group_by(FocusSession.partner_id).order_by(func.count(FocusSession.id).desc()).first()
    
    top_partner = None
    if top_partner_data:
        top_partner = db.session.get(User, top_partner_data[0])

    # Heatmap Data (Current Year)
    year_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    sessions_year = FocusSession.query.filter(
        FocusSession.user_id == current_user.id, 
        FocusSession.date >= year_start
    ).all()
    
    heatmap_data = {}
    for s in sessions_year:
        d_str = s.date.strftime('%Y-%m-%d')
        heatmap_data[d_str] = heatmap_data.get(d_str, 0) + s.minutes
        
    habit_completions = HabitCompletion.query.join(Habit).filter(
        Habit.user_id == current_user.id, 
        HabitCompletion.date >= year_start.date()
    ).all()
    
    habit_heatmap_data = {}
    for c in habit_completions:
        d_str = c.date.strftime('%Y-%m-%d')
        habit_heatmap_data[d_str] = habit_heatmap_data.get(d_str, 0) + 1
        
    return render_template('stats.html', 
                           total_minutes=total_minutes,
                           total_sessions=total_sessions,
                           weekly_minutes=weekly_minutes,
                           sync_minutes=sync_minutes,
                           sync_sessions_count=sync_sessions_count,
                           top_partner=top_partner,
                           heatmap_data=heatmap_data, 
                           habit_heatmap_data=habit_heatmap_data,
                           current_year=now.year)

@main_bp.route('/habits')
@login_required
def habits():
    user_habits = Habit.query.filter_by(user_id=current_user.id).order_by(Habit.created_at.desc()).all()
    today = datetime.now(timezone.utc).date(); dates = []
    for i in range(6, -1, -1): dates.append(today - timedelta(days=i))
    start_date = dates[0]; end_date = dates[-1]
    habit_ids = [h.id for h in user_habits]
    completions = HabitCompletion.query.filter(HabitCompletion.habit_id.in_(habit_ids), HabitCompletion.date >= start_date, HabitCompletion.date <= end_date).all()
    comp_map = {(c.habit_id, c.date): True for c in completions}
    habits_data = []
    for h in user_habits:
        status_list = []
        for d in dates:
            status_list.append({'date': d.strftime('%Y-%m-%d'), 'is_done': (h.id, d) in comp_map, 'is_today': (d == today), 'day_name': d.strftime('%a')})
        habits_data.append({'habit': h, 'days': status_list})
    year_start = today.replace(month=1, day=1)
    year_completions = HabitCompletion.query.join(Habit).filter(Habit.user_id == current_user.id, HabitCompletion.date >= year_start).all()
    heatmap_data = {}; 
    for c in year_completions:
        d_str = c.date.strftime('%Y-%m-%d')
        heatmap_data[d_str] = heatmap_data.get(d_str, 0) + 1
    if request.headers.get('HX-Request') and request.headers.get('HX-Target') == 'habit-list-container':
        return render_template('partials/habit_list.html', habits=habits_data, dates=dates)
    return render_template('habits.html', habits=habits_data, dates=dates, heatmap_data=heatmap_data, current_year=today.year)

@main_bp.route('/habits/add', methods=['POST'])
@login_required
def add_habit():
    title = request.form.get('title')
    if title:
        h = Habit(title=title[:200], user_id=current_user.id)
        db.session.add(h); db.session.commit()
    return habits() if request.headers.get('HX-Request') else redirect(url_for('main.habits'))

@main_bp.route('/habits/<int:habit_id>/delete', methods=['POST'])
@login_required
def delete_habit(habit_id):
    habit = db.session.get(Habit, habit_id)
    if habit and habit.user_id == current_user.id:
        db.session.delete(habit); db.session.commit()
    return habits() if request.headers.get('HX-Request') else redirect(url_for('main.habits'))

@main_bp.route('/habits/<int:habit_id>/toggle', methods=['POST'])
@login_required
def toggle_habit(habit_id):
    habit = db.session.get(Habit, habit_id)
    if not habit or habit.user_id != current_user.id: abort(403)
    date_str = request.args.get('date')
    try: target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now(timezone.utc).date()
    except ValueError: target_date = datetime.now(timezone.utc).date()
    comp = HabitCompletion.query.filter_by(habit_id=habit_id, date=target_date).first()
    if comp: db.session.delete(comp)
    else: db.session.add(HabitCompletion(habit_id=habit_id, date=target_date))
    db.session.commit()
    if request.headers.get('HX-Request'):
        target = request.headers.get('HX-Target', '')
        # Handle index.html toggle
        if target.startswith('habit-home-'):
             return render_template('partials/habit_item_home.html', habit=habit, completed=comp is None)
        
        # Handle habits.html cell toggle
        # target might be the ID we just added
        if 'habit-cell-' in target:
             return render_template('partials/habit_cell.html', habit=habit, day={'date': target_date.strftime('%Y-%m-%d'), 'is_done': comp is None})
        
        # Fallback for habits page if triggered from within the list container
        if target == 'habit-list-container':
            return habits()
            
        # Default to cell if we're not sure, to avoid full page swap
        return render_template('partials/habit_cell.html', habit=habit, day={'date': target_date.strftime('%Y-%m-%d'), 'is_done': comp is None})
    return redirect(url_for('main.index'))

@main_bp.route('/toggle_event/<int:event_id>', methods=['POST'])
@login_required
def toggle_event(event_id):
    event = db.session.get(Event, event_id)
    if not event or event.user_id != current_user.id: abort(403)
    date_str = request.args.get('date')
    if not date_str:
        event.is_completed = not event.is_completed; db.session.commit()
        return render_template('partials/event_item_small.html', event=EventOccurrence(event, event.start_time, event.is_completed))
    try: target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError: return '', 400
    comp = EventCompletion.query.filter_by(event_id=event.id, date=target_date).first()
    is_done = False
    if comp: db.session.delete(comp)
    else:
        db.session.add(EventCompletion(event_id=event.id, user_id=current_user.id, date=target_date))
        is_done = True
    db.session.commit()
    return render_template('partials/event_item_small.html', event=EventOccurrence(event, datetime.combine(target_date, event.start_time.time()).replace(tzinfo=timezone.utc), is_done))
