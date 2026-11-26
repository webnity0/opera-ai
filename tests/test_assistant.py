from app.assistant import answer

def test_assistant():
    docs=[dict(id=1,status='expired',days=-3),dict(id=2,status='soon',days=6),dict(id=3,status='valid',days=90)]
    assert answer('documents expirés',docs,2)['total']==1
    assert answer('cette semaine',docs,2)['items'][0]['id']==2
    assert answer('résumé',docs,2)['total']==2
    assert answer('autre question',docs,2)['total']==0

def test_assistant_isolation():
    from fastapi.testclient import TestClient
    from app.main import app
    from uuid import uuid4
    a,b=TestClient(app),TestClient(app)
    assert a.post('/api/assistant',json={'question':'résumé'}).status_code==401
    for c in (a,b):
        assert c.post('/api/register',json={'organization':'Test Org','email':f'{uuid4()}@example.com','password':'test-password-1234'}).status_code==200
    assert a.post('/api/demo/seed').status_code==200
    assert a.post('/api/assistant',json={'question':'résumé'}).json()['total']==2
    assert b.post('/api/assistant',json={'question':'résumé'}).json()['total']==0
