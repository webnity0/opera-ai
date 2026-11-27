import httpx
from app import integrations
from test_rc10 import account

def test_groq_routing_and_brevo_pilot(monkeypatch):
    a=account(); calls=[]
    monkeypatch.setenv('GROQ_API_KEY','fake-groq')
    monkeypatch.setenv('OPENAI_API_KEY','fake-openai')
    monkeypatch.setenv('OPERA_AI_MODEL','gpt-4.1-mini')
    def post(url,**kwargs):
        calls.append((url,kwargs))
        req=httpx.Request('POST',url)
        return httpx.Response(200,request=req,json={'choices':[{'message':{'content':'Synthèse fictive'}}]})
    monkeypatch.setattr(httpx,'post',post)
    assert a.get('/api/capabilities').json()['generative']
    assert a.post('/api/assistant/generative',json={'question':'Résumé','consent':True}).json()['message']=='Synthèse fictive'
    assert calls[-1][0]=='https://api.groq.com/openai/v1/chat/completions'
    assert calls[-1][1]['json']['model']=='openai/gpt-oss-20b'
    monkeypatch.setenv('BREVO_API_KEY','fake-brevo'); monkeypatch.setenv('BREVO_SENDER_EMAIL','sender@example.com')
    import pytest
    with pytest.raises(ValueError): integrations.send_mail('other@example.com','Test','Test')
    integrations.send_mail('sender@example.com','Test','Test')
    assert calls[-1][0]=='https://api.brevo.com/v3/smtp/email'
    assert calls[-1][1]['json']['to']==[{'email':'sender@example.com'}]
    assert a.post('/api/auto-reminders/test').status_code==403
