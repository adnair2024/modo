from models import db, Achievement, UserAchievement
from utils import create_notification

def check_achievements(user):
    # Get user's earned ids
    earned_ids = {ua.achievement_id for ua in user.achievements}
    
    # Check all achievements
    achievements = Achievement.query.all()
    
    unearned = [ach for ach in achievements if ach.id not in earned_ids]
    if not unearned:
        return

    # Only calculate stats if we have unearned achievements of that type
    total_hours = None
    total_pomos = None
    friend_count = None
    partner_sessions = None
    
    new_unlocks = []
    
    for ach in unearned:
        unlocked = False
        if ach.criteria_type == 'focus_hours':
            if total_hours is None: total_hours = user.total_focus_hours
            if total_hours >= ach.criteria_value: unlocked = True
        elif ach.criteria_type == 'pomodoro_count':
            if total_pomos is None: total_pomos = sum(session.minutes // 25 for session in user.focus_sessions)
            if total_pomos >= ach.criteria_value: unlocked = True
        elif ach.criteria_type == 'friend_count':
            if friend_count is None:
                from models import Friendship
                friend_count = Friendship.query.filter(
                    ((Friendship.user_id == user.id) | (Friendship.friend_id == user.id)),
                    Friendship.status == 'accepted'
                ).count()
            if friend_count >= ach.criteria_value: unlocked = True
        elif ach.criteria_type == 'partner_session_count':
            if partner_sessions is None:
                from models import FocusSession
                partner_sessions = FocusSession.query.filter(
                    FocusSession.user_id == user.id,
                    FocusSession.partner_id.isnot(None)
                ).count()
            if partner_sessions >= ach.criteria_value: unlocked = True
            
        if unlocked:
            ua = UserAchievement(user_id=user.id, achievement_id=ach.id)
            db.session.add(ua)
            new_unlocks.append(ach)
            
    if new_unlocks:
        db.session.commit()
        for ach in new_unlocks:
            create_notification(user.id, f"🏆 Achievement Unlocked: {ach.name}", type='success')

def seed_achievements():
    # Define all achievements
    all_badges = [
        # Focus Hours
        ('Novice Focus', 'Complete 1 hour of focus', '🌱', 'focus_hours', 1),
        ('Getting Serious', 'Complete 5 hours of focus', '🌿', 'focus_hours', 5),
        ('Dedicated', 'Complete 10 hours of focus', '🌳', 'focus_hours', 10),
        ('Unstoppable', 'Complete 20 hours of focus', '🔥', 'focus_hours', 20),
        ('Master of Time', 'Complete 50 hours of focus', '⏳', 'focus_hours', 50),
        ('Grandmaster', 'Complete 75 hours of focus', '🧙‍♂️', 'focus_hours', 75),
        ('Legendary', 'Complete 100 hours of focus', '👑', 'focus_hours', 100),
        
        # Pomodoro Count
        ('First Pomo', 'Complete your first pomodoro', '🍅', 'pomodoro_count', 1),
        ('Pomo Enthusiast', 'Complete 10 pomodoros', '🥗', 'pomodoro_count', 10),
        ('Pomo Pro', 'Complete 50 pomodoros', '🍕', 'pomodoro_count', 50),
        ('Pomo Master', 'Complete 100 pomodoros', '🍝', 'pomodoro_count', 100),
        ('Pomo Legend', 'Complete 500 pomodoros', '🥫', 'pomodoro_count', 500),
        
        # Social Sync
        ('Social Butterfly', 'Add 1 friend', '🦋', 'friend_count', 1),
        ('Community Member', 'Add 5 friends', '🤝', 'friend_count', 5),
        ('Networker', 'Add 10 friends', '🌐', 'friend_count', 10),
        ('Influencer', 'Add 25 friends', '📣', 'friend_count', 25),
        
        # Partner Sessions (Social Sync)
        ('Study Buddy', 'Complete 1 session with a partner', '🤜', 'partner_session_count', 1),
        ('Collaborator', 'Complete 10 sessions with partners', '🤝', 'partner_session_count', 10),
        ('Synergy', 'Complete 50 sessions with partners', '⚡', 'partner_session_count', 50),
    ]
    
    for name, desc, icon, c_type, c_val in all_badges:
        existing = Achievement.query.filter_by(name=name).first()
        if not existing:
            a = Achievement(name=name, description=desc, icon=icon, criteria_type=c_type, criteria_value=c_val)
            db.session.add(a)
    
    db.session.commit()
