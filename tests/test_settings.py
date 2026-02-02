def test_settings_view(auth_client):
    client, user = auth_client
    response = client.get('/settings/')
    assert response.status_code == 200
