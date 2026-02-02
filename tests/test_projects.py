from models import Project, ProjectSection, Task, ProjectMember, ProjectInvite, User
from werkzeug.security import generate_password_hash

def test_create_project(auth_client):
    client, user = auth_client
    client.post('/projects/create', data={'name': 'New Project', 'description': 'Test'})
    project = Project.query.filter_by(name='New Project').first()
    assert project is not None
    assert project.owner_id == user.id
    assert len(project.members) == 1

def test_project_flow(auth_client):
    client, user = auth_client
    # Create
    client.post('/projects/create', data={'name': 'Flow Project'})
    project = Project.query.filter_by(name='Flow Project').first()
    
    # Add Section
    client.post(f'/projects/{project.id}/sections', data={'name': 'Todo'})
    section = ProjectSection.query.filter_by(project_id=project.id).first()
    assert section.name == 'Todo'
    
    # Add Task
    client.post(f'/projects/sections/{section.id}/tasks', data={'title': 'Project Task'})
    task = Task.query.filter_by(title='Project Task').first()
    assert task.section_id == section.id
    
    # Edit Section
    client.post(f'/projects/sections/{section.id}/edit', data={'name': 'Doing'})
    assert ProjectSection.query.get(section.id).name == 'Doing'
    
    # Delete Section
    client.post(f'/projects/sections/{section.id}/delete')
    assert ProjectSection.query.get(section.id) is None

def test_project_invite(auth_client):
    client, user = auth_client
    from app import db
    
    # Create another user
    other = User(username='other', password_hash=generate_password_hash('pass', method='scrypt'))
    db.session.add(other)
    db.session.commit()
    
    # Create Project
    client.post('/projects/create', data={'name': 'Invite Project'})
    project = Project.query.filter_by(name='Invite Project').first()
    
    # Invite
    response = client.post(f'/projects/{project.id}/invite', data={'username': 'other'})
    assert response.status_code == 200
    assert ProjectInvite.query.filter_by(recipient_id=other.id).first() is not None
    
    # Login as other and accept
    client.get('/logout')
    client.post('/login', data={'username': 'other', 'password': 'pass'})
    
    invite = ProjectInvite.query.filter_by(recipient_id=other.id).first()
    client.post(f'/projects/invite/respond/{invite.id}/accept')
    
    assert ProjectMember.query.filter_by(project_id=project.id, user_id=other.id).first() is not None
