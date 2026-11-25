import io
from uuid import uuid4
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from app.main import app
from app.pdf_tools import analyze_pdf

def sample_pdf():
    writer=PdfWriter(); writer.add_blank_page(width=200,height=200)
    out=io.BytesIO(); writer.write(out); return out.getvalue()

def test_pdf_lifecycle(monkeypatch):
    monkeypatch.setenv('COOKIE_SECURE','0')
    a,b=TestClient(app),TestClient(app)
    for c in (a,b):
        assert c.post('/api/register',json={'organization':'Pilot','email':f'{uuid4()}@example.com','password':'test-password-1234'}).status_code==200
    cid=a.post('/api/companies',json={'name':'Example company'}).json()['id']
    data=sample_pdf(); fields={'company_id':str(cid),'kind':'Assurance','expiry':'2027-01-01'}
    def files(content=data): return {'file':('sample.pdf',content,'application/pdf')}
    assert a.post('/api/pdf/analyze',files=files(b'not a PDF')).status_code==422
    assert a.post('/api/pdf/analyze',files=files()).json()['text_found'] is False
    assert b.post('/api/documents/upload',data=fields,files=files()).status_code==404
    r=a.post('/api/documents/upload',data=fields,files=files()); assert r.status_code==200, r.text
    did=r.json()['id']; path=f'/api/documents/{did}/pdf'
    assert a.get('/api/documents').json()[0]['has_pdf'] is True
    assert a.get(path).content==data
    assert b.get(path).status_code==404
    assert TestClient(app).get(path).status_code==401
    assert a.delete(f'/api/documents/{did}').status_code==200
    assert a.get(path).status_code==404

def test_origin():
    c=TestClient(app)
    assert c.post('/api/logout',headers={'Origin':'https://evil.example'}).status_code==403

def test_text_suggestions():
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer=PdfWriter(); page=writer.add_blank_page(width=600,height=800)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject(); stream.set_data(b'BT /F1 12 Tf 20 700 Td (Assurance decennale - Date expiration: 31/12/2027) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    out=io.BytesIO(); writer.write(out)
    result=analyze_pdf(out.getvalue())
    assert result['kind']=='Assurance décennale'
    assert result['expiry']=='2027-12-31'
