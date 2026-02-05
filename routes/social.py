from flask import render_template, request, jsonify, abort, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from datetime import datetime
from . import social_bp
from models import db, User, Friendship, FocusSession, StudyRoom, Task
from utils import get_username_html, create_notification

@social_bp.route('/u/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    
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

    total_minutes = db.session.query(func.sum(FocusSession.minutes)).filter_by(user_id=user.id).scalar() or 0
    total_sessions = FocusSession.query.filter_by(user_id=user.id).count()

    recent_sessions = FocusSession.query.filter_by(user_id=user.id).order_by(FocusSession.date.desc()).limit(5).all()
    
    return render_template('profile.html', user=user, status=status, total_minutes=total_minutes, 
                           total_sessions=total_sessions, recent_sessions=recent_sessions, now=datetime.utcnow())

@social_bp.route('/friends')
@login_required
def friends_list():
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
    
    pending_friendships = Friendship.query.filter_by(friend_id=current_user.id, status='pending').all()
    pending_ids = [f.user_id for f in pending_friendships]
    pending_requests = User.query.filter(User.id.in_(pending_ids)).all()
    
    suggested_users = []
    if not friends and not pending_requests:
        all_related = Friendship.query.filter(
            or_(Friendship.user_id == current_user.id, Friendship.friend_id == current_user.id)
        ).all()
        exclude_ids = {current_user.id}
        for f in all_related:
            exclude_ids.add(f.user_id)
            exclude_ids.add(f.friend_id)
            
        suggested_users = (User.query.filter(~User.id.in_(exclude_ids))
            .order_by(func.random())
            .limit(3).all())
    
    friends_data = []
    now = datetime.utcnow()
    
    for friend in friends:
        is_online = (now - friend.last_seen).total_seconds() < 300 
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
                task = db.session.get(Task, friend.current_task_id)
                if task:
                    timer_info['task'] = task.title
        elif is_online:
            # Idling logic
            # Idle since last_focus_end or last_seen (whichever is more relevant)
            # last_focus_end is the start of 'true' idle time
            idle_start = friend.last_focus_end or friend.last_seen
            idle_seconds = (now - idle_start).total_seconds()
            idle_mins = int(idle_seconds // 60)
            timer_info = {
                'mode': 'idle',
                'minutes': idle_mins,
                'task': None
            }
        
        friends_data.append({
            'user': friend,
            'is_online': is_online,
            'is_syncing': is_syncing,
            'status_msg': status_msg,
            'timer': timer_info
        })
        
    return render_template('friends.html', friends=friends_data, suggested_users=suggested_users, pending_requests=pending_requests)

@social_bp.route('/friends/search', methods=['POST'])
@login_required
def search_friends():
    query = request.form.get('username')
    if not query:
        return ''
        
    users = User.query.filter(User.username.ilike(f'%{query}%'), User.id != current_user.id).limit(5).all()
    
    results = []
    for u in users:
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

@social_bp.route('/friend/request/<int:user_id>', methods=['POST'])
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
        
        accept_url = url_for('social.respond_friend_request', user_id=current_user.id, action='accept')
        reject_url = url_for('social.respond_friend_request', user_id=current_user.id, action='reject')
        
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
        
    return redirect(url_for('social.profile', username=target_user.username))

@social_bp.route('/friend/respond/<int:user_id>/<action>', methods=['POST'])
@login_required
def respond_friend_request(user_id, action):
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
        # Check achievements for both users
        from services.achievement_service import check_achievements
        check_achievements(current_user)
        target_user = User.query.get(user_id)
        if target_user:
            check_achievements(target_user)
    elif action == 'reject':
        db.session.delete(friendship)
    elif action == 'remove':
        friendship = Friendship.query.filter(
            or_(
                (Friendship.user_id == current_user.id) & (Friendship.friend_id == user_id),
                (Friendship.user_id == user_id) & (Friendship.friend_id == current_user.id)
            )
        ).first()
        if friendship:
            db.session.delete(friendship)
            
    db.session.commit()
    
    referrer = request.referrer
    if referrer and 'friends' in referrer:
        return redirect(url_for('social.friends_list'))
        
    target_user = User.query.get(user_id)
    return redirect(url_for('social.profile', username=target_user.username))
