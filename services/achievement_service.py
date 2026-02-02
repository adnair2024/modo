from models import db, Achievement, UserAchievement
from utils import create_notification

def check_achievements(user):
    # Total Focus Time
    # user.total_focus_hours returns float hours
    total_hours = user.total_focus_hours
    
    # Get all time-based achievements
    achievements = Achievement.query.filter_by(criteria_type='focus_hours').all()
    
    # Get user's earned ids
    earned_ids = {ua.achievement_id for ua in user.achievements}
    
    new_unlocks = []
    
    for ach in achievements:
        if ach.id not in earned_ids and total_hours >= ach.criteria_value:
            ua = UserAchievement(user_id=user.id, achievement_id=ach.id)
            db.session.add(ua)
            new_unlocks.append(ach)
            
    if new_unlocks:
        db.session.commit()
        for ach in new_unlocks:
            create_notification(user.id, f"🏆 Achievement Unlocked: {ach.name}", type='success')

def seed_achievements():
    if Achievement.query.first():
        return
        
    badges = [
        (1, 'Novice Focus', 'Complete 1 hour of focus', '🌱'),
        (5, 'Getting Serious', 'Complete 5 hours of focus', '🌿'),
        (10, 'Dedicated', 'Complete 10 hours of focus', '🌳'),
        (20, 'Unstoppable', 'Complete 20 hours of focus', '🔥'),
        (50, 'Master of Time', 'Complete 50 hours of focus', '⏳'),
        (75, 'Grandmaster', 'Complete 75 hours of focus', '🧙‍♂️'),
        (100, 'Legendary', 'Complete 100 hours of focus', '👑'),
    ]
    
    for hours, name, desc, icon in badges:
        a = Achievement(name=name, description=desc, icon=icon, criteria_type='focus_hours', criteria_value=hours)
        db.session.add(a)
    
    db.session.commit()
