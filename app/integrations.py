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



def stripe_request(path, data=None):
    key=os.environ['STRIPE_SECRET_KEY']
    with httpx.Client(timeout=15, auth=(key,'')) as client:
        response=client.post('https://api.stripe.com/v1/'+path,data=data) if data is not None else client.get('https://api.stripe.com/v1/'+path)
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


def mail_ready():
    return all(os.getenv(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM','REMINDER_JOB_SECRET'))


def send_mail(recipient, subject, body):
    msg=EmailMessage(); msg['From']=os.environ['SMTP_FROM']; msg['To']=recipient; msg['Subject']=subject; msg.set_content(body)
    with smtplib.SMTP_SSL(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','465')),timeout=15,context=ssl.create_default_context()) as smtp:
        smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']); smtp.send_message(msg)
