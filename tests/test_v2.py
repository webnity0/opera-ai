from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app

def register(c):
    email=f'{uuid4()}@example.com'
    assert c.post('/api/register',json={'organization':'Demo','email':email,'password':'test-password-1234'}).status_code==200
    return email

def test_settings_reminders_and_revocation():
    a,b=TestClient(app),TestClient(app)
    email=register(a); register(b)
    cid=a.post('/api/companies',json={'name':'Demo BTP'}).json()['id']
    assert b.put(f'/api/companies/{cid}',json={'name':'Intrus'}).status_code==404
    assert a.put(f'/api/companies/{cid}',json={'name':'Demo BTP 2'}).status_code==200
    did=a.post('/api/documents',json={'company_id':cid,'kind':'Assurance','expiry':'2027-01-01'}).json()['id']
    assert b.post(f'/api/reminders/{did}').status_code==404
    assert a.post(f'/api/reminders/{did}').status_code==200
    assert str(did) in a.get('/api/reminders').json()
    assert b.get('/api/reminders').json()=={}
    assert a.put('/api/settings',json={'organization':'New Demo'}).status_code==200
    assert a.get('/api/me').json()['organization']=='New Demo'
    token=a.cookies.get('opera_session')
    assert a.post('/api/logout').status_code==200
    assert TestClient(app).get('/api/me',cookies={'opera_session':token}).status_code==401
    assert a.post('/api/login',json={'email':email,'password':'test-password-1234'}).status_code==200
    token=a.cookies.get('opera_session')
    assert a.post('/api/password',json={'current':'wrong','new':'new-password-1234'}).status_code==400
    assert a.post('/api/password',json={'current':'test-password-1234','new':'new-password-1234'}).status_code==200
    assert TestClient(app).get('/api/me',cookies={'opera_session':token}).status_code==401
    assert a.post('/api/login',json={'email':email,'password':'new-password-1234'}).status_code==200
    assert a.delete(f'/api/documents/{did}').status_code==200
    assert a.get('/api/reminders').json()=={}
