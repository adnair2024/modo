@main_bp.route('/habits')
@login_required
def habits():
    user_habits = Habit.query.filter_by(user_id=current_user.id).order_by(Habit.created_at.desc()).all()
    
    today = datetime.now(timezone.utc).date()
    dates = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        dates.append(d)
        
    start_date = dates[0]
    end_date = dates[-1]
    
    habit_ids = [h.id for h in user_habits]
    completions = HabitCompletion.query.filter(
        HabitCompletion.habit_id.in_(habit_ids),
        HabitCompletion.date >= start_date,
        HabitCompletion.date <= end_date
    ).all()
    
    comp_map = {(c.habit_id, c.date): True for c in completions}
    
    habits_data = []
    for h in user_habits:
        status_list = []
        for d in dates:
            is_done = (h.id, d) in comp_map
            status_list.append({
                'date': d.strftime('%Y-%m-%d'),
                'is_done': is_done,
                'is_today': (d == today),
                'day_name': d.strftime('%a')
            })
            
        habits_data.append({
            'habit': h,
            'days': status_list
        })

    # Yearly Heatmap Data
    year_start = today.replace(month=1, day=1)
    year_completions = HabitCompletion.query.join(Habit).filter(
        Habit.user_id == current_user.id,
        HabitCompletion.date >= year_start
    ).all()
    
    heatmap_data = {}
    for c in year_completions:
        d_str = c.date.strftime('%Y-%m-%d')
        heatmap_data[d_str] = heatmap_data.get(d_str, 0) + 1

    current_year = today.year

    if request.headers.get('HX-Request') and request.headers.get('HX-Target') == 'habit-list-container':
        return render_template('partials/habit_list.html', habits=habits_data, dates=dates)
        
    return render_template('habits.html', habits=habits_data, dates=dates, heatmap_data=heatmap_data, current_year=current_year)

@main_bp.route('/habits/add', methods=['POST'])
@login_required
def add_habit():
    title = request.form.get('title')
    if title:
        title = title[:200]
        h = Habit(title=title, user_id=current_user.id)
        db.session.add(h)
        db.session.commit()
    
    if request.headers.get('HX-Request'):
        return habits()
    return redirect(url_for('main.habits'))

@main_bp.route('/habits/<int:habit_id>/delete', methods=['POST'])
@login_required
def delete_habit(habit_id):
    habit = db.session.get(Habit, habit_id)
    if not habit: abort(404)
    if habit.user_id != current_user.id:
        abort(403)
    db.session.delete(habit)
    db.session.commit()
    
    if request.headers.get('HX-Request'):
        return habits()
    return redirect(url_for('main.habits'))

@main_bp.route('/habits/<int:habit_id>/toggle', methods=['POST'])
@login_required
def toggle_habit(habit_id):
    habit = db.session.get(Habit, habit_id)
    if not habit: abort(404)
    if habit.user_id != current_user.id:
        abort(403)
        
    date_str = request.args.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = datetime.now(timezone.utc).date()
    else:
        target_date = datetime.now(timezone.utc).date()

    comp = HabitCompletion.query.filter_by(habit_id=habit_id, date=target_date).first()
    
    if comp:
        db.session.delete(comp)
    else:
        comp = HabitCompletion(habit_id=habit_id, date=target_date)
        db.session.add(comp)
        
    db.session.commit()
    
    if request.headers.get('HX-Request'):
        # If toggling from the main index habits list, return the cell
        target = request.headers.get('HX-Target', '')
        if target.startswith('habit-cell-') or target.startswith('habit-home-'):
             return render_template('partials/habit_cell.html', habit=habit, day={'date': target_date.strftime('%Y-%m-%d'), 'is_done': comp is None})
        
        return habits()

    return redirect(url_for('main.index'))
