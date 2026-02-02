from flask import render_template, request, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from . import api_bp
from models import db, FocusSession, StudyRoom, Task, Notification
from utils import create_notification, check_event_notifications, check_task_access
from services.achievement_service import check_achievements

@api_bp.route('/log_session', methods=['POST'])
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

        current_user.last_focus_end = datetime.utcnow()
        db.session.commit()
        
        # Check Achievements
        check_achievements(current_user)
        
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 400

@api_bp.route('/next_priority_task', methods=['GET'])
@login_required
def get_next_priority_task():
    task = (Task.query.filter_by(user_id=current_user.id, status='todo')
        .order_by(Task.priority.desc(), Task.created_at.asc()).first())
    if task:
        return jsonify({'id': task.id, 'title': task.title})
    return jsonify({'id': None})

@api_bp.route('/sync_presence', methods=['POST'])
@login_required
def sync_presence():
    data = request.json
    status = data.get('status')
    mode = data.get('mode') 
    seconds_left = data.get('seconds_left')
    task_id = data.get('task_id')
    
    current_user.last_seen = datetime.utcnow()
    current_user.current_focus_mode = mode
    
    if status == 'running' and seconds_left is not None:
        current_user.current_focus_end = datetime.utcnow() + timedelta(seconds=int(seconds_left))
        if not current_user.current_focus_start: 
             current_user.current_focus_start = datetime.utcnow() 
    else:
        # If transitioning from running to not running
        if current_user.current_focus_end:
            current_user.last_focus_end = datetime.utcnow()
        current_user.current_focus_end = None

    if task_id:
        current_user.current_task_id = int(task_id)
    else:
        current_user.current_task_id = None
        
    db.session.commit()
    return jsonify({'status': 'ok'})

@api_bp.route('/notifications')
@login_required
def get_notifications():
    check_event_notifications(current_user)
    
    notifications = (Notification.query.filter_by(user_id=current_user.id, is_read=False)
        .order_by(Notification.created_at.desc()).all())
        
    if request.headers.get('HX-Request'):
        return render_template('partials/notification_list.html', notifications=notifications)
    
    return jsonify([
        {
            'id': n.id, 
            'message': n.message,
            'type': n.type,
            'created_at': n.created_at.isoformat()
        } for n in notifications
    ])

@api_bp.route('/notifications/mark_read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        abort(403)
    notif.is_read = True
    db.session.commit()
    return ''

@api_bp.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return ''

@api_bp.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    data = request.json
    if 'enable_vim_mode' in data:
        current_user.enable_vim_mode = data['enable_vim_mode']
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

