from fastapi.testclient import TestClient
from app.main import app,SessionLocal,Billing,User
from app import integrations
from sqlalchemy import select
from test_v2 import register

def test_direct_billing(monkeypatch):
    for k,v in {'STRIPE_SECRET_KEY':'sk_test_example','STRIPE_WEBHOOK_SECRET':'whsec_example','PUBLIC_URL':'https://example.com'}.items():monkeypatch.setenv(k,v)
    a=TestClient(app);register(a)
    email=a.get('/api/me').json()['email']
    with SessionLocal() as db:
        u=db.scalar(select(User).where(User.email==email));db.add(Billing(org_id=u.org_id,customer_id='cus_final',subscription_id='sub_final',state='active'));db.commit()
    current={'id':'sub_final','customer':'cus_final','livemode':False,'status':'active','cancel_at_period_end':False,'current_period_end':2000000000,'items':{'data':[{'id':'si_final','quantity':1,'price':{'id':integrations.PLANS['essential_monthly'][0]}}]}}
    def stripe(path,data=None):
        if path.startswith('prices/'):
            p,amount,interval=integrations.PLANS['professional_monthly'];return {'id':p,'unit_amount':amount,'currency':'eur','active':True,'livemode':False,'recurring':{'interval':interval,'interval_count':1}}
        assert path=='subscriptions/sub_final'
        if data and 'cancel_at_period_end' in data:current['cancel_at_period_end']=data['cancel_at_period_end']=='true'
        if data and 'items[0][price]' in data:current['items']['data'][0]['price']['id']=data['items[0][price]']
        return current
    monkeypatch.setattr(integrations,'stripe_request',stripe)
    assert a.post('/api/billing/manage?action=cancel').json()['cancel_pending'] is True
    assert a.get('/api/capabilities').json()['cancel_pending'] is True
    assert a.post('/api/billing/manage?action=resume').json()['cancel_pending'] is False
    assert a.post('/api/billing/manage?action=change&plan=professional_monthly').status_code==200
    assert a.get('/api/capabilities').json()['tier']=='professional'
    current['customer']='cus_other'
    assert a.post('/api/billing/manage?action=sync').status_code==409
