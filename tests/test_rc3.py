import hashlib,hmac,time,json
from fastapi.testclient import TestClient
from app.main import app
from app import integrations
from test_v2 import register

def test_stripe_signature():
    body=b'{"id":"evt_demo"}';stamp=int(time.time());secret='test_secret'
    sig=hmac.new(secret.encode(),str(stamp).encode()+b'.'+body,hashlib.sha256).hexdigest()
    assert integrations.valid_stripe_signature(body,f't={stamp},v1={sig}',secret)
    assert not integrations.valid_stripe_signature(body+b' ',f't={stamp},v1={sig}',secret)
    assert not integrations.valid_stripe_signature(body,f't={stamp},v1={sig}',secret,now=stamp+301)

def test_optional_services_and_billing(monkeypatch):
    a=TestClient(app);register(a)
    assert a.post('/api/billing/checkout').status_code==503
    assert a.post('/webhooks/stripe',content=b'{}').status_code==400
    for k,v in {'STRIPE_SECRET_KEY':'sk_test_example','STRIPE_PRICE_ID':'price_example','STRIPE_WEBHOOK_SECRET':'whsec_example','PUBLIC_URL':'https://example.com'}.items():monkeypatch.setenv(k,v)
    def stripe(path,data=None):
        if path.startswith('prices/'):return {'id':path.split('/')[1],'livemode':False,'active':True,'currency':'eur','unit_amount':3900,'recurring':{'interval':'month','interval_count':1}}
        if path.startswith('checkout/sessions?') or path.startswith('subscriptions?'):return {'data':[]}
        if path=='customers':return {'id':'cus_test_rc3'}
        if path=='checkout/sessions':return {'url':'https://checkout.stripe.com/test'}
        if path=='subscriptions/sub_test':return {'id':'sub_test','customer':'cus_test_rc3','status':'active','items':{'data':[{'price':{'id':integrations.PLANS['essential_monthly'][0]}}]}}
        raise AssertionError(path)
    monkeypatch.setattr(integrations,'stripe_request',stripe)
    assert a.post('/api/billing/checkout').json()['url'].startswith('https://checkout.stripe.com')
    body=json.dumps({'type':'customer.subscription.updated','data':{'object':{'id':'sub_test','customer':'cus_test_rc3'}}}).encode();stamp=int(time.time());sig=hmac.new(b'whsec_example',str(stamp).encode()+b'.'+body,hashlib.sha256).hexdigest()
    assert a.post('/webhooks/stripe',content=body,headers={'stripe-signature':f't={stamp},v1={sig}'}).status_code==200
    assert a.get('/api/capabilities').json()['subscription']=='active'
    assert a.post('/api/billing/checkout').status_code==409

def test_scheduled_reminders(monkeypatch):
    a,b=TestClient(app),TestClient(app);email=register(a);register(b)
    c=a.post('/api/companies',json={'name':'Fake company','email':'demo@example.com'}).json()['id']
    d=a.post('/api/documents',json={'company_id':c,'kind':'Attestation','expiry':'2020-01-01'}).json()['id']
    for k,v in {'SMTP_HOST':'smtp.example.com','SMTP_USER':'test','SMTP_PASSWORD':'test','SMTP_FROM':'sender@example.com','REMINDER_JOB_SECRET':'a'*32,'REMINDER_ALLOWED_ACCOUNTS':email}.items():monkeypatch.setenv(k,v)
    sent=[];monkeypatch.setattr(integrations,'send_mail',lambda *args:sent.append(args))
    assert b.put(f'/api/auto-reminders/{d}').status_code==503
    assert a.put(f'/api/auto-reminders/{d}').status_code==200
    assert b.get('/api/auto-reminders').json()==[]
    assert a.post('/jobs/reminders').status_code==403
    assert a.post('/jobs/reminders',headers={'x-job-secret':'a'*32}).json()['sent']==1
    assert a.post('/jobs/reminders',headers={'x-job-secret':'a'*32}).json()['sent']==0
    assert len(sent)==1
    assert a.delete(f'/api/documents/{d}').status_code==200

def test_reference_extraction():
    from app.pdf_tools import analyze_text
    assert analyze_text('Numéro de police : ABC-12345\nExpiration: 31/12/2027')['reference']=='ABC-12345'
    assert analyze_text('Numéro de police : ABC-12345\nNuméro de contrat : XYZ-67890')['reference']==''
