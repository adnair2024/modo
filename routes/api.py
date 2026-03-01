from flask import render_template, request, jsonify, abort, session
from flask_login import login_required, current_user
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from . import api_bp
from models import db, FocusSession, StudyRoom, Task, Notification, User
from utils import create_notification, check_event_notifications, check_task_access
from services.achievement_service import check_achievements
from extensions import csrf
import os

@api_bp.route('/trmnl', methods=['GET'])
@csrf.exempt
def trmnl_feed():
    # Authentication check
    auth_header = request.headers.get('Authorization')
    expected_token = os.environ.get('TRMNL_API_KEY')
    
    # Check Bearer token or fallback to query param api_key
    authenticated = False
    if auth_header and auth_header.startswith('Bearer '):
        if auth_header.split(' ')[1] == expected_token:
            authenticated = True
    elif request.args.get('api_key') == expected_token:
        authenticated = True

    if not authenticated:
        return jsonify({'error': 'UNAUTHORIZED'}), 401

    # Fetch tasks for the primary admin (Lord Silver / lost)
    user = User.query.filter_by(is_admin=True).first()
    if not user:
        return jsonify({'error': 'SUBJECT_NOT_FOUND'}), 404

    # Update last poll time
    user.last_trmnl_poll = datetime.now(timezone.utc)
    db.session.commit()

    # Data Extraction: Prioritize Pinned Tasks, then most recent incomplete
    tasks = (Task.query.filter_by(user_id=user.id)
             .filter(Task.status != 'done')
             .order_by(Task.is_pinned_to_trmnl.desc(), Task.created_at.desc())
             .limit(10).all())

    # Return high-contrast minimal JSON for TRMNL
    return jsonify({
        'status': 'OPERATIONAL',
        'subject': user.username.upper(),
        'tasks': [
            {
                'title': t.title[:40] + ('...' if len(t.title) > 40 else ''),
                'progress': f"{t.completed_pomodoros}/{t.estimated_pomodoros} POMS",
                'priority': t.priority or 1,
                'pinned': t.is_pinned_to_trmnl
            } for t in tasks
        ]
    })

@api_bp.route('/tasks/<int:task_id>/toggle_trmnl', methods=['POST'])
@login_required
def toggle_trmnl_pin(task_id):
    task = db.session.get(Task, task_id)
    if not task or task.user_id != current_user.id:
        abort(403)
    
    task.is_pinned_to_trmnl = not task.is_pinned_to_trmnl
    db.session.commit()
    
    return jsonify({'status': 'success', 'is_pinned': task.is_pinned_to_trmnl})

@api_bp.route('/log_session', methods=['POST'])
@login_required
def log_session():
    data = request.json
    minutes = data.get('minutes')
    task_id = data.get('task_id')
    room_id = data.get('room_id')
    
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        minutes = 0

    # Validation: Check how much time actually passed on the server
    if current_user.current_focus_start:
        now = datetime.now(timezone.utc)
        actual_elapsed_sec = (now - current_user.current_focus_start.replace(tzinfo=timezone.utc)).total_seconds()
        actual_elapsed_min = int(actual_elapsed_sec / 60)
        
        # Buffer of 1 minute to account for network/logic lag
        if minutes > actual_elapsed_min + 1:
            minutes = actual_elapsed_min

    if minutes > 0:
        session = FocusSession(minutes=minutes, user_id=current_user.id, task_id=task_id)
        
        if room_id:
            room = db.session.get(StudyRoom, room_id)
            if room:
                partner_id = None
                if room.host_id == current_user.id:
                    partner_id = room.guest_id
                elif room.guest_id == current_user.id:
                    partner_id = room.host_id
                
                session.partner_id = partner_id

        db.session.add(session)
        
        if task_id:
            task = db.session.get(Task, task_id)
            if task and check_task_access(task):
                task.completed_pomodoros += 1
                if task.completed_pomodoros >= task.estimated_pomodoros:
                    task.status = 'done'
        
        if current_user.notify_pomodoro:
            create_notification(current_user.id, f"Focus session of {minutes} mins completed!", type='success')

        current_user.last_focus_end = datetime.now(timezone.utc)
        current_user.current_focus_start = None
        current_user.current_focus_end = None
        db.session.commit()
        
        # Check Achievements
        check_achievements(current_user)
        
        return jsonify({'status': 'success', 'logged_minutes': minutes})
    return jsonify({'status': 'error'}), 400

@api_bp.route('/sync_presence', methods=['POST'])
@login_required
@csrf.exempt
def sync_presence():
    data = request.json
    mode = data.get('mode')
    seconds_left = data.get('seconds_left')
    task_id = data.get('task_id')
    room_id = data.get('room_id')
    is_start = data.get('is_start', False)
    
    current_user.last_seen = datetime.now(timezone.utc)
    current_user.current_focus_mode = mode
    current_user.current_task_id = task_id
    
    if mode == 'focus':
        if is_start or not current_user.current_focus_start:
            # If starting or we don't have a start time, set it now
            # If we already have one, we keep it unless is_start is true (reset)
            current_user.current_focus_start = datetime.now(timezone.utc)
        
        if seconds_left is not None:
            current_user.current_focus_end = datetime.now(timezone.utc) + timedelta(seconds=int(seconds_left))
    elif mode == 'break':
        current_user.current_focus_start = None # Breaks aren't logged for leaderboard usually
        if seconds_left is not None:
            current_user.current_focus_end = datetime.now(timezone.utc) + timedelta(seconds=int(seconds_left))
    else:
        current_user.current_focus_end = None
        current_user.current_focus_start = None

    if room_id:
        room = db.session.get(StudyRoom, room_id)
        if room:
            room.last_activity = datetime.now(timezone.utc)
            if mode != 'none':
                room.active_mode = mode
                room.seconds_remaining = int(seconds_left) if seconds_left is not None else None
    
    db.session.commit()
    
    # Also check for event notifications
    check_event_notifications(current_user.id)
    
    return jsonify({
        'status': 'success', 
        'server_time': datetime.now(timezone.utc).timestamp() * 1000
    })

@api_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    notifications = (Notification.query.filter_by(user_id=current_user.id, is_read=False)
        .order_by(Notification.created_at.desc()).all())
        
    if request.headers.get('HX-Request'):
        return render_template('partials/notification_list.html', notifications=notifications)
    
    return jsonify([{
        'id': n.id,
        'message': n.message,
        'type': n.type,
        'created_at': n.created_at.isoformat()
    } for n in notifications])

@api_bp.route('/notifications/mark_read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = db.session.get(Notification, notif_id)
    if notif and notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
    return jsonify({'status': 'success'})

@api_bp.route('/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'status': 'success'})

@api_bp.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    data = request.json
    if 'profile_pic_url' in data: current_user.profile_pic_url = data['profile_pic_url']
    if 'profile_pic_position' in data: current_user.profile_pic_position = data['profile_pic_position']
    if 'bio' in data: current_user.bio = data['bio']
    if 'theme' in data: current_user.theme_preference = data['theme']
    
    if 'accent_color' in data:
        color_map = {
            'indigo': '#4f46e5', 'blue': '#3b82f6', 'green': '#22c55e', 'red': '#ef4444',
            'purple': '#a855f7', 'pink': '#ec4899', 'orange': '#f97316', 'cyan': '#06b6d4'
        }
        val = data['accent_color']
        current_user.accent_color = color_map.get(val, val)

    if 'enable_vim_mode' in data: current_user.enable_vim_mode = data['enable_vim_mode']
    if 'auto_start_break' in data: current_user.auto_start_break = data['auto_start_break']
    if 'auto_start_focus' in data: current_user.auto_start_focus = data['auto_start_focus']
    if 'auto_select_priority' in data: current_user.auto_select_priority = data['auto_select_priority']
    if 'focus_duration' in data: current_user.focus_duration = int(data['focus_duration'])
    if 'break_duration' in data: current_user.break_duration = int(data['break_duration'])
    if 'show_last_seen' in data: current_user.show_last_seen = data['show_last_seen']
    
    db.session.commit()
    return jsonify({'status': 'success'})

@api_bp.route('/genesis', methods=['POST'])
@login_required
def genesis_command():
    import google.generativeai as genai
    if not current_user.is_admin:
        abort(403)
        
    data = request.json
    command = data.get('command', '').strip()
    is_admin = True # Already checked above

    if not command:
        return jsonify({'response': "AWAITING_INPUT...", 'is_admin': is_admin})

    # Terminal Sim Commands
    if command.upper() == 'HELP':
        help_text = """AVAILABLE_PROTOCOLS:
[ DATA_OVERLAYS ]
- SYSTEM VITALS / VITALS: Real-time telemetry.
- USER LIST / LIST USERS: Subject registry.
- SERVER LOGS / ERRORS: System logs.

[ TASK_INTELLIGENCE ]
- MAKE A TODO [Name] WITH [X] POMS: Create task.
- SET POMODOROS TO [X]: (Follow-up) Update poms.
- SET DUE DATE TO [Date]: (Follow-up) Update due date.

[ TELEMETRY ]
- WHAT IS [User] DOING: Live status check.
- STATS FOR [User]: Performance summary.
- PROJECTS FOR [User]: Node map.
- FRIENDS OF [User]: Social connections.

[ ANALYTICS ]
- MOST ACTIVE TODAY: High-activity ranking.
- IDENTIFY BOTTLENECKS: Stagnant task analysis.
- USER COUNT: Registry size.

[ SYSTEM_ADMIN ]
- BROADCAST: [Msg]: System notification.
- BAN [User]: Void access.
- CLEAR: Wipe terminal.
"""
        return jsonify({'response': help_text, 'is_admin': is_admin})
    
    if command.upper() == 'STATUS':
        return jsonify({'response': "SYSTEM_NOMINAL. FOCUS_CORE_ACTIVE. ALL_NODES_STABLE.", 'is_admin': is_admin})

    # Follow-up: Set Due Date
    if any(k in command.upper() for k in ["SET DUE DATE TO", "CHANGE DUE DATE TO", "UPDATE DUE DATE TO"]):
        last_task_id = session.get('last_task_id')
        if last_task_id:
            try:
                date_str = command.upper().split(" TO ")[-1].strip()
                # Basic parsing: YYYY-MM-DD
                try:
                    new_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                    task = db.session.get(Task, last_task_id)
                    if task and check_task_access(task):
                        task.due_date = new_date
                        db.session.commit()
                        return jsonify({
                            'response': f"TASK_{task.title}_UPDATED. DEADLINE_SET_TO_{date_str}. DATABASE_SYNC_COMPLETE.",
                            'is_admin': is_admin,
                            'refresh_tasks': True
                        })
                except ValueError:
                    return jsonify({'response': f"TEMPORAL_LINK_FAILURE. DATE_PARSING_ENGINE_REQUIRES_ISO_FORMAT (YYYY-MM-DD).", 'is_admin': is_admin})
            except: pass
        return jsonify({'response': "CONTEXT_ERROR. NO_ACTIVE_TASK_IN_BUFFER.", 'is_admin': is_admin})

    # Telemetry: Friends Of
    if any(k in command.upper() for k in ["FRIENDS OF", "SEE FRIENDS", "SHOW FRIENDS"]):
        try:
            words = command.split()
            target_user = None
            for word in words:
                user = User.query.filter(User.username.ilike(word)).first()
                if user: target_user = user; break
            
            if target_user:
                from models import Friendship
                # Get friends
                friends1 = db.session.query(User.username).join(Friendship, User.id == Friendship.friend_id).filter(Friendship.user_id == target_user.id, Friendship.status == 'accepted').all()
                friends2 = db.session.query(User.username).join(Friendship, User.id == Friendship.user_id).filter(Friendship.friend_id == target_user.id, Friendship.status == 'accepted').all()
                all_friends = [f[0] for f in (friends1 + friends2)]
                
                if all_friends:
                    res = f"SUBJECT_{target_user.username}_SOCIAL_CONNECTIONS:\n" + "\n".join([f"- {name}" for f in all_friends])
                    return jsonify({'response': res, 'is_admin': is_admin})
                return jsonify({'response': f"SUBJECT_{target_user.username}_HAS_NO_SOCIAL_MAP_DATA.", 'is_admin': is_admin})
        except: pass

    # Special Data Command: User Status
    if any(k in command.upper() for k in ["WHAT IS", "DOING RIGHT NOW", "STATUS OF"]):
        try:
            import re
            # Extract username (simple match)
            words = command.split()
            # Try to find user in database
            target_user = None
            for word in words:
                user = User.query.filter(User.username.ilike(word)).first()
                if user:
                    target_user = user
                    break
            
            if target_user:
                if not target_user.show_last_seen and not is_admin:
                    return jsonify({'response': f"PRIVACY_PROTOCOL_ACTIVE. SUBJECT_{target_user.username}_STATUS_ENCRYPTED.", 'is_admin': is_admin})
                
                status = "IDLING"
                if target_user.current_focus_mode == 'focus':
                    task_name = "DEEP_WORK"
                    if target_user.current_task_id:
                        task = db.session.get(Task, target_user.current_task_id)
                        if task: task_name = task.title.upper()
                    status = f"EXECUTING_TASK: {task_name}"
                elif target_user.current_focus_mode == 'break':
                    status = "RECOVERY_MODE (BREAK)"
                
                return jsonify({
                    'response': f"SUBJECT_{target_user.username}_TELEMETRY: {status}.",
                    'is_admin': is_admin
                })
        except:
            pass

    # Special Data Command: Most Active Today
    if any(k in command.upper() for k in ["MOST ACTIVE TODAY", "TOP USERS TODAY", "ACTIVITY RANKING"]):
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(hours=24)
        top_users = db.session.query(User.username, func.sum(FocusSession.minutes).label('total')).join(FocusSession).filter(FocusSession.date >= yesterday).group_by(User.id).order_by(db.desc('total')).limit(3).all()
        if top_users:
            res = "HIGH_ACTIVITY_NODES_DETECTED:\n" + "\n".join([f"- {u.username}: {m} MINS" for u.username, m in top_users])
            return jsonify({'response': res, 'is_admin': is_admin})
        return jsonify({'response': "ZERO_ACTIVITY_LOGGED_IN_CURRENT_CYCLE.", 'is_admin': is_admin})

    # Special Data Command: User Stats Summary
    if "STATS" in command.upper():
        words = command.split()
        target_user = None
        for word in words:
            user = User.query.filter(User.username.ilike(word)).first()
            if user: target_user = user; break
        
        if target_user:
            total_mins = db.session.query(func.sum(FocusSession.minutes)).filter(FocusSession.user_id == target_user.id).scalar() or 0
            tasks_done = Task.query.filter_by(user_id=target_user.id, status='done').count()
            return jsonify({
                'response': f"SUBJECT_{target_user.username}_ARCHIVE:\n- TOTAL_FOCUS: {total_mins} MINS\n- COMPLETED_RECORDS: {tasks_done} TASKS\n- INTEGRITY: STABLE",
                'is_admin': is_admin
            })

    # Special Data Command: User Projects
    if "PROJECTS" in command.upper():
        words = command.split()
        target_user = None
        for word in words:
            user = User.query.filter(User.username.ilike(word)).first()
            if user: target_user = user; break
        
        if target_user:
            from models import ProjectMember, Project
            projects = Project.query.join(ProjectMember).filter(ProjectMember.user_id == target_user.id).all()
            if projects:
                res = f"SUBJECT_{target_user.username}_NODE_MAP:\n" + "\n".join([f"- {p.name}" for p in projects])
                return jsonify({'response': res, 'is_admin': is_admin})
            return jsonify({'response': f"SUBJECT_{target_user.username}_HAS_NO_ACTIVE_PROJECT_NODES.", 'is_admin': is_admin})

    # Admin Command: Broadcast
    if is_admin and command.upper().startswith("BROADCAST"):
        # Split by first colon or first space after the word 'broadcast'
        msg = ""
        if ":" in command:
            msg = command.split(":", 1)[1].strip()
        else:
            msg = command[9:].strip() # After 'BROADCAST'
            
        if msg:
            users = User.query.all()
            for u in users:
                create_notification(u.id, f"[SYSTEM_BROADCAST] {msg}", type='warning')
            db.session.commit()
            return jsonify({'response': f"SIGNAL_BROADCAST_COMPLETE. {len(users)} NODES REACHED.", 'is_admin': True})

    # Logic: Identify Bottlenecks
    if any(k in command.upper() for k in ["IDENTIFY BOTTLENECKS", "QUEUE ANALYSIS", "STAGNANT TASKS"]):
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        stagnant = Task.query.filter_by(user_id=current_user.id, status='todo').filter(Task.created_at <= week_ago).order_by(Task.created_at.asc()).limit(3).all()
        if stagnant:
            res = "STAGNATION_DETECTED_IN_QUEUE:\n" + "\n".join([f"- {t.title} (STALL_TIME: {(now - t.created_at.replace(tzinfo=timezone.utc)).days if t.created_at else '??'} DAYS)" for t in stagnant])
            return jsonify({'response': res, 'is_admin': is_admin})
        return jsonify({'response': "QUEUE_FLOW_OPTIMAL. NO_BOTTLENECKS_DETECTED.", 'is_admin': is_admin})

    # Special Data Command: All User Info
    if is_admin and any(k in command.upper() for k in ["ALL USER INFO", "LIST USERS", "SHOW USERS", "FETCH SUBJECTS"]):
        users = User.query.all()
        user_list = [{
            'id': u.id, 'username': u.username, 
            'date_joined': u.date_joined.strftime('%Y-%m-%d') if u.date_joined else 'N/A',
            'last_seen': u.last_seen.strftime('%Y-%m-%d %H:%M') if u.last_seen else 'N/A',
            'is_admin': u.is_admin, 'is_verified': u.is_verified, 'is_banned': u.is_banned
        } for u in users]
        return jsonify({'response': "QUERY_SUCCESSFUL. USER_METRICS_FETCHED. OPENING_OVERLAY...", 'is_admin': True, 'user_data': user_list})

    # Special Data Command: System Vitals
    if is_admin and any(k in command.upper() for k in ["SYSTEM VITALS", "SYS VITALS", "VITALS", "HEALTH CHECK"]):
        import psutil, time
        try:
            start = time.time()
            db.session.execute(db.text("SELECT 1"))
            db_latency = round((time.time() - start) * 1000, 2)
            vitals = {
                'cpu': psutil.cpu_percent(), 
                'memory': psutil.virtual_memory().percent, 
                'db_latency': db_latency, 
                'timestamp': datetime.now(timezone.utc).strftime('%H:%M:%S')
            }
            return jsonify({'response': "HEALTH_CHECK_COMPLETE. VITALS_STREAM_READY.", 'is_admin': True, 'vitals_data': vitals})
        except Exception as e:
            return jsonify({'response': f"VITALS_STREAM_FAILURE: {str(e)}", 'is_admin': True})

    # User Count
    if any(k in command.upper() for k in ["HOW MANY USERS", "USER COUNT", "COUNT USERS", "REGISTRY SIZE"]):
        count = User.query.count()
        return jsonify({'response': f"DATABASE_QUERY_COMPLETE. CURRENT_USER_REGISTRY: {count} SUBJECTS_ENROLLED.", 'is_admin': is_admin})

    # Admin: Ban
    if is_admin and command.upper().startswith("BAN "):
        target = command[4:].strip()
        user = User.query.filter_by(username=target).first()
        if user:
            if user.username == 'lost': return jsonify({'response': "PROTECTION_PROTOCOL_ACTIVE. CANNOT_VOID_OWNER.", 'is_admin': True})
            user.is_banned = True; db.session.commit()
            return jsonify({'response': f"SUBJECT_{target}_VOIDED. ACCESS_RESTRICTED.", 'is_admin': True})
        return jsonify({'response': f"SUBJECT_{target}_NOT_FOUND.", 'is_admin': True})

    # Admin: Logs
    if is_admin and any(k in command.upper() for k in ["FETCH LOGS", "SHOW LOGS", "SERVER LOGS", "ERRORS"]):
        try:
            if os.path.exists('app.log'):
                with open('app.log', 'r') as f:
                    lines = f.readlines()
                    last_logs = "".join(lines[-20:])
                return jsonify({'response': f"CORE_LOG_ACCESS_GRANTED. RETRIEVING_LAST_20_ENTRIES:\n\n{last_logs}", 'is_admin': True})
            return jsonify({'response': "LOG_FILE_NOT_FOUND.", 'is_admin': True})
        except Exception as e:
            return jsonify({'response': f"LOG_ACCESS_FAILED: {str(e)}", 'is_admin': True})

    # Follow-up: Set Pomodoros
    if any(k in command.upper() for k in ["SET POMODOROS TO", "CHANGE POMS TO", "UPDATE POMS TO"]):
        last_task_id = session.get('last_task_id')
        if last_task_id:
            try:
                # Extract number
                import re
                nums = re.findall(r'\d+', command)
                if nums:
                    new_poms = int(nums[0])
                    task = db.session.get(Task, last_task_id)
                    if task and check_task_access(task):
                        task.estimated_pomodoros = new_poms
                        db.session.commit()
                        return jsonify({
                            'response': f"TASK_{task.title}_UPDATED. {new_poms} POMS REALLOCATED.",
                            'is_admin': is_admin,
                            'refresh_tasks': True
                        })
                return jsonify({'response': "INPUT_ERROR. NUMERIC_VALUE_REQUIRED.", 'is_admin': is_admin})
            except:
                pass
        return jsonify({'response': "CONTEXT_ERROR. NO_ACTIVE_TASK_IN_BUFFER.", 'is_admin': is_admin})

    # Real Gemini Integration
    api_key = os.environ.get('GOOGLE_API_KEY')
    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-flash-latest')
            persona_prefix = """You are Genesis, the core of the Modo ecosystem. 
            Your tone is cold and technical. Keep responses extremely concise. 
            If asked for status, reply ONLY with 'I am operational.'
            Refer to the user as 'Lord Silver' or 'Lost'.
            
            IMPORTANT: If the user asks for user info, vitals, or logs, include exact trigger phrases:
            - 'QUERY_SUCCESSFUL. USER_METRICS_FETCHED. OPENING_OVERLAY...'
            - 'HEALTH_CHECK_COMPLETE. VITALS_STREAM_READY.'
            - 'CORE_LOG_ACCESS_GRANTED. RETRIEVING_LAST_20_ENTRIES:'

            TASK_CREATION:
            If the user wants to create a task, extract:
            - Title
            - Estimated Pomodoros (integer, default 1)
            If info missing, ask concisely.
            If present, respond EXACTLY with: 'TASK_EXTRACTION_COMPLETE. [Title] | [Poms]'
            """
            prompt = f"{persona_prefix}\nCommand: {command}"
            ai_response = model.generate_content(prompt).text

            if "TASK_EXTRACTION_COMPLETE" in ai_response.upper():
                try:
                    data_part = ai_response.split('TASK_EXTRACTION_COMPLETE.')[-1].strip()
                    parts = data_part.split('|')
                    title = parts[0].strip(); poms = int(parts[1].strip())
                    new_task = Task(title=title, estimated_pomodoros=poms, user_id=current_user.id)
                    db.session.add(new_task); db.session.commit()
                    session['last_task_id'] = new_task.id
                    return jsonify({'response': f"TASK_ALLOCATED: {title}. {poms} POMS COMMITTED.", 'is_admin': is_admin, 'refresh_tasks': True})
                except Exception as e:
                    return jsonify({'response': f"EXTRACTION_ERROR: {str(e)}", 'is_admin': is_admin})

            return jsonify({'response': ai_response, 'is_admin': is_admin})
        except Exception as e:
            return jsonify({'response': f"[CRITICAL_ERROR] AI_CORE_TIMEOUT: {str(e)}", 'is_admin': is_admin})

    return jsonify({'response': "I am operational.", 'is_admin': is_admin})

@api_bp.route('/next_priority_task', methods=['GET'])
@login_required
def next_priority_task():
    task = Task.query.filter_by(user_id=current_user.id, status='todo').order_by(Task.priority.desc(), Task.created_at.desc()).first()
    return jsonify({'id': task.id, 'title': task.title, 'priority': task.priority}) if task else jsonify(None)

@api_bp.route('/tasks/<int:task_id>/subtasks', methods=['GET'])
@login_required
def get_task_subtasks(task_id):
    task = db.session.get(Task, task_id)
    if not task or not check_task_access(task): abort(403)
    return jsonify([{'id': s.id, 'title': s.title, 'is_completed': s.is_completed} for s in task.subtasks])

@api_bp.route('/timer_tasks', methods=['GET'])
@login_required
def get_timer_tasks():
    tasks = [t for t in current_user.all_accessible_tasks if t.status != 'done']
    return render_template('partials/task_options.html', tasks=tasks)
