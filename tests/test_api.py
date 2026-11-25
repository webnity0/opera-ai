import os
from fastapi.testclient import TestClient
from app.main import app
from uuid import uuid4

def test_tenant_isolation_and_login():
    os.environ['COOKIE_SECURE']='0'
    a,b=TestClient(app),TestClient(app)
    password='test-password-1234'
    email=f'{uuid4()}@example.com'
    for client,addr in [(a,email),(b,f'{uuid4()}@example.com')]:
        assert client.post('/api/register',json={'organization':'Test Org','email':addr,'password':password}).status_code==200
    cid=a.post('/api/companies',json={'name':'Test Company'}).json()['id']
    payload={'company_id':cid,'kind':'Insurance','expiry':'2027-01-01'}
    did=a.post('/api/documents',json=payload).json()['id']
    assert b.get('/api/companies').json()==[]
    assert b.get('/api/documents').json()==[]
    assert b.post('/api/documents',json=payload).status_code==404
    assert b.put(f'/api/documents/{did}',json=payload).status_code==404
    assert b.delete(f'/api/documents/{did}').status_code==404
    assert b.delete(f'/api/companies/{cid}').status_code==404
    assert a.post('/api/logout').status_code==200
    assert a.get('/api/me').status_code==401
    assert a.post('/api/login',json={'email':email,'password':'incorrect'}).status_code==401
    assert a.post('/api/login',json={'email':email,'password':password}).status_code==200
    assert a.get('/api/documents').json()[0]['id']==did
