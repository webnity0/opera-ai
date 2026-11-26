"""OPERA AI beta: tenant-isolated document metadata. PDF storage and assisted text extraction."""
import csv
import io
import os
import secrets
import hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

def today_fr(): return datetime.now(ZoneInfo("Europe/Paris")).date()
from .pdf_tools import MAX_BYTES
from .pdf_isolation import process_pdf
from sqlalchemy.exc import IntegrityError
from threading import Lock
from time import monotonic
from threading import BoundedSemaphore
from collections import deque
from urllib.parse import quote
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Integer, ForeignKey, Date, DateTime, LargeBinary, select, func, delete, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./opera_beta.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
if DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
SECRET_KEY = os.getenv('SECRET_KEY', '')
if os.getenv('RENDER') and (len(SECRET_KEY) < 48 or DATABASE_URL.startswith('sqlite:') or os.getenv('COOKIE_SECURE','1') != '1'):
    raise RuntimeError('Production: PostgreSQL, SECRET_KEY >= 48 et COOKIE_SECURE=1 requis')
if not SECRET_KEY:
    # Ephemeral secret: safe for local testing, but sessions expire on server restart.
    SECRET_KEY = secrets.token_urlsafe(48)
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite:') else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
hasher = PasswordHasher()

def verify_password(password, encoded):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False
signer = URLSafeTimedSerializer(SECRET_KEY, salt='opera-session-v1')

class Base(DeclarativeBase): pass
class Organization(Base):
    __tablename__ = 'organizations'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
class Company(Base):
    __tablename__ = 'companies'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    name: Mapped[str] = mapped_column(String(160))
    contact: Mapped[str] = mapped_column(String(160), default='')
    email: Mapped[str] = mapped_column(String(255), default='')
class Document(Base):
    __tablename__ = 'documents'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'))
    kind: Mapped[str] = mapped_column(String(150))
    reference: Mapped[str] = mapped_column(String(200), default='')
    expiry: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(String(500), default='')
class Attachment(Base):
    __tablename__ = 'attachments'
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    filename: Mapped[str] = mapped_column(String(180))
    data: Mapped[bytes] = mapped_column(LargeBinary)
class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class LoginSession(Base):
    __tablename__ = 'login_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class Reminder(Base):
    __tablename__ = 'reminders'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(engine)  # Beta only; production migrations should use Alembic.
app = FastAPI(title='OPERA AI', version='2.0-rc9', docs_url=None, redoc_url=None, openapi_url=None)

_pdf_requests = BoundedSemaphore(2)

@app.middleware('http')
async def security_headers(request: Request, call_next):
    if request.method in ('POST','PUT','PATCH','DELETE'):
        length = request.headers.get('content-length')
        if length is not None and not length.isdigit():
            return Response(status_code=411)
        limit = MAX_BYTES + 65536 if (request.url.path in ('/api/pdf/analyze','/api/documents/upload') or (request.url.path.startswith('/api/documents/') and request.url.path.endswith('/renew'))) else 65536
        if length is not None and int(length) > limit: return Response(status_code=413)
        # Enforce actual streamed body length too, before multipart parsing.
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > limit: return Response(status_code=413)
        request._body = bytes(chunks)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if os.getenv('RENDER'): response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api/') else 'no-cache'
    return response

def db():
    with SessionLocal() as session:
        yield session

def me(request: Request, session: Session = Depends(db)) -> User:
    token = request.cookies.get('opera_session')
    if not token:
        raise HTTPException(401, 'Connexion requise')
    entry = session.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if not entry or entry.expires_at.replace(tzinfo=None) <= datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(401, 'Session expirée')
    user = session.get(User, entry.user_id)
    if not user:
        raise HTTPException(401, 'Compte introuvable')
    return user

def access_info(user, session):
    b=session.get(Billing,user.org_id)
    plan=session.get(BillingPlan,user.org_id)
    detail=session.get(BillingDetails,user.org_id)
    if b and plan and plan.plan in integrations.PLANS and b.state in ('active','trialing'):
        expired=False
        if detail and detail.cancel_pending and detail.ends_at:
            expired=datetime.fromisoformat(detail.ends_at)<=datetime.now(timezone.utc)
        if not expired: return plan.plan.split('_')[0],None
    trial=session.get(Trial,user.org_id)
    # Legacy pilot accounts receive the same fixed 14-day period, based on original registration.
    if not trial:
        created=session.scalar(select(func.min(Audit.created_at)).where(Audit.org_id==user.org_id))
        end=(created.date() if created else today_fr())+timedelta(days=14)
    else: end=trial.ends_at
    return ('trial' if today_fr()<end else 'expired'),end.isoformat()

LIMITS={'trial':(15,100),'essential':(15,100),'professional':(50,300),'business':(150,1000),'expired':(0,0)}

def write_access(user:User=Depends(me),session:Session=Depends(db)):
    tier,_=access_info(user,session)
    if tier=='expired': raise HTTPException(403,'Essai terminé : choisissez une formule. Lecture et export restent disponibles.')
    return tier

def check_quota(user,session,table,extra=1):
    if engine.dialect.name=='postgresql': session.execute(text('SELECT pg_advisory_xact_lock(726384, :org)'),{'org':user.org_id})
    tier,_=access_info(user,session)
    maximum=LIMITS[tier][0 if table is Company else 1]
    count=session.scalar(select(func.count()).select_from(table).where(table.org_id==user.org_id))
    if count+extra>maximum: raise HTTPException(409,'Limite de votre formule atteinte.')

def csrf_guard(request: Request):
    if request.method in ('POST','PUT','PATCH','DELETE'):
        if request.headers.get('sec-fetch-site') == 'cross-site': raise HTTPException(403, 'Origine refusée')
        origin = request.headers.get('origin')
        if origin:
            from urllib.parse import urlparse
            target = urlparse(str(request.base_url))
            source = urlparse(origin)
            if source.netloc != target.netloc or source.scheme not in ('http', 'https') or (os.getenv('COOKIE_SECURE','1') == '1' and source.scheme != 'https'):
                raise HTTPException(403, 'Origine refusée')

_attempts = {}
_attempt_lock = Lock()
def rate_limit(request, action, maximum):
    now = monotonic()
    key = (request.client.host if request.client else 'unknown', action)
    with _attempt_lock:
        for k in list(_attempts):
            if not _attempts[k] or _attempts[k][-1] < now - 600: del _attempts[k]
        if key not in _attempts and len(_attempts) >= 5000: raise HTTPException(429, 'Réessayez plus tard')
        q = _attempts.setdefault(key, deque())
        while q and q[0] < now - 600: q.popleft()
        if len(q) >= maximum: raise HTTPException(429, 'Réessayez plus tard')
        q.append(now)

def log(session, user, action):
    session.add(Audit(org_id=user.org_id, user_id=user.id, action=action))

class RegisterIn(BaseModel):
    organization: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=12, max_length=128)
class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=128)
class CompanyIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    contact: str = Field(default='', max_length=160)
    email: str = Field(default='', max_length=255)
class DocIn(BaseModel):
    company_id: int
    kind: str = Field(min_length=2, max_length=150)
    expiry: date
    reference: str = Field(default='', max_length=200)
    notes: str = Field(default='', max_length=500)

def set_cookie(response, user, session):
    token = secrets.token_urlsafe(32)
    session.execute(delete(LoginSession).where(LoginSession.user_id == user.id, LoginSession.expires_at < datetime.now(timezone.utc).replace(tzinfo=None)))
    session.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires_at=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(days=7)))
    session.commit()
    response.set_cookie('opera_session', token, max_age=604800, httponly=True, secure=os.getenv('COOKIE_SECURE','1') == '1', samesite='lax', path='/')

@app.get('/')
def home():
    return FileResponse(Path(__file__).parent / 'static' / 'index.html')

@app.get('/health')
def health():
    try:
        with engine.connect() as connection: connection.execute(text('SELECT 1'))
    except Exception:
        raise HTTPException(503, 'Base indisponible')
    return {'status': 'ok', 'version': '2.0-rc8'}

@app.post('/api/register', dependencies=[Depends(csrf_guard)])
def register(payload: RegisterIn, response: Response, request: Request, session: Session = Depends(db)):
    rate_limit(request, 'register', 10)
    email = payload.email.strip().lower()
    if len(payload.organization.strip()) < 2 or email.count('@') != 1 or any(c.isspace() for c in email) or not email.split('@')[0] or '.' not in email.split('@')[-1]:
        raise HTTPException(422, 'E-mail invalide')
    if session.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, 'Adresse déjà utilisée')
    org = Organization(name=payload.organization.strip())
    session.add(org); session.flush()
    user = User(org_id=org.id, email=email, password_hash=hasher.hash(payload.password))
    session.add(user)
    try: session.flush()
    except IntegrityError:
        session.rollback(); raise HTTPException(409, 'Adresse déjà utilisée')
    session.add(Trial(org_id=org.id,ends_at=today_fr()+timedelta(days=14)))
    log(session, user, 'Création du compte')
    session.commit(); set_cookie(response, user, session)
    return {'email': user.email, 'organization': org.name}

@app.post('/api/login', dependencies=[Depends(csrf_guard)])
def login(payload: LoginIn, response: Response, request: Request, session: Session = Depends(db)):
    rate_limit(request, 'login', 20)
    user = session.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, 'Identifiants incorrects')
    set_cookie(response, user, session)
    return {'email': user.email}

@app.post('/api/logout', dependencies=[Depends(csrf_guard)])
def logout(response: Response, request: Request, session: Session = Depends(db)):
    token = request.cookies.get('opera_session')
    if token:
        session.execute(delete(LoginSession).where(LoginSession.token_hash == hashlib.sha256(token.encode()).hexdigest()))
        session.commit()
    response.delete_cookie('opera_session', path='/')
    return {'ok': True}

@app.get('/api/me')
def profile(user: User = Depends(me), session: Session = Depends(db)):
    org = session.get(Organization, user.org_id)
    return {'email': user.email, 'organization': org.name}

@app.get('/api/companies')
def companies(user: User = Depends(me), session: Session = Depends(db)):
    return [{'id': c.id, 'name': c.name, 'contact': c.contact, 'email': c.email} for c in session.scalars(select(Company).where(Company.org_id == user.org_id).order_by(Company.name))]

@app.post('/api/companies', dependencies=[Depends(csrf_guard),Depends(write_access)])
def add_company(payload: CompanyIn, user: User = Depends(me), session: Session = Depends(db)):
    check_quota(user,session,Company)
    c = Company(org_id=user.org_id, **payload.model_dump())
    session.add(c); log(session,user,'Entreprise créée'); session.commit()
    return {'id': c.id}

@app.delete('/api/companies/{company_id}', dependencies=[Depends(csrf_guard)])
def delete_company(company_id: int, user: User = Depends(me), session: Session = Depends(db)):
    c = session.scalar(select(Company).where(Company.id == company_id, Company.org_id == user.org_id))
    if not c: raise HTTPException(404, 'Entreprise introuvable')
    if session.scalar(select(Document.id).where(Document.org_id == user.org_id, Document.company_id == company_id)):
        raise HTTPException(409, 'Supprimez d’abord les documents associés')
    session.delete(c); log(session,user,'Entreprise supprimée'); session.commit()
    return {'ok': True}

def status(expiry):
    days = (date.fromisoformat(expiry) - today_fr()).days
    return "expired" if days < 0 else "soon" if days <= 30 else "valid"

def doc_dict(d, company):
    days = (d.expiry - today_fr()).days
    return {'id': d.id, 'company_id': d.company_id, 'company': company, 'kind': d.kind, 'expiry': d.expiry.isoformat(), 'reference': d.reference, 'notes': d.notes, 'days': days, 'status': status(d.expiry.isoformat())}

@app.get('/api/documents')
def documents(user: User = Depends(me), session: Session = Depends(db)):
    rows = session.execute(select(Document, Company.name).join(Company, Document.company_id == Company.id).where(Document.org_id == user.org_id, Company.org_id == user.org_id).order_by(Document.expiry)).all()
    attached = set(session.scalars(select(Attachment.document_id).where(Attachment.org_id == user.org_id)))
    return [dict(doc_dict(d, name), has_pdf=d.id in attached) for d,name in rows]

@app.post('/api/documents', dependencies=[Depends(csrf_guard),Depends(write_access)])
def add_doc(payload: DocIn, user: User = Depends(me), session: Session = Depends(db)):
    c = session.scalar(select(Company).where(Company.id == payload.company_id, Company.org_id == user.org_id))
    if not c: raise HTTPException(404, 'Entreprise introuvable')
    check_quota(user,session,Document)
    d = Document(org_id=user.org_id, **payload.model_dump())
    session.add(d); log(session,user,'Document ajouté'); session.commit()
    return {'id': d.id}

@app.put('/api/documents/{document_id}', dependencies=[Depends(csrf_guard),Depends(write_access)])
def edit_doc(document_id: int, payload: DocIn, user: User = Depends(me), session: Session = Depends(db)):
    d = session.scalar(select(Document).where(Document.id == document_id, Document.org_id == user.org_id))
    c = session.scalar(select(Company).where(Company.id == payload.company_id, Company.org_id == user.org_id))
    if not d or not c: raise HTTPException(404, 'Document ou entreprise introuvable')
    if d.company_id != payload.company_id or d.expiry != payload.expiry or d.kind != payload.kind:
        session.execute(delete(AutoReminder).where(AutoReminder.document_id == d.id, AutoReminder.org_id == user.org_id))
    for key,value in payload.model_dump().items(): setattr(d,key,value)
    log(session,user,'Document modifié'); session.commit()
    return {'ok': True}

@app.delete('/api/documents/{document_id}', dependencies=[Depends(csrf_guard)])
def delete_doc(document_id: int, user: User = Depends(me), session: Session = Depends(db)):
    d = session.scalar(select(Document).where(Document.id == document_id, Document.org_id == user.org_id))
    if not d: raise HTTPException(404, 'Document introuvable')
    session.execute(delete(Attachment).where(Attachment.document_id == d.id, Attachment.org_id == user.org_id))
    session.execute(delete(Reminder).where(Reminder.document_id == d.id, Reminder.org_id == user.org_id))
    session.execute(delete(AutoReminder).where(AutoReminder.document_id == d.id, AutoReminder.org_id == user.org_id))
    session.delete(d); log(session,user,'Document supprimé'); session.commit()
    return {'ok': True}

@app.get('/api/dashboard')
def dashboard(user: User = Depends(me), session: Session = Depends(db)):
    docs = session.scalars(select(Document).where(Document.org_id == user.org_id)).all()
    return {'companies': session.scalar(select(func.count()).select_from(Company).where(Company.org_id == user.org_id)), 'documents': len(docs), 'expired': sum(d.expiry < today_fr() for d in docs), 'soon': sum(today_fr() <= d.expiry <= today_fr()+timedelta(days=30) for d in docs)}

@app.get('/api/audit')
def audit(user: User = Depends(me), session: Session = Depends(db)):
    return [{'action':a.action,'at':a.created_at.replace(tzinfo=timezone.utc).isoformat()} for a in session.scalars(select(Audit).where(Audit.org_id == user.org_id).order_by(Audit.id.desc()).limit(30))]

@app.get('/api/export.csv')
def export_csv(user: User = Depends(me), session: Session = Depends(db)):
    rows = documents(user,session)
    buf = io.StringIO(); writer = csv.writer(buf)
    writer.writerow(['Entreprise','Document','Référence','Échéance','Jours restants','Statut','Notes'])
    def safe_cell(value):
        if isinstance(value, str) and (value.startswith(('\t', '\r', '\n')) or value.lstrip().startswith(('=', '+', '-', '@'))):
            return "'" + value
        return value
    for d in rows: writer.writerow([safe_cell(d[k]) for k in ('company','kind','reference','expiry','days','status','notes')])
    return Response('\ufeff'+buf.getvalue(), media_type='text/csv; charset=utf-8', headers={'Content-Disposition':'attachment; filename="opera-export.csv"'})


def checked_pdf(data,mode):
    if not _pdf_requests.acquire(blocking=False): raise HTTPException(503,'Analyse occupée, réessayez dans un instant')
    try:
        try: return process_pdf(data,mode)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
        except RuntimeError as exc: raise HTTPException(503,str(exc)) from exc
    finally: _pdf_requests.release()

@app.post('/api/pdf/analyze', dependencies=[Depends(csrf_guard),Depends(write_access)])
def pdf_analysis(request: Request, file: UploadFile = File(...), user: User = Depends(me)):
    rate_limit(request, 'pdf', 20)
    return checked_pdf(file.file.read(MAX_BYTES+1),'analyze')

@app.post('/api/documents/upload', dependencies=[Depends(csrf_guard),Depends(write_access)])
def upload_document(request: Request, file: UploadFile = File(...), company_id: int = Form(...), kind: str = Form(..., min_length=2,max_length=150), expiry: date = Form(...), reference: str = Form('',max_length=200), notes: str = Form('',max_length=500), user: User = Depends(me), session: Session = Depends(db)):
    c = session.scalar(select(Company).where(Company.id == company_id, Company.org_id == user.org_id))
    if not c: raise HTTPException(404, 'Entreprise introuvable')
    rate_limit(request,'pdf',20)
    data = file.file.read(MAX_BYTES+1)
    checked_pdf(data,'validate')
    if engine.dialect.name == 'postgresql':
        session.execute(text('SELECT pg_advisory_xact_lock(726381)'))
    used = session.scalar(select(func.coalesce(func.sum(func.length(Attachment.data)),0)).where(Attachment.org_id == user.org_id))
    total = session.scalar(select(func.coalesce(func.sum(func.length(Attachment.data)),0)))
    if used + len(data) > 50*1024*1024 or total + len(data) > 400*1024*1024:
        raise HTTPException(409, 'Quota de stockage pilote atteint')
    count = session.scalar(select(func.count()).select_from(Attachment).where(Attachment.org_id == user.org_id))
    if count >= 100: raise HTTPException(409, 'Limite pilote : 100 PDF par organisation')
    check_quota(user,session,Document)
    d = Document(org_id=user.org_id,company_id=company_id,kind=kind,expiry=expiry,reference=reference,notes=notes)
    session.add(d); session.flush()
    filename = (file.filename or 'document.pdf').replace('\\','/').split('/')[-1][:170]
    if not filename.lower().endswith('.pdf'): filename += '.pdf'
    session.add(Attachment(document_id=d.id,org_id=user.org_id,filename=filename,data=data))
    log(session,user,'PDF enregistré'); session.commit()
    return {'id':d.id}

@app.get('/api/documents/{document_id}/pdf')
def download_pdf(document_id: int, user: User = Depends(me), session: Session = Depends(db)):
    a = session.scalar(select(Attachment).join(Document, Attachment.document_id == Document.id).where(Attachment.document_id == document_id, Attachment.org_id == user.org_id, Document.org_id == user.org_id))
    if not a: raise HTTPException(404, 'PDF introuvable')
    return Response(a.data, media_type='application/octet-stream', headers={'Content-Disposition':"attachment; filename=\"document.pdf\"; filename*=UTF-8''"+quote(a.filename,safe='')})


class SettingsIn(BaseModel):
    organization: str = Field(min_length=2,max_length=150)
class PasswordIn(BaseModel):
    current: str = Field(max_length=128)
    new: str = Field(min_length=12,max_length=128)

@app.put('/api/settings', dependencies=[Depends(csrf_guard)])
def settings(payload: SettingsIn, user: User = Depends(me), session: Session = Depends(db)):
    org = session.get(Organization, user.org_id)
    if len(payload.organization.strip()) < 2: raise HTTPException(422,'Nom invalide')
    org.name = payload.organization.strip()
    log(session,user,'Paramètres modifiés'); session.commit()
    return {'ok':True}

@app.post('/api/password', dependencies=[Depends(csrf_guard)])
def password(payload: PasswordIn, request: Request, response: Response, user: User = Depends(me), session: Session = Depends(db)):
    rate_limit(request,'password',5)
    if not verify_password(payload.current,user.password_hash): raise HTTPException(400,'Mot de passe actuel incorrect')
    user.password_hash = hasher.hash(payload.new)
    session.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    log(session,user,'Mot de passe modifié'); session.commit()
    response.delete_cookie('opera_session',path='/')
    return {'ok':True}

@app.put('/api/companies/{company_id}', dependencies=[Depends(csrf_guard),Depends(write_access)])
def edit_company(company_id:int,payload:CompanyIn,user:User=Depends(me),session:Session=Depends(db)):
    c=session.scalar(select(Company).where(Company.id==company_id,Company.org_id==user.org_id))
    if not c: raise HTTPException(404,'Entreprise introuvable')
    if c.email != payload.email:
        session.execute(delete(AutoReminder).where(AutoReminder.org_id==user.org_id, AutoReminder.document_id.in_(select(Document.id).where(Document.company_id==c.id,Document.org_id==user.org_id))))
    for k,v in payload.model_dump().items(): setattr(c,k,v)
    log(session,user,'Entreprise modifiée'); session.commit()
    return {'ok':True}

@app.get('/api/reminders')
def reminders(user:User=Depends(me),session:Session=Depends(db)):
    rows=session.execute(select(Reminder.document_id,func.max(Reminder.created_at)).where(Reminder.org_id==user.org_id).group_by(Reminder.document_id)).all()
    return {str(i):dt.replace(tzinfo=timezone.utc).isoformat() for i,dt in rows}

@app.post('/api/reminders/{document_id}', dependencies=[Depends(csrf_guard),Depends(write_access)])
def reminder(document_id:int,user:User=Depends(me),session:Session=Depends(db)):
    d=session.scalar(select(Document).where(Document.id==document_id,Document.org_id==user.org_id))
    if not d: raise HTTPException(404,'Document introuvable')
    session.add(Reminder(org_id=user.org_id,document_id=d.id))
    log(session,user,'Relance déclarée envoyée'); session.commit()
    return {'ok':True}

# Optional integrations. The pilot never activates real payments by default.
from . import integrations as integrations
import hmac
import json
from fastapi import Header

class Billing(Base):
    __tablename__='billing_accounts'
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'),primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(100),unique=True)
    subscription_id: Mapped[str] = mapped_column(String(100),default='')
    state: Mapped[str] = mapped_column(String(30),default='none')

class BillingPlan(Base):
    __tablename__='billing_plans'
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'),primary_key=True)
    plan: Mapped[str] = mapped_column(String(40),default='')

class BillingDetails(Base):
    __tablename__='billing_details'
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'),primary_key=True)
    ends_at: Mapped[str] = mapped_column(String(40),default='')
    cancel_pending: Mapped[int] = mapped_column(Integer,default=0)

class Trial(Base):
    __tablename__='workspace_trials'
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'),primary_key=True)
    ends_at: Mapped[date] = mapped_column(Date)

class AutoReminder(Base):
    __tablename__='auto_reminders'
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id',ondelete='CASCADE'),primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'),index=True)
    last_expiry: Mapped[str] = mapped_column(String(10),default='')
    last_stage: Mapped[int] = mapped_column(Integer,default=0)

Base.metadata.create_all(engine)

@app.get('/api/capabilities')
def capabilities(user:User=Depends(me),session:Session=Depends(db)):
    from .ocr_tools import available
    b=session.get(Billing,user.org_id)
    plan=session.get(BillingPlan,user.org_id)
    details=session.get(BillingDetails,user.org_id)
    tier,trial_until=access_info(user,session)
    return {'tier':tier,'company_limit':LIMITS[tier][0],'document_limit':LIMITS[tier][1],'cancel_pending':bool(details and details.cancel_pending),'ends_at':details.ends_at if details else '', 'trial_until':trial_until or '', 'plan':plan.plan if plan and b and b.state in ('active','trialing') else '', 'ocr':available(),'email':integrations.mail_ready() and user.email in {x.strip().lower() for x in os.getenv('REMINDER_ALLOWED_ACCOUNTS','').split(',')},'billing':integrations.billing_ready(),'subscription':b.state if b else 'none','billing_test':True}

@app.post('/api/billing/checkout',dependencies=[Depends(csrf_guard)])
def checkout(request:Request,plan:str='essential_monthly',user:User=Depends(me),session:Session=Depends(db)):
    rate_limit(request,'checkout',5)
    if not integrations.billing_ready(): raise HTTPException(503,'Paiement non configuré')
    # Real charges must not be enabled accidentally during pilot testing.
    if not os.getenv('STRIPE_SECRET_KEY','').startswith('sk_test_'): raise HTTPException(403,'Paiement réel désactivé')
    base=os.environ['PUBLIC_URL'].rstrip('/')
    if not base.startswith('https://'): raise HTTPException(503,'URL publique HTTPS requise')
    if plan not in integrations.PLANS: raise HTTPException(422,'Offre inconnue')
    try:
        price_id=integrations.checked_price(plan)
        # Serialize checkout creation per organization in PostgreSQL.
        if engine.dialect.name=='postgresql': session.execute(text('SELECT pg_advisory_xact_lock(7831, :org)'),{'org':user.org_id})
        b=session.get(Billing,user.org_id)
        if not b:
            customer=integrations.stripe_request('customers',{'email':user.email,'metadata[org_id]':str(user.org_id)})
            b=Billing(org_id=user.org_id,customer_id=customer['id']);session.add(b);session.flush()
        if b.state in ('active','trialing','past_due','unpaid','incomplete'): raise HTTPException(409,'Gérez votre abonnement existant')
        existing=integrations.stripe_request('checkout/sessions?customer='+quote(b.customer_id,safe='')+'&status=open&limit=100')
        if existing.get('data'): raise HTTPException(409,'Un paiement est déjà en cours. Terminez-le ou attendez son expiration.')
        subscriptions=integrations.stripe_request('subscriptions?customer='+quote(b.customer_id,safe='')+'&status=all&limit=100')
        if any(x.get('status') in ('active','trialing','past_due','unpaid','incomplete','paused') for x in subscriptions.get('data',[])): raise HTTPException(409,'Gérez votre abonnement existant')
        result=integrations.stripe_request('checkout/sessions',{'mode':'subscription','customer':b.customer_id,'line_items[0][price]':price_id,'line_items[0][quantity]':'1','success_url':base+'/?payment=returned','cancel_url':base+'/?payment=cancelled'})
        session.commit()
        return {'url':result['url']}
    except HTTPException: raise
    except Exception: raise HTTPException(502,'Service de paiement indisponible')

@app.post('/api/billing/portal',dependencies=[Depends(csrf_guard)])
def billing_portal(user:User=Depends(me),session:Session=Depends(db)):
    b=session.get(Billing,user.org_id)
    if not os.getenv('STRIPE_SECRET_KEY','').startswith('sk_test_'): raise HTTPException(403,'Paiement réel désactivé')
    if not integrations.billing_ready() or not b: raise HTTPException(404,'Aucun compte de facturation')
    try: return {'url':integrations.stripe_request('billing_portal/sessions',{'customer':b.customer_id,'return_url':os.environ['PUBLIC_URL'].rstrip('/')+'/'} )['url']}
    except Exception: raise HTTPException(502,'Portail indisponible')

@app.post('/webhooks/stripe')
async def stripe_webhook(request:Request,session:Session=Depends(db)):
    if os.getenv('STRIPE_SECRET_KEY') and not os.getenv('STRIPE_SECRET_KEY','').startswith('sk_test_'): raise HTTPException(403,'Paiement réel désactivé')
    secret=os.getenv('STRIPE_WEBHOOK_SECRET',''); body=await request.body()
    if not secret or not integrations.valid_stripe_signature(body,request.headers.get('stripe-signature',''),secret): raise HTTPException(400,'Signature invalide')
    try: event=json.loads(body); obj=event['data']['object']
    except (ValueError,KeyError,TypeError): raise HTTPException(400,'Événement invalide')
    if event.get('livemode') is True: raise HTTPException(400,'Événement réel refusé')
    if event.get('type') in ('customer.subscription.created','customer.subscription.updated','customer.subscription.deleted'):
        b=session.scalar(select(Billing).where(Billing.customer_id==obj.get('customer')))
        if b:
            if engine.dialect.name=='postgresql':
                session.execute(text('SELECT pg_advisory_xact_lock(7831, :org)'),{'org':b.org_id});session.refresh(b)
            # Fetch current Stripe state to avoid replay/out-of-order stale updates.
            try: current=integrations.stripe_request('subscriptions/'+obj['id'])
            except Exception: raise HTTPException(502,'Vérification Stripe indisponible')
            if current.get('customer')==b.customer_id and current.get('livemode') is not True:
                # An old cancelled subscription must not overwrite a different active one.
                if b.subscription_id and b.subscription_id!=current['id'] and current['status'] not in ('active','trialing') and b.state in ('active','trialing'):
                    return {'received':True}
                items=current.get('items',{}).get('data',[])
                price_id=items[0].get('price',{}).get('id') if len(items)==1 and items[0].get('quantity',1)==1 else None
                plan=next((k for k,v in integrations.PLANS.items() if v[0]==price_id),'')
                record=session.get(BillingPlan,b.org_id)
                if not record: record=BillingPlan(org_id=b.org_id);session.add(record)
                record.plan=plan
                detail=session.get(BillingDetails,b.org_id)
                if not detail: detail=BillingDetails(org_id=b.org_id);session.add(detail)
                detail.cancel_pending=int(bool(current.get('cancel_at_period_end') or current.get('cancel_at')))
                stamp=current.get('cancel_at') or current.get('current_period_end') or (items[0].get('current_period_end') if items else None)
                detail.ends_at=datetime.fromtimestamp(stamp,timezone.utc).isoformat() if isinstance(stamp,(int,float)) else ''
                b.subscription_id=current['id'];b.state=current['status'] if plan or current['status'] not in ('active','trialing') else 'unrecognized';session.commit()
    return {'received':True}

@app.get('/api/auto-reminders')
def auto_list(user:User=Depends(me),session:Session=Depends(db)):
    return list(session.scalars(select(AutoReminder.document_id).where(AutoReminder.org_id==user.org_id)))

@app.put('/api/auto-reminders/{document_id}',dependencies=[Depends(csrf_guard),Depends(write_access)])
def auto_enable(document_id:int,user:User=Depends(me),session:Session=Depends(db)):
    if not integrations.mail_ready() or user.email not in {x.strip().lower() for x in os.getenv('REMINDER_ALLOWED_ACCOUNTS','').split(',')}: raise HTTPException(503,'Envoi automatique non activé pour ce compte')
    if access_info(user,session)[0] not in ('trial','professional','business'): raise HTTPException(403,'Relances automatiques : formule Professional ou Business')
    d=session.scalar(select(Document).where(Document.id==document_id,Document.org_id==user.org_id))
    if not d: raise HTTPException(404,'Document introuvable')
    c=session.get(Company,d.company_id)
    if not c or c.org_id!=user.org_id or not c.email or '@' not in c.email: raise HTTPException(422,'Adresse de contact requise')
    if not session.get(AutoReminder,d.id): session.add(AutoReminder(document_id=d.id,org_id=user.org_id));session.commit()
    return {'ok':True}

@app.delete('/api/auto-reminders/{document_id}',dependencies=[Depends(csrf_guard)])
def auto_disable(document_id:int,user:User=Depends(me),session:Session=Depends(db)):
    session.execute(delete(AutoReminder).where(AutoReminder.document_id==document_id,AutoReminder.org_id==user.org_id));session.commit();return {'ok':True}

@app.post('/jobs/reminders')
def run_reminders(x_job_secret:str=Header(default=''),session:Session=Depends(db)):
    secret=os.getenv('REMINDER_JOB_SECRET','')
    if not integrations.mail_ready() or len(secret)<32 or not hmac.compare_digest(secret,x_job_secret): raise HTTPException(403,'Non autorisé')
    # One transaction per batch, advisory lock prevents overlapping jobs on PostgreSQL.
    if engine.dialect.name=='postgresql':
        if not session.scalar(text('SELECT pg_try_advisory_xact_lock(726382)')): return {'sent':0,'busy':True}
    allowed={x.strip().lower() for x in os.getenv('REMINDER_ALLOWED_ACCOUNTS','').split(',') if x.strip()}
    eligible=select(User.org_id).where(User.email.in_(allowed))
    rows=session.execute(select(AutoReminder,Document,Company).join(Document,AutoReminder.document_id==Document.id).join(Company,Document.company_id==Company.id).where(AutoReminder.org_id==Document.org_id,Company.org_id==Document.org_id,Document.org_id.in_(eligible),Document.expiry<=today_fr()+timedelta(days=30)).order_by(Document.expiry)).all()
    sent=0;failed=0
    for rule,d,c in rows:
        owner=session.scalar(select(User).where(User.org_id==d.org_id,User.email.in_(allowed)))
        if not owner or access_info(owner,session)[0] not in ('trial','professional','business'):continue
        days=(d.expiry-today_fr()).days; stage=3 if days<0 else 2 if days<=7 else 1 if days<=30 else 0
        if not stage or not c.email or (rule.last_expiry==d.expiry.isoformat() and rule.last_stage>=stage):continue
        if sent+failed>=10:break
        try: integrations.send_mail(c.email,'Renouvellement documentaire',f'Bonjour,\n\nMerci de nous transmettre une version à jour du document {d.kind} (échéance : {d.expiry}).\n\nCordialement.')
        except Exception: failed+=1;continue
        rule.last_expiry=d.expiry.isoformat();rule.last_stage=stage;session.add(Reminder(org_id=d.org_id,document_id=d.id));sent+=1
    session.commit();return {'sent':sent,'failed':failed}


@app.get('/api/storage')
def storage(user:User=Depends(me),session:Session=Depends(db)):
    count, used=session.execute(select(func.count(),func.coalesce(func.sum(func.length(Attachment.data)),0)).where(Attachment.org_id==user.org_id)).one()
    return {'files':count,'bytes':used,'max_files':100,'max_bytes':50*1024*1024}

@app.get('/api/workspace-export.json')
def workspace_export(user:User=Depends(me),session:Session=Depends(db)):
    from fastapi.responses import JSONResponse
    org=session.get(Organization,user.org_id)
    data={'organization':org.name,'email':user.email,'companies':companies(user,session),'documents':documents(user,session),'reminders':reminders(user,session),'exported_at':datetime.now(timezone.utc).isoformat()}
    return JSONResponse(data,headers={'Content-Disposition':'attachment; filename="opera-workspace.json"'})


@app.put('/api/documents/{document_id}/renew', dependencies=[Depends(csrf_guard),Depends(write_access)])
def renew_pdf(document_id:int, request:Request, file:UploadFile=File(...), expiry:date=Form(...), reference:str=Form('',max_length=200), user:User=Depends(me), session:Session=Depends(db)):
    rate_limit(request,'pdf',20)
    d=session.scalar(select(Document).where(Document.id==document_id,Document.org_id==user.org_id))
    if not d: raise HTTPException(404,'Document introuvable')
    data=file.file.read(MAX_BYTES+1); checked_pdf(data,'validate')
    if engine.dialect.name=='postgresql': session.execute(text('SELECT pg_advisory_xact_lock(726381)'))
    a=session.scalar(select(Attachment).where(Attachment.document_id==d.id,Attachment.org_id==user.org_id))
    old=len(a.data) if a else 0
    used=session.scalar(select(func.coalesce(func.sum(func.length(Attachment.data)),0)).where(Attachment.org_id==user.org_id))
    total=session.scalar(select(func.coalesce(func.sum(func.length(Attachment.data)),0)))
    count=session.scalar(select(func.count()).select_from(Attachment).where(Attachment.org_id==user.org_id))
    if used-old+len(data)>50*1024*1024 or total-old+len(data)>400*1024*1024 or (not a and count>=100): raise HTTPException(409,'Quota de stockage pilote atteint')
    filename=(file.filename or 'document.pdf').replace(chr(92),'/').split('/')[-1][:170]
    if not filename.lower().endswith('.pdf'): filename+='.pdf'
    if a: a.data=data; a.filename=filename
    else: session.add(Attachment(document_id=d.id,org_id=user.org_id,filename=filename,data=data))
    d.expiry=expiry; d.reference=reference
    # Re-confirm permission after a renewal; old PDF is replaced, not archived.
    session.execute(delete(AutoReminder).where(AutoReminder.document_id==d.id,AutoReminder.org_id==user.org_id))
    session.execute(delete(Reminder).where(Reminder.document_id==d.id,Reminder.org_id==user.org_id))
    log(session,user,'Document renouvelé · PDF remplacé');session.commit()
    return {'ok':True}

@app.get('/api/calendar.ics')
def calendar_export(user:User=Depends(me),session:Session=Depends(db)):
    def escape_ics(v):
        return str(v).replace(chr(92),chr(92)*2).replace('\r\n','\n').replace('\r','\n').replace('\n',chr(92)+'n').replace(';',chr(92)+';').replace(',',chr(92)+',')
    def fold(line):
        parts=[]; part=''
        for c in line:
            if len((part+c).encode('utf-8'))>75: parts.append(part);part=' '
            part+=c
        parts.append(part);return '\r\n'.join(parts)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//OPERA AI//Echeances//FR','CALSCALE:GREGORIAN']
    for d in documents(user,session):
        day=date.fromisoformat(d['expiry'])
        if day==date.max: continue
        lines.extend(['BEGIN:VEVENT',f'UID:opera-{user.org_id}-{d["id"]}@opera-local',f'DTSTAMP:{stamp}',f'DTSTART;VALUE=DATE:{day:%Y%m%d}',f'DTEND;VALUE=DATE:{day+timedelta(days=1):%Y%m%d}','SUMMARY:'+escape_ics(d['kind']+' - '+d['company']),'BEGIN:VALARM','ACTION:DISPLAY','TRIGGER:-P7D','DESCRIPTION:Renouvellement documentaire','END:VALARM','END:VEVENT'])
    lines.append('END:VCALENDAR')
    return Response('\r\n'.join(map(fold,lines))+'\r\n',media_type='text/calendar',headers={'Content-Disposition':'attachment; filename="opera-echeances.ics"'})


@app.post('/api/demo/seed', dependencies=[Depends(csrf_guard),Depends(write_access)])
def seed_demo(user:User=Depends(me),session:Session=Depends(db)):
    """Explicit, tenant-local fictional onboarding, only in an empty workspace."""
    if engine.dialect.name=='postgresql':
        session.execute(text('SELECT pg_advisory_xact_lock(726383, :org)'),{'org':user.org_id})
    if session.scalar(select(Company.id).where(Company.org_id==user.org_id).limit(1)):
        raise HTTPException(409,'Le jeu de démonstration est réservé aux espaces vides.')
    check_quota(user,session,Company,3);check_quota(user,session,Document,3)
    for name,kind,days in [('Atlas Démo','Assurance décennale',-5),('Horizon Démo','Attestation URSSAF',12),('Vertex Démo','Extrait Kbis',90)]:
        c=Company(org_id=user.org_id,name=name,contact='Contact fictif',email='');session.add(c);session.flush()
        session.add(Document(org_id=user.org_id,company_id=c.id,kind=kind,expiry=today_fr()+timedelta(days=days),reference='DEMO',notes='Exemple fictif – aucun document réel.'))
    log(session,user,'Exemples fictifs ajoutés');session.commit()
    return {'ok':True}

class CompanyBatch(BaseModel):
    rows: list[CompanyIn] = Field(min_length=1,max_length=100)

@app.post('/api/companies/import', dependencies=[Depends(csrf_guard),Depends(write_access)])
def import_companies(payload:CompanyBatch,user:User=Depends(me),session:Session=Depends(db)):
    if engine.dialect.name=='postgresql': session.execute(text('SELECT pg_advisory_xact_lock(726384, :org)'),{'org':user.org_id})
    existing={c.name.strip().casefold() for c in session.scalars(select(Company).where(Company.org_id==user.org_id))}
    added=0; skipped=0
    for row in payload.rows:
        values=row.model_dump(); values={k:v.strip() for k,v in values.items()}
        if len(values['name'])<2: raise HTTPException(422,'Nom d’entreprise invalide')
        if values['email'] and not __import__('re').fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',values['email']): raise HTTPException(422,'Adresse e-mail invalide : '+values['name'])
        if values['name'].casefold() in existing: skipped+=1;continue
        check_quota(user,session,Company)
        session.add(Company(org_id=user.org_id,**values));existing.add(values['name'].casefold());added+=1
    log(session,user,'Import groupé des entreprises');session.commit()
    return {'added':added,'skipped':skipped}

class AssistantIn(BaseModel):
    question: str = Field(min_length=2,max_length=500)

@app.post('/api/assistant', dependencies=[Depends(csrf_guard),Depends(write_access)])
def assistant_query(payload:AssistantIn, user:User=Depends(me),session:Session=Depends(db)):
    from .assistant import answer
    rows=documents(user,session)
    safe=[{k:d[k] for k in ('id','company','kind','expiry','days','status')} for d in rows]
    count=session.scalar(select(func.count()).select_from(Company).where(Company.org_id==user.org_id))
    return answer(payload.question,safe,count)
