from datetime import timedelta
from io import BytesIO
from pypdf import PdfReader
from test_rc10 import account
from app.main import today_fr

def test_distinct_project_status_and_report():
    a=account();cid=a.post('/api/companies',json={'name':'Atlas Démo'}).json()['id']
    for kind,days in [('Décennale',-1),('URSSAF',10),('Kbis',90)]:
        assert a.post('/api/documents',json={'company_id':cid,'kind':kind,'expiry':(today_fr()+timedelta(days=days)).isoformat()}).status_code==200
    assert a.post('/api/projects',json={'name':'Résidence Démo','companies':[cid],'required':['Décennale','URSSAF','Kbis','RC Pro']}).status_code==200
    c=a.get('/api/projects').json()[0]['companies'][0]
    assert [x['status'] for x in c['pieces']]==['expired','soon','valid','missing']
    assert c['missing']==['Décennale','RC Pro']
    r=a.get('/api/report.pdf');assert r.status_code==200
    txt=' '.join(x.extract_text() for x in PdfReader(BytesIO(r.content)).pages)
    for label in ('Actions prioritaires','Manquant','Expiré','À renouveler','Hors alerte','Résidence Démo'):assert label in txt

def test_report_multiple_pages():
    a=account();cid=a.post('/api/companies',json={'name':'Entreprise Démo'}).json()['id']
    for i in range(35):
        assert a.post('/api/documents',json={'company_id':cid,'kind':f'Pièce test {i:02}','expiry':'2099-01-01'}).status_code==200
    r=a.get('/api/report.pdf');assert r.status_code==200
    pages=PdfReader(BytesIO(r.content)).pages
    assert len(pages)>1
    assert 'Pièce test 34' in ' '.join(x.extract_text() for x in pages)
