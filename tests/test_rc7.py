import hashlib,hmac,json,time
from fastapi.testclient import TestClient
from app.main import app,_attempts
from app import integrations
from test_v2 import register

def test_six_prices_and_webhook(monkeypatch):
    for k,v in {'STRIPE_SECRET_KEY':'sk_test_example','STRIPE_WEBHOOK_SECRET':'whsec_example','PUBLIC_URL':'https://example.com'}.items():monkeypatch.setenv(k,v)
    actual={v[0]:v for v in integrations.PLANS.values()}; selected={}; customers=[]
    def stripe(path,data=None):
        if path.startswith('prices/'):
            p,amount,interval=actual[path.split('/')[1]]
            return {'id':p,'livemode':False,'active':True,'currency':'eur','unit_amount':amount,'recurring':{'interval':interval,'interval_count':1}}
        if path=='customers':
            c='cus_rc7_'+str(len(customers));customers.append(c);return {'id':c}
        if path.startswith('checkout/sessions?') or path.startswith('subscriptions?'):return {'data':[]}
        if path=='checkout/sessions':
            selected[data['customer']]=data['line_items[0][price]'];return {'url':'https://checkout.stripe.com/test'}
        if path.startswith('subscriptions/'):
            c=path.split('/')[1];return {'id':c,'customer':c,'status':'active','livemode':False,'items':{'data':[{'price':{'id':selected[c]},'quantity':1}]}}
        raise AssertionError(path)
    monkeypatch.setattr(integrations,'stripe_request',stripe)
    for plan,(price,_,_) in integrations.PLANS.items():
        _attempts.clear();a=TestClient(app);register(a)
        assert a.post('/api/billing/checkout?plan=invalid').status_code==422
        assert a.post('/api/billing/checkout?plan='+plan).status_code==200
        c=customers[-1];assert selected[c]==price
        body=json.dumps({'type':'customer.subscription.updated','livemode':False,'data':{'object':{'id':c,'customer':c}}}).encode();stamp=int(time.time());sig=hmac.new(b'whsec_example',str(stamp).encode()+b'.'+body,hashlib.sha256).hexdigest()
        assert a.post('/webhooks/stripe',content=body,headers={'stripe-signature':f't={stamp},v1={sig}'}).status_code==200
        assert a.get('/api/capabilities').json()['plan']==plan
        assert a.post('/api/billing/checkout?plan='+plan).status_code==409

def test_reject_mismatched_price(monkeypatch):
    for k,v in {'STRIPE_SECRET_KEY':'sk_test_example','STRIPE_WEBHOOK_SECRET':'whsec_example','PUBLIC_URL':'https://example.com'}.items():monkeypatch.setenv(k,v)
    a=TestClient(app);register(a)
    monkeypatch.setattr(integrations,'stripe_request',lambda *args: {'id':integrations.PLANS['business_annual'][0],'active':True,'livemode':False,'currency':'eur','unit_amount':1,'recurring':{'interval':'year','interval_count':1}})
    assert a.post('/api/billing/checkout?plan=business_annual').status_code==502
