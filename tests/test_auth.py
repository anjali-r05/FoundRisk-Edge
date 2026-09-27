def test_landing_is_public(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Know what the numbers" in response.data


def test_workspace_redirects_when_signed_out(client):
    response = client.get("/overview")
    assert response.status_code == 302
    assert "/signin" in response.headers["Location"]


def _csrf(client, path):
    response = client.get(path)
    assert response.status_code == 200
    with client.session_transaction() as sess:
        return sess["csrf_token"]


def test_signup_login_logout(client):
    token = _csrf(client, "/signup")
    response = client.post("/signup", data={"csrf_token":token,"name":"Test User","email":"test@example.com","password":"long-secure-passphrase","confirm_password":"long-secure-passphrase"}, follow_redirects=False)
    assert response.status_code == 302
    assert "/overview" in response.headers["Location"]
    assert client.get("/overview").status_code == 200
    token = _csrf(client, "/overview")
    response = client.post("/logout", data={"csrf_token":token}, follow_redirects=False)
    assert response.status_code == 302
    assert client.get("/overview").status_code == 302


def test_duplicate_signup_rejected(client):
    token = _csrf(client, "/signup")
    data={"csrf_token":token,"name":"Test User","email":"same@example.com","password":"long-secure-passphrase","confirm_password":"long-secure-passphrase"}
    client.post("/signup",data=data)
    token=_csrf(client,"/overview")
    client.post("/logout",data={"csrf_token":token})
    token=_csrf(client,"/signup")
    data["csrf_token"]=token
    response=client.post("/signup",data=data)
    assert response.status_code==200
    assert b"already exists" in response.data
