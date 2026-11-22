"""OPERA AI beta: tenant-isolated document metadata. No file upload or AI processing yet."""
import csv
import io
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import create_engine, String, Integer, ForeignKey, Date, DateTime, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session
from pwdlib import PasswordHash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./opera_beta.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
if DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
SECRET_KEY = os.getenv('SECRET_KEY', '')
if not SECRET_KEY:
    # Ephemeral secret: safe for local testing, but sessions expire on server restart.
    SECRET_KEY = secrets.token_urlsafe(48)
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite:') else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
hasher = PasswordHash.recommended()
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
class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(engine)  # Beta only; production migrations should use Alembic.
app = FastAPI(title='OPERA AI', version='1.0-beta')

@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
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
    try:
        uid = int(signer.loads(token, max_age=60*60*24*7))
    except (BadSignature, SignatureExpired, ValueError):
        raise HTTPException(401, 'Session expirée')
    user = session.get(User, uid)
    if not user:
        raise HTTPException(401, 'Compte introuvable')
    return user

def csrf_guard(request: Request):
    if request.method in ('POST','PUT','PATCH','DELETE'):
        origin = request.headers.get('origin')
        if origin:
            from urllib.parse import urlparse
            target = urlparse(str(request.base_url))
            source = urlparse(origin)
            if source.netloc != target.netloc or source.scheme not in ('http', 'https'):
                raise HTTPException(403, 'Origine refusée')

def log(session, user, action):
    session.add(Audit(org_id=user.org_id, user_id=user.id, action=action))

class RegisterIn(BaseModel):
    organization: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=12, max_length=128)
class LoginIn(BaseModel):
    email: str
    password: str
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

def set_cookie(response, user):
    response.set_cookie('opera_session', signer.dumps(str(user.id)), max_age=604800, httponly=True, secure=os.getenv('COOKIE_SECURE','1') == '1', samesite='lax', path='/')

@app.get('/')
def home():
    return FileResponse(Path(__file__).parent / 'static' / 'index.html')

@app.get('/health')
def health():
    return {'status': 'ok', 'version': '1.0-beta'}

@app.post('/api/register', dependencies=[Depends(csrf_guard)])
def register(payload: RegisterIn, response: Response, session: Session = Depends(db)):
    email = payload.email.strip().lower()
    if '@' not in email or len(email.split('@')[-1]) < 3:
        raise HTTPException(422, 'E-mail invalide')
    if session.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, 'Adresse déjà utilisée')
    org = Organization(name=payload.organization.strip())
    session.add(org); session.flush()
    user = User(org_id=org.id, email=email, password_hash=hasher.hash(payload.password))
    session.add(user); session.flush()
    log(session, user, 'Création du compte')
    session.commit(); set_cookie(response, user)
    return {'email': user.email, 'organization': org.name}

@app.post('/api/login', dependencies=[Depends(csrf_guard)])
def login(payload: LoginIn, response: Response, session: Session = Depends(db)):
    user = session.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if not user or not hasher.verify(payload.password, user.password_hash):
        raise HTTPException(401, 'Identifiants incorrects')
    set_cookie(response, user)
    return {'email': user.email}

@app.post('/api/logout', dependencies=[Depends(csrf_guard)])
def logout(response: Response):
    response.delete_cookie('opera_session', path='/')
    return {'ok': True}

@app.get('/api/me')
def profile(user: User = Depends(me), session: Session = Depends(db)):
    org = session.get(Organization, user.org_id)
    return {'email': user.email, 'organization': org.name}

@app.get('/api/companies')
def companies(user: User = Depends(me), session: Session = Depends(db)):
    return [{'id': c.id, 'name': c.name, 'contact': c.contact, 'email': c.email} for c in session.scalars(select(Company).where(Company.org_id == user.org_id).order_by(Company.name))]

@app.post('/api/companies', dependencies=[Depends(csrf_guard)])
def add_company(payload: CompanyIn, user: User = Depends(me), session: Session = Depends(db)):
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

def doc_dict(d, company):
    days = (d.expiry - date.today()).days
    return {'id': d.id, 'company_id': d.company_id, 'company': company, 'kind': d.kind, 'expiry': d.expiry.isoformat(), 'reference': d.reference, 'notes': d.notes, 'days': days, 'status': 'expired' if days < 0 else 'soon' if days <= 30 else 'valid'}

@app.get('/api/documents')
def documents(user: User = Depends(me), session: Session = Depends(db)):
    rows = session.execute(select(Document, Company.name).join(Company, Document.company_id == Company.id).where(Document.org_id == user.org_id, Company.org_id == user.org_id).order_by(Document.expiry)).all()
    return [doc_dict(d, name) for d,name in rows]

@app.post('/api/documents', dependencies=[Depends(csrf_guard)])
def add_doc(payload: DocIn, user: User = Depends(me), session: Session = Depends(db)):
    c = session.scalar(select(Company).where(Company.id == payload.company_id, Company.org_id == user.org_id))
    if not c: raise HTTPException(404, 'Entreprise introuvable')
    d = Document(org_id=user.org_id, **payload.model_dump())
    session.add(d); log(session,user,'Document ajouté'); session.commit()
    return {'id': d.id}

@app.put('/api/documents/{document_id}', dependencies=[Depends(csrf_guard)])
def edit_doc(document_id: int, payload: DocIn, user: User = Depends(me), session: Session = Depends(db)):
    d = session.scalar(select(Document).where(Document.id == document_id, Document.org_id == user.org_id))
    c = session.scalar(select(Company).where(Company.id == payload.company_id, Company.org_id == user.org_id))
    if not d or not c: raise HTTPException(404, 'Document ou entreprise introuvable')
    for key,value in payload.model_dump().items(): setattr(d,key,value)
    log(session,user,'Document modifié'); session.commit()
    return {'ok': True}

@app.delete('/api/documents/{document_id}', dependencies=[Depends(csrf_guard)])
def delete_doc(document_id: int, user: User = Depends(me), session: Session = Depends(db)):
    d = session.scalar(select(Document).where(Document.id == document_id, Document.org_id == user.org_id))
    if not d: raise HTTPException(404, 'Document introuvable')
    session.delete(d); log(session,user,'Document supprimé'); session.commit()
    return {'ok': True}

@app.get('/api/dashboard')
def dashboard(user: User = Depends(me), session: Session = Depends(db)):
    docs = session.scalars(select(Document).where(Document.org_id == user.org_id)).all()
    return {'companies': session.scalar(select(func.count()).select_from(Company).where(Company.org_id == user.org_id)), 'documents': len(docs), 'expired': sum(d.expiry < date.today() for d in docs), 'soon': sum(date.today() <= d.expiry <= date.today()+timedelta(days=30) for d in docs)}

@app.get('/api/audit')
def audit(user: User = Depends(me), session: Session = Depends(db)):
    return [{'action':a.action,'at':a.created_at.isoformat()} for a in session.scalars(select(Audit).where(Audit.org_id == user.org_id).order_by(Audit.id.desc()).limit(30))]

@app.get('/api/export.csv')
def export_csv(user: User = Depends(me), session: Session = Depends(db)):
    rows = documents(user,session)
    buf = io.StringIO(); writer = csv.writer(buf)
    writer.writerow(['Entreprise','Document','Référence','Échéance','Jours restants','Statut','Notes'])
    for d in rows: writer.writerow([d['company'],d['kind'],d['reference'],d['expiry'],d['days'],d['status'],d['notes']])
    return Response('\ufeff'+buf.getvalue(), media_type='text/csv; charset=utf-8', headers={'Content-Disposition':'attachment; filename="opera-export.csv"'})
