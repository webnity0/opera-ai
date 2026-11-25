"""Optional integrations, disabled by default. No credentials in source."""
import os, ssl, smtplib, hmac, hashlib, time
from email.message import EmailMessage
import httpx


def billing_ready():
    return all(os.getenv(k) for k in ('STRIPE_SECRET_KEY','STRIPE_PRICE_ID','STRIPE_WEBHOOK_SECRET','PUBLIC_URL'))


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
