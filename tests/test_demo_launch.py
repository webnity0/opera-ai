from datetime import timedelta
from test_rc10 import account
from app.main import today_fr
from app import integrations

def test_reminder_job_auth_and_repeat(monkeypatch):
    a=account(); email=a.get('/api/me').json()['email']; secret='x'*40
    for k,v in {'BREVO_API_KEY':'fake','BREVO_SENDER_EMAIL':'sender@example.com','REMINDER_JOB_SECRET':secret,'REMINDER_ALLOWED_ACCOUNTS':email}.items(): monkeypatch.setenv(k,v)
    cid=a.post('/api/companies',json={'name':'Atlas Démo','email':'sender@example.com'}).json()['id']
    did=a.post('/api/documents',json={'company_id':cid,'kind':'Décennale','expiry':(today_fr()-timedelta(days=1)).isoformat()}).json()['id']
    assert a.put(f'/api/auto-reminders/{did}').status_code==200
    sent=[]; monkeypatch.setattr(integrations,'send_mail',lambda *args:sent.append(args))
    assert a.post('/jobs/reminders',headers={'X-Job-Secret':'wrong'}).status_code==403
    assert a.post('/jobs/reminders',headers={'X-Job-Secret':secret}).json()=={'sent':1,'failed':0}
    assert a.post('/jobs/reminders',headers={'X-Job-Secret':secret}).json()=={'sent':0,'failed':0}
    assert len(sent)==1

def test_trial_fourteen_days():
    a=account(); c=a.get('/api/capabilities').json()
    assert c['tier']=='trial'
    assert c['trial_until']==(today_fr()+timedelta(days=14)).isoformat()
