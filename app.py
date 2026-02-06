import os
from datetime import datetime
from flask import Flask
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from dotenv import load_dotenv
from models import db, User, StudyRoom, ProjectInvite
from routes.auth import auth as auth_bp
from routes import main_bp, projects_bp, social_bp, study_bp, api_bp, schedule_bp, settings_bp
from utils import format_minutes, get_pending_invite
from services.achievement_service import seed_achievements

load_dotenv()

app = Flask(__name__)

# Ensure absolute path for SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'db.sqlite3')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_change_in_prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', f'sqlite:///{db_path}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    # Attempt to seed if DB is ready
    try:
        seed_achievements()
        # Failsafe: Ensure owner 'lost' is admin
        owner = User.query.filter_by(username='lost').first()
        if owner and not owner.is_admin:
            owner.is_admin = True
            db.session.commit()
    except:
        pass

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(projects_bp, url_prefix='/projects')
app.register_blueprint(social_bp)
app.register_blueprint(study_bp, url_prefix='/study')
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(schedule_bp, url_prefix='/schedule')
app.register_blueprint(settings_bp, url_prefix='/settings')

# Filters
app.jinja_env.filters['format_minutes'] = format_minutes
app.jinja_env.filters['get_pending_invite'] = get_pending_invite

# Context Processors
@app.context_processor
def inject_active_sync():
    if not current_user.is_authenticated:
        return {}
    active_room = StudyRoom.query.filter(
        ((StudyRoom.host_id == current_user.id) | (StudyRoom.guest_id == current_user.id)),
        StudyRoom.status == 'active'
    ).first()
    return {
        'active_sync_room': active_room,
        'amoled_unlocked': current_user.total_focus_hours >= 10
    }

if __name__ == '__main__':
    app.run(debug=True)