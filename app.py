import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, abort
from flask_login import LoginManager, login_required, current_user
from flask_migrate import Migrate
from sqlalchemy import func
from dotenv import load_dotenv
from models import db, User, Task, Subtask, FocusSession, Tag
from auth import auth

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_change_in_prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///db.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

    # Order by status (done at bottom) then by date
    tasks = query.order_by(Task.status == 'done', Task.created_at.desc()).all()
    all_tags = Tag.query.all()

    if request.headers.get('HX-Request'):
        return render_template('partials/task_list.html', tasks=tasks)

    return render_template('index.html', tasks=tasks, all_tags=all_tags)

@app.route('/timer')
@login_required
def timer():
    tasks = Task.query.filter_by(user_id=current_user.id).filter(Task.status != 'done').order_by(Task.created_at.desc()).all()
    return render_template('timer.html', tasks=tasks)

@app.route('/leaderboard')
@login_required
def leaderboard():
    from sqlalchemy import func
    results = db.session.query(
        User.username,
        func.sum(FocusSession.minutes).label('total_minutes')
    ).join(FocusSession).group_by(User.id).order_by(func.sum(FocusSession.minutes).desc()).limit(10).all()
    
    return render_template('leaderboard.html', leaders=results)

@app.route('/api/log_session', methods=['POST'])
@login_required
def log_session():
    data = request.json
    minutes = data.get('minutes')
    task_id = data.get('task_id')
    
    if minutes:
        session = FocusSession(minutes=minutes, user_id=current_user.id, task_id=task_id)
        db.session.add(session)
        
        if task_id:
            task = Task.query.get(task_id)
            if task and task.user_id == current_user.id:
                task.completed_pomodoros += 1
                if task.completed_pomodoros >= task.estimated_pomodoros:
                    task.status = 'done'
        
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
        return render_template('partials/task_item.html', task=new_task)
    return '', 400

@app.route('/delete_task/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)
    db.session.delete(task)
    db.session.commit()
    return ''

@app.route('/toggle_task/<int:task_id>', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)
    
    if task.status == 'done':
        task.status = 'todo'
    else:
        task.status = 'done'
    
    db.session.commit()
    
    # After toggle, re-fetch and return the full list to maintain order
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.status == 'done', Task.created_at.desc()).all()
    return render_template('partials/task_list.html', tasks=tasks)

@app.route('/task/<int:task_id>/edit', methods=['GET'])
@login_required
def get_edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)
    return render_template('partials/task_edit.html', task=task)

@app.route('/task/<int:task_id>', methods=['PUT', 'POST'])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
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
    return render_template('partials/task_item.html', task=task)

@app.route('/task/<int:task_id>/item', methods=['GET'])
@login_required
def get_task_item(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)
    return render_template('partials/task_item.html', task=task)

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
    return render_template('stats.html', total_minutes=total_minutes, total_sessions=total_sessions)

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
        
    db.session.commit()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True)
