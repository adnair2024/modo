from app import app
from models import db, User, Task, Tag, Project, ProjectSection, Achievement, Friendship, StudyRoom, Subtask, ProjectMember, ProjectInvite, ProjectActivity, FocusSession, Event, Habit, UserAchievement, EventCompletion, Notification, HabitCompletion, ChatMessage

def force_init():
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        
        # We also need to stamp the migration so flask-migrate thinks we are up to date
        from flask_migrate import stamp
        stamp()
        print("Database initialized and stamped.")

if __name__ == "__main__":
    force_init()
