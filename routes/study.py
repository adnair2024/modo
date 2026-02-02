from flask import render_template, request, jsonify, abort, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from . import study_bp
from models import db, StudyRoom, User, Task, ChatMessage
from utils import get_username_html, create_notification

@study_bp.route('/room/<int:room_id>/chat', methods=['GET', 'POST'])
@login_required
def study_chat(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if current_user.id not in [room.host_id, room.guest_id]:
        abort(403)
        
    if request.method == 'POST':
        message = request.form.get('message')
        if message:
            msg = ChatMessage(room_id=room.id, user_id=current_user.id, message=message)
            db.session.add(msg)
            db.session.commit()
            
            # If HTMX, return just the new message (or all)
            # Returning all for simplicity in auto-scroll
            messages = ChatMessage.query.filter_by(room_id=room.id).order_by(ChatMessage.timestamp.asc()).all()
            return render_template('partials/chat_messages.html', messages=messages)

    # GET (Polling)
    messages = ChatMessage.query.filter_by(room_id=room.id).order_by(ChatMessage.timestamp.asc()).all()
    return render_template('partials/chat_messages.html', messages=messages)

@study_bp.route('/join/<int:room_id>')
@login_required
def join_study_room(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if room.guest_id != current_user.id:
        abort(403)
        
    if room.status == 'waiting':
        room.status = 'active'
        db.session.commit()
        
    return redirect(url_for('study.study_room', room_id=room.id))

@study_bp.route('/room/<int:room_id>')
@login_required
def study_room(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if current_user.id not in [room.host_id, room.guest_id]:
        abort(403)
        
    other_user_id = room.guest_id if room.host_id == current_user.id else room.host_id
    other_user = User.query.get(other_user_id)
    
    return render_template('study_room.html', room=room, other_user=other_user)

@study_bp.route('/room/<int:room_id>/poll')
@login_required
def study_room_poll(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if request.headers.get('HX-Request'):
        if room.status == 'active':
             return render_template('partials/study_active.html', room=room)
        return ''
    return ''

@study_bp.route('/control', methods=['POST'])
@login_required
def study_control():
    data = request.json
    room_id = data.get('room_id')
    action = data.get('action') 
    
    room = StudyRoom.query.get_or_404(room_id)
    if current_user.id not in [room.host_id, room.guest_id]:
        abort(403)
        
    # Update activity
    room.last_activity = datetime.utcnow()
        
    duration = (room.focus_duration if room.active_mode == 'focus' else room.break_duration) * 60
        
    if action == 'start':
        if not room.active_start_time:
            if room.seconds_remaining is None:
                room.seconds_remaining = duration
                
            room.active_start_time = datetime.utcnow()
            
    elif action == 'pause':
        if room.active_start_time:
            elapsed = (datetime.utcnow() - room.active_start_time).total_seconds()
            current_rem = room.seconds_remaining if room.seconds_remaining is not None else duration
            room.seconds_remaining = max(0, int(current_rem - elapsed))
            room.active_start_time = None
        
    elif action == 'reset':
        room.active_start_time = None
        room.seconds_remaining = None 
        room.active_mode = 'focus'
        
    elif action == 'skip':
        room.active_start_time = None
        room.seconds_remaining = None
        room.active_mode = 'break' if room.active_mode == 'focus' else 'focus'
    
    room.last_activity = datetime.utcnow()
        
    db.session.commit()
    return jsonify({'status': 'ok'})

@study_bp.route('/state/<int:room_id>')
@login_required
def study_state(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if current_user.id not in [room.host_id, room.guest_id]:
        abort(403)
        
    duration = (room.focus_duration if room.active_mode == 'focus' else room.break_duration) * 60
    
    seconds_remaining = duration
    is_running = False
    
    if room.active_start_time:
        elapsed = (datetime.utcnow() - room.active_start_time).total_seconds()
        start_rem = room.seconds_remaining if room.seconds_remaining is not None else duration
        seconds_remaining = max(0, start_rem - elapsed)
        is_running = True
        
        # While running, it's active. Update timestamp implicitly or we rely on 'running' state not timing out?
        # Let's say if running, it is NOT inactive.
    else:
        # Check for inactivity timeout (30 mins)
        last_active = room.last_activity or room.created_at
        if (datetime.utcnow() - last_active).total_seconds() > 1800: # 30 mins * 60
             # Delete room
             from models import ChatMessage
             ChatMessage.query.filter_by(room_id=room.id).delete()
             db.session.delete(room)
             db.session.commit()
             return jsonify({'status': 'finished'})

        if room.seconds_remaining is not None:
            seconds_remaining = room.seconds_remaining
        else:
            seconds_remaining = duration
            
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

@study_bp.route('/leave/<int:room_id>', methods=['POST'])
@login_required
def leave_study_room(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if current_user.id in [room.host_id, room.guest_id]:
        # Explicitly delete messages first to avoid foreign key issues if cascade isn't set at DB level
        from models import ChatMessage
        ChatMessage.query.filter_by(room_id=room.id).delete()
        db.session.delete(room)
        db.session.commit()
    return redirect(url_for('main.index'))

@study_bp.route('/sync/request/<int:user_id>', methods=['POST'])
@login_required
def sync_request(user_id):
    target_user = User.query.get_or_404(user_id)
    
    focus_duration = request.form.get('focus_duration', type=int, default=25)
    break_duration = request.form.get('break_duration', type=int, default=5)
    sessions_count = request.form.get('sessions_count', type=int, default=1)
    
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
    
    accept_url = url_for('study.sync_accept', room_id=room.id)
    reject_url = url_for('study.sync_reject', room_id=room.id)
    
    user_html = get_username_html(current_user)
    msg = f"""
    {user_html} wants to sync study!<br>
    <span class='text-xs'>Focus: {focus_duration}m | Break: {break_duration}m | Sessions: {sessions_count}</span><br>
    <div class='mt-2 flex gap-2'>
        <button hx-post='{accept_url}' class='bg-green-500 text-white px-3 py-1 rounded text-xs'>Accept</button>
        <button hx-post='{reject_url}' class='bg-red-500 text-white px-3 py-1 rounded text-xs'>Decline</button>
    </div>
    """
    
    create_notification(target_user.id, msg, type='info') 
    
    return '', 204

@study_bp.route('/sync/accept/<int:room_id>', methods=['POST'])
@login_required
def sync_accept(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if room.guest_id != current_user.id:
        abort(403)
        
    room.status = 'active'
    db.session.commit()
    
    join_url = url_for('study.study_room', room_id=room.id)
    create_notification(
        room.host_id,
        f"{get_username_html(current_user)} accepted your sync request! <a href='{join_url}' class='underline font-bold'>Join Now</a>",
        type='success'
    )
    
    response = jsonify({'status': 'success'})
    response.headers['HX-Redirect'] = join_url
    return response

@study_bp.route('/sync/reject/<int:room_id>', methods=['POST'])
@login_required
def sync_reject(room_id):
    room = StudyRoom.query.get_or_404(room_id)
    if room.guest_id != current_user.id:
        abort(403)
        
    db.session.delete(room)
    db.session.commit()
    
    create_notification(room.host_id, f"{current_user.username} declined your sync request.", type='warning')
    return '', 200
