from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from . import settings_bp
from models import db

@settings_bp.route('/')
@login_required
def settings():
    return render_template('settings.html')

