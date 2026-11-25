from fastapi.testclient import TestClient
from app.main import app
from test_v2 import register

def test_demo_onboarding_is_explicit_and_private():
    a,b=TestClient(app),TestClient(app);register(a);register(b)
    assert TestClient(app).post('/api/demo/seed').status_code==401
    assert a.post('/api/demo/seed').status_code==200
    assert a.get('/api/dashboard').json()=={'companies':3,'documents':3,'expired':1,'soon':1}
    assert all(c['email']=='' for c in a.get('/api/companies').json())
    assert b.get('/api/companies').json()==[]
    assert a.post('/api/demo/seed').status_code==409

def test_browser_security_headers():
    r=TestClient(app).get('/')
    assert r.status_code==200
    assert r.headers['permissions-policy']=='camera=(), microphone=(), geolocation=()'
    assert r.headers['x-frame-options']=='DENY'
    assert 'demoSeed' in r.text
