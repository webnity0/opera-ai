from fastapi.testclient import TestClient
from app.main import app
from uuid import uuid4

def account():
    c=TestClient(app)
    assert c.post('/api/register',json={'organization':'RC10 test','email':f'{uuid4()}@example.com','password':'test-password-1234'}).status_code==200
    return c

def test_project_isolation_and_missing():
    a,b=account(),account()
    cid=a.post('/api/companies',json={'name':'Atlas test'}).json()['id']
    data={'name':'Chantier test','companies':[cid],'required':['Assurance décennale']}
    assert b.post('/api/projects',json=data).status_code==404
    r=a.post('/api/projects',json=data);assert r.status_code==200,r.text
    pid=r.json()['id']
    assert a.get('/api/projects').json()[0]['companies'][0]['missing']==['Assurance décennale']
    assert b.get('/api/projects').json()==[]
    assert b.delete(f'/api/projects/{pid}').status_code==404
    assert a.post('/api/documents',json={'company_id':cid,'kind':'Assurance décennale','expiry':'2099-01-01'}).status_code==200
    assert a.get('/api/projects').json()[0]['companies'][0]['missing']==[]
    assert a.delete(f'/api/projects/{pid}').status_code==200
    assert len(a.get('/api/documents').json())==1

def test_generative_disabled_and_consent(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    a=account()
    assert a.post('/api/assistant/generative',json={'question':'Résumé'}).status_code==403
    assert a.post('/api/assistant/generative',json={'question':'Résumé','consent':True}).status_code==503
