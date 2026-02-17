import os
import logging
from datetime import datetime, timezone
from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_caching import Cache
from whitenoise import WhiteNoise
from extensions import cache, csrf
from dotenv import load_dotenv
from models import db, User, StudyRoom, ProjectInvite
from routes.auth import auth as auth_bp
from routes import main_bp, projects_bp, social_bp, study_bp, api_bp, schedule_bp, settings_bp
from utils import format_minutes, get_pending_invite
from services.achievement_service import seed_achievements

load_dotenv()

app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/', prefix='static/')

# Configure logging
if not app.debug:
    file_handler = logging.FileHandler('app.log')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
else:
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s: %(message)s')

# Ensure absolute path for SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'db.sqlite3')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_change_in_prod')

if os.environ.get('MODO_TESTING'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    from sqlalchemy import StaticPool
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'poolclass': StaticPool}
else:
    db_uri = os.environ.get('SQLALCHEMY_DATABASE_URI') or os.environ.get('DATABASE_URL')
    if db_uri and db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri or f'sqlite:///{db_path}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Caching Configuration
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300

# Session Security (Production)
if not app.debug and not os.environ.get('MODO_TESTING'):
    # In production (Northflank/Supabase), use secure cookies
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True

db.init_app(app)
migrate = Migrate(app, db)
cache.init_app(app)
csrf.init_app(app)

with app.app_context():
    # Attempt to seed if DB is ready
    if not os.environ.get('MODO_TESTING'):
        try:
            seed_achievements()
            # Failsafe: Ensure owner 'lost' is admin and verified
            owner = User.query.filter_by(username='lost').first()
            if owner:
                changed = False
                if not owner.is_admin:
                    owner.is_admin = True
                    changed = True
                if not owner.is_verified:
                    owner.is_verified = True
                    changed = True
                if changed:
                    db.session.commit()
        except:
            pass

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        # Check if user needs to be remotely logged out
        if current_user.must_logout:
            current_user.must_logout = False
            db.session.commit()
            logout_user()
            flash('You have been logged out for a scheduled update. Please wait a moment.', 'info')
            return redirect(url_for('auth.login', updating=1))
            
        now = datetime.now(timezone.utc)
        # Throttle update to once every 5 minutes
        if not current_user.last_seen or (now - current_user.last_seen.replace(tzinfo=timezone.utc)).total_seconds() > 300:
            current_user.last_seen = now
            db.session.commit()
            try:
                db.session.refresh(current_user)
            except:
                pass

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
app.jinja_env.globals.update(int=int)

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

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
