import pytest

def test_base_template_noir_elements(auth_client):
    client, user = auth_client
    response = client.get('/')
    assert response.status_code == 200
    # Check for core Digital Noir identifiers
    assert b'MODO_OS' in response.data
    assert b'Command_Center' in response.data
    assert b'START' in response.data
    assert b'RESET' in response.data

def test_login_page_noir_elements(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b'SYS_ACCESS' in response.data
    assert b'INIT_SESSION' in response.data
    assert b'User_ID' in response.data

def test_timer_page_noir_elements(auth_client):
    client, user = auth_client
    response = client.get('/timer')
    assert response.status_code == 200
    assert b'FOCUS_EXECUTION' in response.data or b'IDLE_READY' in response.data
    assert b'EXE_START' in response.data
    assert b'Target_Execution_Task' in response.data

def test_settings_page_noir_elements(auth_client):
    client, user = auth_client
    # Flask-Login might redirect if not properly handled in some setups, but here it should be 200
    # Let's ensure we follow redirects if any (though /settings should be direct for auth_client)
    # The error showed 308 PERMANENT REDIRECT - likely due to trailing slash
    response = client.get('/settings/')
    if response.status_code == 308:
        response = client.get('/settings', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'System_Config' in response.data
    assert b'COMMIT_CHANGES' in response.data
    assert b'Hardware_Skin' in response.data

def test_index_page_noir_elements(auth_client):
    client, user = auth_client
    response = client.get('/')
    assert response.status_code == 200
    assert b'Command_Center' in response.data
    assert b'Initial_Task_Input_Protocol' in response.data
    assert b'ADD_TO_QUEUE' in response.data
