"""Bounded spreadsheet preview and tenant-scoped administrative report."""
import io, zipfile, re
from datetime import datetime, date
from fastapi import Depends, HTTPException, UploadFile, File, Request, Response
from sqlalchemy import select
from openpyxl import load_workbook
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from xml.sax.saxutils import escape
from .main import app, me, db, csrf_guard, write_access, rate_limit, documents, Organization, today_fr, CompanyIn
from .rc10 import Project, project_row

@app.post('/api/companies/xlsx-preview', dependencies=[Depends(csrf_guard),Depends(write_access)])
def xlsx_preview(request:Request,file:UploadFile=File(...),user=Depends(me)):
    rate_limit(request,'xlsx',10)
    data=file.file.read(512*1024+1)
    if len(data)>512*1024: raise HTTPException(422,'Excel limité à 512 Ko')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            entries=z.infolist()
            if len(entries)>150 or sum(x.file_size for x in entries)>4*1024*1024 or any('vbaProject' in x.filename or 'externalLinks/' in x.filename for x in entries): raise ValueError()
        wb=load_workbook(io.BytesIO(data),read_only=True,data_only=False,keep_links=False)
        try:
            ws=wb.active
            if ws.max_row and ws.max_row>101 or ws.max_column and ws.max_column>3: raise ValueError()
            result=[]
            for i,row in enumerate(ws.iter_rows(min_row=1,max_row=min(ws.max_row or 101,101),max_col=3)):
                if any(c.data_type=='f' for c in row): raise ValueError()
                vals=[str(c.value or '').strip() for c in row]
                if not any(vals): continue
                if i==0 and vals[0].casefold() in ('nom','entreprise','nom de l’entreprise','nom entreprise'): continue
                if any(re.search(r'[\t\r\n]',v) for v in vals): raise ValueError()
                result.append(CompanyIn(name=vals[0],contact=vals[1],email=vals[2]).model_dump())
            if not result or len(result)>100: raise ValueError()
        finally: wb.close()
    except Exception: raise HTTPException(422,'Excel invalide : 100 entreprises maximum, 3 colonnes (nom, contact, e-mail), sans formule.')
    return {'rows':result}

@app.get('/api/report.pdf')
def report(user=Depends(me),session=Depends(db)):
    rows=documents(user,session)
    org=session.get(Organization,user.org_id)
    projects=[project_row(p,session,user.org_id) for p in session.scalars(select(Project).where(Project.org_id==user.org_id).order_by(Project.name))]
    styles=getSampleStyleSheet(); buf=io.BytesIO()
    def p(s,style='BodyText'): return Paragraph(escape(str(s)),styles[style])
    story=[p('OPERA AI | Rapport administratif','Title'),p(org.name),p('Situation au '+today_fr().strftime('%d/%m/%Y')),Spacer(1,12),p('Suivi documentaire','Heading2'),p(f'{len(rows)} documents · {sum(d["status"]=="expired" for d in rows)} expirés · {sum(d["status"]=="soon" for d in rows)} à renouveler'),Spacer(1,10)]
    table=[[p('Entreprise'),p('Document'),p('Échéance'),p('Statut')]]
    labels={'valid':'Hors alerte','expired':'Expiré','soon':'À renouveler'}
    for d in rows: table.append([p(d['company']),p(d['kind']),p(d['expiry'][8:10]+'/'+d['expiry'][5:7]+'/'+d['expiry'][:4]),p(labels[d['status']])])
    t=Table(table,colWidths=[135,150,80,90],repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#C8E9DE')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.25,colors.HexColor('#CDD8D5')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F2F7F5')])]))
    story.extend([t,Spacer(1,16),p('Chantiers et pièces à contrôler','Heading2')])
    for project in projects:
        story.append(p(project['name'],'Heading3'))
        for c in project['companies']: story.append(p(c['name']+' : '+(', '.join(c['missing']) if c['missing'] else 'Aucune pièce signalée manquante selon les exigences renseignées')))
    story.extend([Spacer(1,16),p('Rapport de suivi interne, non constitutif d’une certification de conformité. Vérifier les originaux et les exigences applicables.')])
    def footer(canvas,doc):
        canvas.setFont('Helvetica',9);canvas.setFillColor(colors.HexColor('#53645F'));canvas.drawString(72,35,'OPERA AI — confidentiel');canvas.drawRightString(523,35,f'Page {doc.page}')
    SimpleDocTemplate(buf).build(story,onFirstPage=footer,onLaterPages=footer)
    return Response(buf.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="opera-rapport.pdf"','Cache-Control':'no-store'})

# Single-use document collection link. The recipient cannot read any workspace data.
import hashlib, secrets
from datetime import timedelta, timezone
from pathlib import Path
from sqlalchemy import String, Integer, DateTime, LargeBinary, ForeignKey, func, delete, text
from sqlalchemy.orm import Mapped, mapped_column
from fastapi import Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .main import Base, engine, User, Document, Attachment, Company, AutoReminder, Reminder, access_info, checked_pdf, log, MAX_BYTES

class Deposit(Base):
    __tablename__='document_deposits'
    id:Mapped[int]=mapped_column(primary_key=True)
    org_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),index=True)
    document_id:Mapped[int]=mapped_column(ForeignKey('documents.id',ondelete='CASCADE'),index=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    expires:Mapped[datetime]=mapped_column(DateTime)
    owner_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    state:Mapped[str]=mapped_column(String(16),default='open')
    filename:Mapped[str]=mapped_column(String(180),default='')
    data:Mapped[bytes|None]=mapped_column(LargeBinary,nullable=True)
Base.metadata.create_all(engine)

def utcnow(): return datetime.now(timezone.utc).replace(tzinfo=None)
def lock_storage(session):
    if engine.dialect.name=='postgresql': session.execute(text('SELECT pg_advisory_xact_lock(726381)'))
def pending_storage(session,org=None):
    q=select(func.coalesce(func.sum(func.length(Deposit.data)),0)).where(Deposit.state=='received')
    if org is not None:q=q.where(Deposit.org_id==org)
    return session.scalar(q) or 0

def get_deposit(session,id,org):
    r=session.scalar(select(Deposit).where(Deposit.id==id,Deposit.org_id==org))
    if not r: raise HTTPException(404,'Dépôt introuvable')
    return r

@app.post('/api/documents/{did}/deposit-link',dependencies=[Depends(csrf_guard),Depends(write_access)])
def create_deposit(did:int,request:Request,user=Depends(me),session=Depends(db)):
    rate_limit(request,'deposit-create',20)
    if access_info(user,session)[0] not in ('trial','professional','business'): raise HTTPException(403,'Collecte : Professional ou Business')
    lock_storage(session)
    d=session.scalar(select(Document).where(Document.id==did,Document.org_id==user.org_id))
    if not d:raise HTTPException(404,'Document introuvable')
    if session.scalar(select(Deposit.id).where(Deposit.document_id==did,Deposit.org_id==user.org_id,Deposit.state=='received')):raise HTTPException(409,'Un PDF est déjà en attente de validation')
    session.execute(delete(Deposit).where(Deposit.document_id==did,Deposit.org_id==user.org_id))
    token=secrets.token_urlsafe(32)
    session.add(Deposit(org_id=user.org_id,document_id=did,owner_id=user.id,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires=utcnow()+timedelta(days=7)))
    log(session,user,'Lien de collecte créé');session.commit()
    return {'path':'/depot#'+token,'expires_days':7}

@app.get('/depot')
def deposit_page():return FileResponse(Path(__file__).parent/'static'/'deposit.html',headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})

@app.post('/api/public/deposit',dependencies=[Depends(csrf_guard)])
def receive_deposit(request:Request,token:str=Form(...,min_length=40,max_length=60),file:UploadFile=File(...),session=Depends(db)):
    rate_limit(request,'deposit-receive',10)
    digest=hashlib.sha256(token.encode()).hexdigest()
    r=session.scalar(select(Deposit).where(Deposit.token_hash==digest))
    if not r or r.state!='open' or r.expires<utcnow():raise HTTPException(404,'Lien invalide ou expiré')
    data=file.file.read(MAX_BYTES+1);checked_pdf(data,'validate')
    lock_storage(session)
    r=session.scalar(select(Deposit).where(Deposit.token_hash==digest).execution_options(populate_existing=True))
    if not r or r.state!='open' or r.expires<utcnow():raise HTTPException(404,'Lien invalide ou expiré')
    owner=session.get(User,r.owner_id);d=session.get(Document,r.document_id)
    if not owner or owner.org_id!=r.org_id or not d or d.org_id!=r.org_id or access_info(owner,session)[0] not in ('trial','professional','business'):raise HTTPException(404,'Lien invalide ou expiré')
    used=session.scalar(select(func.coalesce(func.sum(func.length(Attachment.data)),0)).where(Attachment.org_id==r.org_id))
    total=session.scalar(select(func.coalesce(func.sum(func.length(Attachment.data)),0)))
    if used+pending_storage(session,r.org_id)+len(data)>50*1024*1024 or total+pending_storage(session)+len(data)>400*1024*1024:raise HTTPException(409,'Capacité de stockage atteinte')
    r.data=data;r.filename=(file.filename or 'document.pdf').replace(chr(92),'/').split('/')[-1][:170];r.state='received';log(session,owner,'PDF reçu par lien de collecte');session.commit();return {'ok':True}

@app.get('/api/deposits')
def deposits(user=Depends(me),session=Depends(db)):
    rows=session.execute(select(Deposit.id,Deposit.state,Deposit.expires,Deposit.filename,Document.kind,Company.name).join(Document,Deposit.document_id==Document.id).join(Company,Document.company_id==Company.id).where(Deposit.org_id==user.org_id,Document.org_id==user.org_id,Company.org_id==user.org_id).order_by(Deposit.id.desc())).all()
    return [dict(id=i,state=('expired' if state=='open' and expires<utcnow() else state),filename=filename,kind=kind,company=company) for i,state,expires,filename,kind,company in rows]

@app.get('/api/deposits/{id}/pdf')
def deposit_pdf(id:int,user=Depends(me),session=Depends(db)):
    r=get_deposit(session,id,user.org_id)
    if r.state!='received' or r.data is None:raise HTTPException(404,'PDF indisponible')
    return Response(r.data,media_type='application/octet-stream',headers={'Content-Disposition':'attachment; filename="depot.pdf"'})

class AcceptDeposit(BaseModel):
    expiry:date
    reference:str=Field(default='',max_length=200)
@app.post('/api/deposits/{id}/accept',dependencies=[Depends(csrf_guard),Depends(write_access)])
def accept_deposit(id:int,payload:AcceptDeposit,user=Depends(me),session=Depends(db)):
    lock_storage(session);r=get_deposit(session,id,user.org_id)
    if r.state!='received' or r.data is None:raise HTTPException(409,'Aucun PDF à valider')
    d=session.scalar(select(Document).where(Document.id==r.document_id,Document.org_id==user.org_id))
    if not d:raise HTTPException(404,'Document introuvable')
    a=session.scalar(select(Attachment).where(Attachment.document_id==d.id,Attachment.org_id==user.org_id))
    if a:a.data=r.data;a.filename=r.filename
    else:
        if session.scalar(select(func.count()).select_from(Attachment).where(Attachment.org_id==user.org_id))>=100:raise HTTPException(409,'Limite PDF atteinte')
        session.add(Attachment(document_id=d.id,org_id=user.org_id,data=r.data,filename=r.filename))
    d.expiry=payload.expiry;d.reference=payload.reference
    session.execute(delete(AutoReminder).where(AutoReminder.document_id==d.id,AutoReminder.org_id==user.org_id))
    session.execute(delete(Reminder).where(Reminder.document_id==d.id,Reminder.org_id==user.org_id))
    session.delete(r);log(session,user,'PDF collecté et renouvellement validé');session.commit();return {'ok':True}

@app.delete('/api/deposits/{id}',dependencies=[Depends(csrf_guard)])
def revoke_deposit(id:int,user=Depends(me),session=Depends(db)):
    lock_storage(session);r=get_deposit(session,id,user.org_id);session.delete(r);log(session,user,'Lien ou dépôt supprimé');session.commit();return {'ok':True}

# Customizable reminder templates; placeholders are literal substitution, not executable.
class ReminderSettings(Base):
    __tablename__='reminder_settings'
    org_id:Mapped[int]=mapped_column(ForeignKey('organizations.id'),primary_key=True)
    signature:Mapped[str]=mapped_column(String(300),default='')
    upcoming:Mapped[str]=mapped_column(String(1500),default='')
    overdue:Mapped[str]=mapped_column(String(1500),default='')
Base.metadata.create_all(engine)
DEFAULT_UPCOMING='Bonjour,\n\nDans le cadre du suivi administratif de nos sous-traitants, votre document « {document} » arrive à échéance le {date}.\n\nNous vous remercions de nous transmettre une version à jour avant cette date.\n\nCordialement,\n{signature}'
DEFAULT_OVERDUE='Bonjour,\n\nDans le cadre du suivi administratif de nos sous-traitants, votre document « {document} » est arrivé à expiration le {date}.\n\nNous vous remercions de nous transmettre une version à jour dans les meilleurs délais.\n\nCordialement,\n{signature}'
class ReminderSettingsIn(BaseModel):
    signature:str=Field(default='',max_length=300)
    upcoming:str=Field(default='',max_length=1500)
    overdue:str=Field(default='',max_length=1500)

def reminder_settings(session,org_id):
    org=session.get(Organization,org_id);r=session.get(ReminderSettings,org_id)
    return {'signature':(r.signature if r else '') or org.name,'upcoming':(r.upcoming if r else '') or DEFAULT_UPCOMING,'overdue':(r.overdue if r else '') or DEFAULT_OVERDUE}
def reminder_draft(session,org_id,d,c):
    cfg=reminder_settings(session,org_id);is_overdue=d.expiry<today_fr();template=cfg['overdue' if is_overdue else 'upcoming']
    mapping={'document':d.kind,'date':d.expiry.strftime('%d/%m/%Y'),'entreprise':c.name,'signature':cfg['signature']}
    body=re.sub(r'\{(document|date|entreprise|signature)\}',lambda m:mapping[m.group(1)],template)
    subject=('Renouvellement nécessaire' if is_overdue else 'Échéance à anticiper')+' — '+re.sub(r'[\r\n]+',' ',d.kind)[:120]
    return {'subject':subject,'body':body,'email':c.email}
@app.get('/api/reminder-settings')
def reminder_settings_get(user=Depends(me),session=Depends(db)):return reminder_settings(session,user.org_id)
@app.put('/api/reminder-settings',dependencies=[Depends(csrf_guard),Depends(write_access)])
def reminder_settings_put(payload:ReminderSettingsIn,user=Depends(me),session=Depends(db)):
    for template in (payload.upcoming,payload.overdue):
        if template and not all(x in template for x in ('{document}','{date}')):raise HTTPException(422,'Les modèles doivent contenir {document} et {date}.')
    r=session.get(ReminderSettings,user.org_id)
    if not r:r=ReminderSettings(org_id=user.org_id);session.add(r)
    for k,v in payload.model_dump().items():setattr(r,k,v)
    log(session,user,'Modèles de relance modifiés');session.commit();return {'ok':True}
@app.get('/api/reminders/{did}/draft')
def get_reminder_draft(did:int,user=Depends(me),session=Depends(db)):
    d=session.scalar(select(Document).where(Document.id==did,Document.org_id==user.org_id));c=session.get(Company,d.company_id) if d else None
    if not d or not c or c.org_id!=user.org_id:raise HTTPException(404,'Document introuvable')
    return reminder_draft(session,user.org_id,d,c)
