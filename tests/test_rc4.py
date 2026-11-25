from fastapi.testclient import TestClient
from app.main import app
from test_v2 import register
from test_pdf import sample_pdf
from app.pdf_isolation import process_pdf
import pytest

def test_worker():
    assert process_pdf(sample_pdf(),'validate') is True
    assert process_pdf(sample_pdf(),'analyze')['pages']==1
    with pytest.raises(ValueError): process_pdf(b'invalid','validate')

def test_export_and_storage():
    a,b=TestClient(app),TestClient(app);register(a);register(b)
    c=a.post('/api/companies',json={'name':'Private demo'}).json()['id']
    data=sample_pdf()
    assert a.post('/api/documents/upload',data={'company_id':c,'kind':'Assurance','expiry':'2027-01-01'},files={'file':('a.pdf',data,'application/pdf')}).status_code==200
    assert a.get('/api/storage').json()['bytes']==len(data)
    assert b.get('/api/storage').json()['files']==0
    assert a.get('/api/workspace-export.json').json()['companies'][0]['name']=='Private demo'
    assert b.get('/api/workspace-export.json').json()['companies']==[]
    assert TestClient(app).get('/api/workspace-export.json').status_code==401
