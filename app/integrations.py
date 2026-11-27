"""Optional integrations, disabled by default. No credentials in source."""
import os, ssl, smtplib, hmac, hashlib, time
from email.message import EmailMessage
import httpx


# Sandbox price IDs only, not credentials. Never use these in live mode.
PLANS = {
    'essential_monthly': ('price_1UfoCF3xR0YeBswixwv9AcEZ', 3900, 'month'),
    'essential_annual': ('price_1UfoFh3xR0YeBswiiByGIZxW', 39000, 'year'),
    'professional_monthly': ('price_1UfoJs3xR0YeBswis9girtXv', 6900, 'month'),
    'professional_annual': ('price_1UfoMB3xR0YeBswiZBlMQHTk', 69000, 'year'),
    'business_monthly': ('price_1UfoOE3xR0YeBswijMljwBzm', 10900, 'month'),
    'business_annual': ('price_1UfoPL3xR0YeBswiMcJzZ3sp', 109000, 'year'),
}

def billing_ready():
    return os.getenv('STRIPE_SECRET_KEY','').startswith('sk_test_') and bool(os.getenv('STRIPE_WEBHOOK_SECRET')) and os.getenv('PUBLIC_URL','').startswith('https://')

def checked_price(plan):
    price_id, amount, interval = PLANS[plan]
    obj = stripe_request('prices/'+price_id)
    if (obj.get('id') != price_id or obj.get('livemode') is not False or obj.get('active') is not True or obj.get('currency') != 'eur' or obj.get('unit_amount') != amount or obj.get('recurring',{}).get('interval') != interval or obj.get('recurring',{}).get('interval_count') != 1):
        raise ValueError('Unexpected Stripe price')
    return price_id



# Reuse TLS connections between calls; credentials are passed per request.
_stripe_client = httpx.Client(timeout=httpx.Timeout(15,connect=5),limits=httpx.Limits(max_connections=10,max_keepalive_connections=5))
def stripe_request(path, data=None):
    auth=(os.environ['STRIPE_SECRET_KEY'],'')
    response=_stripe_client.post('https://api.stripe.com/v1/'+path,data=data,auth=auth) if data is not None else _stripe_client.get('https://api.stripe.com/v1/'+path,auth=auth)
    response.raise_for_status()
    return response.json()


def valid_stripe_signature(body, header, secret, now=None):
    try:
        pairs=[x.split('=',1) for x in header.split(',')]
        stamp=int(next(v for k,v in pairs if k=='t'))
        if abs((time.time() if now is None else now)-stamp)>300: return False
        expected=hmac.new(secret.encode(),str(stamp).encode()+b'.'+body,hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected,v) for k,v in pairs if k=='v1')
    except (ValueError,StopIteration): return False


def ai_config():
    # Prefer Groq explicitly when its key is present. Never silently switch providers.
    if os.getenv('GROQ_API_KEY'):
        return ('https://api.groq.com/openai/v1/chat/completions', os.environ['GROQ_API_KEY'], os.getenv('GROQ_MODEL','openai/gpt-oss-20b'))
    if os.getenv('OPENAI_API_KEY') and os.getenv('OPERA_AI_MODEL'):
        return ('https://api.openai.com/v1/chat/completions',os.environ['OPENAI_API_KEY'],os.environ['OPERA_AI_MODEL'])
    return None


def brevo_ready():
    return bool(os.getenv('BREVO_API_KEY') and os.getenv('BREVO_SENDER_EMAIL'))


def mail_ready():
    if os.getenv('BREVO_API_KEY'):
        return brevo_ready() and len(os.getenv('REMINDER_JOB_SECRET',''))>=32
    return all(os.getenv(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM','REMINDER_JOB_SECRET'))


def send_mail(recipient, subject, body):
    if os.getenv('BREVO_API_KEY'):
        if not brevo_ready(): raise ValueError('Brevo not configured')
        sender=os.environ['BREVO_SENDER_EMAIL'].strip()
        # Pilot only: never send to an actual subcontractor or an arbitrary address.
        if recipient.strip().casefold()!=sender.casefold(): raise ValueError('Pilot recipient not allowed')
        r=httpx.post('https://api.brevo.com/v3/smtp/email',headers={'api-key':os.environ['BREVO_API_KEY'],'accept':'application/json'},json={'sender':{'name':'OPERA AI','email':sender},'to':[{'email':sender}],'subject':subject,'textContent':body},timeout=15)
        r.raise_for_status()
        return
    msg=EmailMessage(); msg['From']=os.environ['SMTP_FROM']; msg['To']=recipient; msg['Subject']=subject; msg.set_content(body)
    with smtplib.SMTP_SSL(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','465')),timeout=15,context=ssl.create_default_context()) as smtp:
        smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']); smtp.send_message(msg)
