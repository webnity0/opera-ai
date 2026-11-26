from test_rc10 import account
from openpyxl import Workbook
from io import BytesIO
from pypdf import PdfReader

def workbook(rows):
    w=Workbook();s=w.active
    for row in rows:s.append(row)
    b=BytesIO();w.save(b);return b.getvalue()

def test_excel_preview_and_formula():
    a=account()
    r=a.post('/api/companies/xlsx-preview',files={'file':('companies.xlsx',workbook([['Nom','Contact','Email'],['Atlas','Jean','a@example.com']]))})
    assert r.status_code==200,r.text
    assert r.json()['rows']==[{'name':'Atlas','contact':'Jean','email':'a@example.com'}]
    assert a.get('/api/companies').json()==[]
    assert a.post('/api/companies/xlsx-preview',files={'file':('bad.xlsx',workbook([['=1+1']]))}).status_code==422

def test_pdf_report_and_project_update():
    a,b=account(),account();cid=a.post('/api/companies',json={'name':'SecretAtlasUnique'}).json()['id'];pid=a.post('/api/projects',json={'name':'Test chantier','companies':[cid]}).json()['id']
    data={'name':'Chantier modifié','companies':[cid],'required':['Attestation URSSAF']}
    assert b.put(f'/api/projects/{pid}',json=data).status_code==404
    assert a.put(f'/api/projects/{pid}',json=data).status_code==200
    assert a.get('/api/projects').json()[0]['name']=='Chantier modifié'
    for c,expected in [(a,True),(b,False)]:
        r=c.get('/api/report.pdf');assert r.status_code==200
        txt=' '.join(p.extract_text() for p in PdfReader(BytesIO(r.content)).pages)
        assert ('SecretAtlasUnique' in txt)==expected

def test_secure_deposit_lifecycle():
    from fastapi.testclient import TestClient
    from app.main import app
    from test_pdf import sample_pdf
    a,b=account(),account();anon=TestClient(app)
    cid=a.post('/api/companies',json={'name':'Dépôt test'}).json()['id'];did=a.post('/api/documents',json={'company_id':cid,'kind':'Assurance','expiry':'2027-01-01'}).json()['id']
    assert b.post(f'/api/documents/{did}/deposit-link').status_code==404
    r=a.post(f'/api/documents/{did}/deposit-link');assert r.status_code==200,r.text
    token=r.json()['path'].split('#')[1];data=sample_pdf()
    assert anon.get('/depot').status_code==200
    assert anon.post('/api/public/deposit',data={'token':token},files={'file':('test.pdf',data)}).status_code==200
    assert anon.post('/api/public/deposit',data={'token':token},files={'file':('test.pdf',data)}).status_code==404
    assert a.get('/api/documents').json()[0]['has_pdf'] is False
    assert a.get('/api/storage').json()['bytes']==len(data)
    dep=a.get('/api/deposits').json()[0]['id'];assert b.get('/api/deposits').json()==[]
    assert b.get(f'/api/deposits/{dep}/pdf').status_code==404
    assert a.get(f'/api/deposits/{dep}/pdf').content==data
    assert b.post(f'/api/deposits/{dep}/accept',json={'expiry':'2028-01-01'}).status_code==404
    assert a.post(f'/api/deposits/{dep}/accept',json={'expiry':'2028-01-01','reference':'NEW'}).status_code==200
    assert a.get('/api/deposits').json()==[]
    assert a.get(f'/api/documents/{did}/pdf').content==data
    assert a.get('/api/documents').json()[0]['expiry']=='2028-01-01'
    assert a.get('/api/storage').json()['bytes']==len(data)

def test_deposit_revoke_and_document_delete():
    from fastapi.testclient import TestClient
    from app.main import app
    from test_pdf import sample_pdf
    a=account();cid=a.post('/api/companies',json={'name':'Test'}).json()['id'];did=a.post('/api/documents',json={'company_id':cid,'kind':'Assurance','expiry':'2027-01-01'}).json()['id']
    def issue():return a.post(f'/api/documents/{did}/deposit-link').json()['path'].split('#')[1]
    token=issue();dep=a.get('/api/deposits').json()[0]['id'];assert a.delete(f'/api/deposits/{dep}').status_code==200
    anon=TestClient(app);files={'file':('test.pdf',sample_pdf())}
    assert anon.post('/api/public/deposit',data={'token':token},files=files).status_code==404
    token=issue();assert a.delete(f'/api/documents/{did}').status_code==200
    assert anon.post('/api/public/deposit',data={'token':token},files=files).status_code==404

def test_custom_reminder_and_project_assistant():
    a,b=account(),account();cid=a.post('/api/companies',json={'name':'Atlas confidentiel'}).json()['id'];did=a.post('/api/documents',json={'company_id':cid,'kind':'Assurance','expiry':'2020-01-01'}).json()['id']
    r=a.get(f'/api/reminders/{did}/draft');assert r.status_code==200 and '01/01/2020' in r.json()['body']
    assert a.put('/api/reminder-settings',json={'signature':'Mon équipe','overdue':'Relance : {document} - {date}\n{signature}'}).status_code==200
    assert a.get(f'/api/reminders/{did}/draft').json()['body']=='Relance : Assurance - 01/01/2020\nMon équipe'
    assert b.get(f'/api/reminders/{did}/draft').status_code==404
    assert 'Mon équipe' not in b.get('/api/reminder-settings').json()['signature']
    assert a.post('/api/projects',json={'name':'Chantier confidentiel','companies':[cid],'required':['Assurance']}).status_code==200
    assert 'Atlas confidentiel' in a.post('/api/assistant',json={'question':'Quels chantiers ont des documents manquants ?'}).json()['message']
    assert 'Atlas confidentiel' not in b.post('/api/assistant',json={'question':'Quels chantiers ont des documents manquants ?'}).json()['message']

def test_generative_request_minimizes_data(monkeypatch):
    from app import rc10
    a=account();cid=a.post('/api/companies',json={'name':'Atlas démo','email':'private@example.com'}).json()['id'];a.post('/api/documents',json={'company_id':cid,'kind':'Assurance','expiry':'2027-01-01','reference':'PRIVATE-REF','notes':'PRIVATE-NOTES'})
    monkeypatch.setenv('OPENAI_API_KEY','test-only');monkeypatch.setenv('OPERA_AI_MODEL','test-model');calls=[]
    class MockResponse:
        def raise_for_status(self):pass
        def json(self):return {'choices':[{'message':{'content':'Synthèse simulée'}}]}
    def mock(url,**kwargs):calls.append(kwargs['json']);return MockResponse()
    monkeypatch.setattr(rc10.httpx,'post',mock)
    assert a.post('/api/assistant/generative',json={'question':'Résumé'}).status_code==403
    assert calls==[]
    r=a.post('/api/assistant/generative',json={'question':'Résumé','consent':True});assert r.status_code==200 and r.json()['message']=='Synthèse simulée'
    sent=str(calls[0]);assert 'Atlas démo' in sent and all(x not in sent for x in ('private@example.com','PRIVATE-REF','PRIVATE-NOTES'))

def test_essential_feature_rights():
    from app.main import SessionLocal,User,Billing,BillingPlan
    from sqlalchemy import select
    a=account();email=a.get('/api/me').json()['email'];cid=a.post('/api/companies',json={'name':'Atlas test'}).json()['id'];did=a.post('/api/documents',json={'company_id':cid,'kind':'Assurance','expiry':'2027-01-01'}).json()['id']
    with SessionLocal() as s:
        u=s.scalar(select(User).where(User.email==email));s.add(Billing(org_id=u.org_id,customer_id='cus_essential_rights',state='active'));s.add(BillingPlan(org_id=u.org_id,plan='essential_monthly'));s.commit()
    assert a.get('/api/capabilities').json()['tier']=='essential'
    assert a.post('/api/projects',json={'name':'Chantier'}).status_code==403
    assert a.post(f'/api/documents/{did}/deposit-link').status_code==403
    assert a.post('/api/assistant/generative',json={'question':'Résumé','consent':True}).status_code==403
    assert a.get('/api/report.pdf').status_code==200
