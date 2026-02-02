from flask import Blueprint

main_bp = Blueprint('main', __name__)
projects_bp = Blueprint('projects', __name__)
social_bp = Blueprint('social', __name__)
study_bp = Blueprint('study', __name__)
api_bp = Blueprint('api', __name__)
schedule_bp = Blueprint('schedule', __name__)
settings_bp = Blueprint('settings', __name__)

from . import main, projects, social, study, api, schedule, settings

