from fastapi.testclient import TestClient
from app.main import app
from test_v2 import register
from test_pdf import sample_pdf

def test_renewal_and_calendar():
    a,b=TestClient(app),TestClient(app);register(a);register(b)
    c=a.post('/api/companies',json={'name':'Entreprise privée, A;B'}).json()['id']
    d=a.post('/api/documents',json={'company_id':c,'kind':'Assurance','expiry':'2027-01-01'}).json()['id']
    url=f'/api/documents/{d}/renew'; payload={'expiry':'2028-01-01','reference':'REF-2'}; files={'file':('renew.pdf',sample_pdf(),'application/pdf')}
    assert b.put(url,data=payload,files=files).status_code==404
    assert a.put(url,data=payload,files=files).status_code==200
    assert a.get('/api/documents').json()[0]['expiry']=='2028-01-01'
    assert a.get('/api/storage').json()['files']==1
    assert a.put(url,data=payload,files=files).status_code==200
    assert a.get('/api/storage').json()['files']==1
    assert a.put(url,data={'expiry':'2029-01-01'},files={'file':('bad.pdf',b'bad','application/pdf')}).status_code==422
    assert a.get('/api/documents').json()[0]['expiry']=='2028-01-01'
    cal=a.get('/api/calendar.ics');assert cal.status_code==200
    assert 'DTSTART;VALUE=DATE:20280101' in cal.text
    assert 'Entreprise privée\\, A\\;B' in cal.text
    assert 'Entreprise privée' not in b.get('/api/calendar.ics').text
    assert TestClient(app).get('/api/calendar.ics').status_code==401

def test_live_stripe_blocked(monkeypatch):
    a=TestClient(app);register(a);monkeypatch.setenv('STRIPE_SECRET_KEY','sk_live_dummy')
    assert a.post('/api/billing/portal').status_code==403
    assert a.post('/webhooks/stripe',json={}).status_code==403
