from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from models import db, User

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            if user.is_banned:
                flash('Your account has been banned.', 'error')
                return redirect(url_for('auth.login'))
            login_user(user)
            return redirect(url_for('main.index'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists', 'error')
        else:
            new_user = User(username=username, password_hash=generate_password_hash(password, method='scrypt'))
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('main.index'))
    return render_template('signup.html')

@auth.route('/logout')
@login_required
def logout():
    # Clear live focus state on logout
    current_user.current_focus_mode = 'none'
    current_user.current_focus_start = None
    current_user.current_focus_end = None
    db.session.commit()
    
    logout_user()
    return redirect(url_for('auth.login'))
