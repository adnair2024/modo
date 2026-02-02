from flask import render_template, request, jsonify, abort, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from . import projects_bp
from models import db, Project, ProjectMember, ProjectSection, Task, ProjectInvite, User
from utils import log_project_action, get_username_html, create_notification

@projects_bp.route('/')
@login_required
def projects_list():
    member_projects = Project.query.join(ProjectMember).filter(ProjectMember.user_id == current_user.id).all()
    pending_invites = ProjectInvite.query.filter_by(recipient_id=current_user.id, status='pending').all()
    return render_template('projects.html', projects=member_projects, pending_invites=pending_invites)

@projects_bp.route('/create', methods=['POST'])
@login_required
def create_project():
    name = request.form.get('name')
    description = request.form.get('description')
    if not name:
        return redirect(url_for('projects.projects_list'))
    
    project = Project(name=name, description=description, owner_id=current_user.id)
    db.session.add(project)
    db.session.commit()
    
    member = ProjectMember(project_id=project.id, user_id=current_user.id, role='owner')
    db.session.add(member)
    log_project_action(project.id, "Created the project")
    db.session.commit()
    
    return redirect(url_for('projects.project_detail', project_id=project.id))

@projects_bp.route('/<int:project_id>')
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    member = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
    if not member:
        abort(403)
    
    members = ProjectMember.query.filter_by(project_id=project_id).all()
    member_ids = [m.user_id for m in members]
    
    return render_template('project_detail.html', project=project, member_ids=member_ids)

@projects_bp.route('/<int:project_id>/sections', methods=['POST'])
@login_required
def add_project_section(project_id):
    project = Project.query.get_or_404(project_id)
    member = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
    if not member:
        abort(403)
    
    name = request.form.get('name')
    if name:
        order = len(project.sections)
        section = ProjectSection(project_id=project_id, name=name, order=order)
        db.session.add(section)
        log_project_action(project_id, f"Added section: {name}")
        db.session.commit()
    
    return redirect(url_for('projects.project_detail', project_id=project_id))

@projects_bp.route('/sections/<int:section_id>/tasks', methods=['POST'])
@login_required
def add_project_task(section_id):
    section = ProjectSection.query.get_or_404(section_id)
    project = section.project
    member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
    if not member:
        abort(403)
    
    title = request.form.get('title')
    description = request.form.get('description')
    priority = request.form.get('priority', type=int, default=1)
    due_date_str = request.form.get('due_date')
    
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass

    if title:
        task = Task(title=title, description=description, section_id=section_id, user_id=current_user.id, priority=priority, due_date=due_date)
        db.session.add(task)
        log_project_action(project.id, f"Added task: {title}")
        db.session.commit()
    
    return redirect(url_for('projects.project_detail', project_id=project.id))

@projects_bp.route('/sections/<int:section_id>/edit', methods=['POST'])
@login_required
def edit_project_section(section_id):
    section = ProjectSection.query.get_or_404(section_id)
    project = section.project
    member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
    if not member:
        abort(403)
    
    name = request.form.get('name')
    if name:
        old_name = section.name
        section.name = name
        log_project_action(project.id, f"Renamed section '{old_name}' to '{name}'")
        db.session.commit()
        return "", 204
    
    return redirect(url_for('projects.project_detail', project_id=project.id))

@projects_bp.route('/sections/<int:section_id>/delete', methods=['POST'])
@login_required
def delete_project_section(section_id):
    section = ProjectSection.query.get_or_404(section_id)
    project = section.project
    member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
    if not member or project.owner_id != current_user.id:
        abort(403)
    
    name = section.name
    db.session.delete(section)
    log_project_action(project.id, f"Deleted section: {name}")
    db.session.commit()
    
    return redirect(url_for('projects.project_detail', project_id=project.id))

@projects_bp.route('/tasks/<int:task_id>/move', methods=['POST'])
@login_required
def move_project_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not task.section_id:
        abort(400)
    
    project = task.section.project
    member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
    if not member:
        abort(403)
    
    new_section_id = request.form.get('section_id', type=int)
    if new_section_id:
        new_section = ProjectSection.query.get_or_404(new_section_id)
        if new_section.project_id != project.id:
            abort(400)
        
        old_section_name = task.section.name
        task.section_id = new_section_id
        log_project_action(project.id, f"Moved task '{task.title}' from {old_section_name} to {new_section.name}")
        db.session.commit()
    
    return "", 204

@projects_bp.route('/<int:project_id>/invite', methods=['POST'])
@login_required
def invite_to_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.owner_id != current_user.id:
        return jsonify({'error': 'Only the owner can invite others'}), 403
    
    if ProjectMember.query.filter_by(project_id=project_id).count() >= 6:
        return jsonify({'error': 'Member limit reached (max 6 total)'}), 400
    
    username = request.form.get('username')
    target_user = User.query.filter_by(username=username).first()
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    existing_member = ProjectMember.query.filter_by(project_id=project_id, user_id=target_user.id).first()
    if existing_member:
        return jsonify({'error': 'User is already a member'}), 400
        
    existing_invite = ProjectInvite.query.filter_by(project_id=project_id, recipient_id=target_user.id, status='pending').first()
    if existing_invite:
        return jsonify({'error': 'Invite already sent'}), 400
    
    invite = ProjectInvite(project_id=project_id, sender_id=current_user.id, recipient_id=target_user.id)
    db.session.add(invite)
    
    msg = f"{get_username_html(current_user)} invited you to project: <strong>{project.name}</strong>"
    create_notification(target_user.id, msg, type='project_invite', project_id=project.id)
    
    log_project_action(project_id, f"Invited {target_user.username}")
    db.session.commit()
    return jsonify({'message': 'Invite sent!'}), 200

@projects_bp.route('/invite/respond/<int:invite_id>/<action>', methods=['POST'])
@login_required
def respond_project_invite(invite_id, action):
    invite = ProjectInvite.query.filter_by(id=invite_id, recipient_id=current_user.id, status='pending').first_or_404()
    
    if action == 'accept':
        if ProjectMember.query.filter_by(project_id=invite.project_id).count() >= 6:
            invite.status = 'declined'
            db.session.commit()
            return "Project is full", 400
            
        invite.status = 'accepted'
        member = ProjectMember(project_id=invite.project_id, user_id=current_user.id)
        db.session.add(member)
        
        msg = f"{get_username_html(current_user)} joined your project: <strong>{invite.project.name}</strong>"
        create_notification(invite.sender_id, msg, type='success', project_id=invite.project_id)
        log_project_action(invite.project_id, "Joined the project")
    else:
        invite.status = 'declined'
        
    db.session.commit()
    return redirect(url_for('projects.projects_list'))

@projects_bp.route('/<int:project_id>/kick/<int:user_id>', methods=['POST'])
@login_required
def kick_project_member(project_id, user_id):
    project = Project.query.get_or_404(project_id)
    if project.owner_id != current_user.id:
        abort(403)
    if user_id == project.owner_id:
        return "Cannot kick owner", 400
    member = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first_or_404()
    username = member.user.username
    db.session.delete(member)
    log_project_action(project_id, f"Kicked member: {username}")
    db.session.commit()
    return redirect(url_for('projects.project_detail', project_id=project_id))
