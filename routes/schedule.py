from flask import render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user
from datetime import datetime
import calendar
from . import schedule_bp
from models import db, Event, Notification
from utils import create_notification

@schedule_bp.route('/')
@login_required
def schedule():
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    
    if month > 12:
        month = 1
        year += 1
    elif month < 1:
        month = 12
        year -= 1
        
    cal_matrix = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
    
    events = Event.query.filter_by(user_id=current_user.id).all()
    
    return render_template('schedule.html', 
                           year=year, month=month, month_name=month_name, 
                           calendar_matrix=cal_matrix, events=events)

@schedule_bp.route('/add', methods=['POST'])
@login_required
def add_event():
    title = request.form.get('title')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    recurrence = request.form.get('recurrence', 'none')
    recurrence_days_list = request.form.getlist('recurrence_days')
    
    if title and start_time_str and end_time_str:
        try:
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            
            recurrence_days_str = ",".join(recurrence_days_list) if recurrence_days_list else None

            new_event = Event(
                title=title,
                start_time=start_time,
                end_time=end_time,
                recurrence=recurrence,
                recurrence_days=recurrence_days_str,
                user_id=current_user.id
            )
            db.session.add(new_event)
            db.session.commit()
        except ValueError:
            pass
            
    return redirect(url_for('schedule.schedule'))

@schedule_bp.route('/event/<int:event_id>/edit', methods=['GET'])
@login_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)
    return render_template('partials/event_edit.html', event=event)

@schedule_bp.route('/event/<int:event_id>/update', methods=['POST'])
@login_required
def update_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)

    title = request.form.get('title')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    recurrence = request.form.get('recurrence')
    recurrence_days_list = request.form.getlist('recurrence_days')

    if title: event.title = title
    if recurrence: event.recurrence = recurrence
    
    event.recurrence_days = ",".join(recurrence_days_list) if recurrence_days_list else None

    if start_time_str:
        try:
            event.start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
            
    if end_time_str:
        try:
            event.end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass

    db.session.commit()
    return render_template('partials/event_item.html', event=event)

@schedule_bp.route('/event/<int:event_id>/item', methods=['GET'])
@login_required
def get_event_item(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)
    return render_template('partials/event_item.html', event=event)

@schedule_bp.route('/delete/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)
        
    Notification.query.filter_by(event_id=event.id).update({'event_id': None})
    
    db.session.delete(event)
    db.session.commit()
    return redirect(url_for('schedule.schedule'))
