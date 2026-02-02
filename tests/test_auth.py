from models import User

def test_signup(client):
    response = client.post('/signup', data={'username': 'newuser', 'password': 'newpassword'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'My Tasks' in response.data # Redirects to index
    assert User.query.filter_by(username='newuser').first() is not None

def test_signup_existing_user(client):
    # Create user first
    client.post('/signup', data={'username': 'existing', 'password': 'password'})
    # Try again
    response = client.post('/signup', data={'username': 'existing', 'password': 'password'}, follow_redirects=True)
    assert b'Username already exists' in response.data

def test_login(client):
    client.post('/signup', data={'username': 'loginuser', 'password': 'password'})
    client.get('/logout')
    
    response = client.post('/login', data={'username': 'loginuser', 'password': 'password'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'My Tasks' in response.data

def test_login_invalid(client):
    response = client.post('/login', data={'username': 'wrong', 'password': 'wrong'}, follow_redirects=True)
    assert b'Invalid username or password' in response.data

def test_logout(client):
    client.post('/signup', data={'username': 'outuser', 'password': 'password'})
    response = client.get('/logout', follow_redirects=True)
    assert b'Login' in response.data
