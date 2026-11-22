"""OPERA AI local MVP. Demo only: no authentication or production file storage."""
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
import os
import sqlite3
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('OPERA_DB', ROOT.parent / 'opera.db'))


def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con


def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.executescript('''
          CREATE TABLE IF NOT EXISTS subcontractors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            contact TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
          );
          CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_id INTEGER NOT NULL REFERENCES subcontractors(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            expiry TEXT NOT NULL,
            reference TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
          );
        ''')


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title='OPERA AI — Démonstration', version='0.3.0', lifespan=lifespan)

@app.middleware('http')
async def protect_public_demo(request: Request, call_next):
    # Public demo: prevent unauthenticated modifications of the shared database.
    if os.environ.get('OPERA_PUBLIC_DEMO', '1') == '1' and request.url.path.startswith('/api/'):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail': 'API désactivée dans la démonstration publique.'}, status_code=403)
    return await call_next(request)


class SubcontractorIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    contact: str = Field(default='', max_length=150)
    email: str = Field(default='', max_length=200)

class DocumentIn(BaseModel):
    subcontractor_id: int
    kind: str = Field(min_length=2, max_length=120)
    expiry: date
    reference: str = Field(default='', max_length=200)


def status(expiry: str):
    delta = (date.fromisoformat(expiry) - date.today()).days
    return 'expired' if delta < 0 else 'soon' if delta <= 30 else 'valid'

@app.get('/')
def home():
    return FileResponse(ROOT / 'static' / 'index.html')

@app.get('/api/subcontractors')
def list_subcontractors():
    with connect() as con:
        return [dict(x) for x in con.execute('SELECT * FROM subcontractors ORDER BY name')]

@app.post('/api/subcontractors', status_code=201)
def add_subcontractor(data: SubcontractorIn):
    try:
        with connect() as con:
            cur = con.execute('INSERT INTO subcontractors(name, contact, email) VALUES (?,?,?)', (data.name.strip(), data.contact.strip(), data.email.strip()))
            return {'id': cur.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'Cette entreprise existe déjà.')

@app.delete('/api/subcontractors/{item_id}')
def delete_subcontractor(item_id: int):
    with connect() as con:
        cur = con.execute('DELETE FROM subcontractors WHERE id=?', (item_id,))
        if not cur.rowcount:
            raise HTTPException(404, 'Entreprise introuvable')
    return {'ok': True}

@app.get('/api/documents')
def list_documents():
    with connect() as con:
        rows = con.execute('''SELECT d.*, s.name AS subcontractor FROM documents d
          JOIN subcontractors s ON s.id=d.subcontractor_id ORDER BY d.expiry''').fetchall()
        return [{**dict(r), 'status': status(r['expiry'])} for r in rows]

@app.post('/api/documents', status_code=201)
def add_document(data: DocumentIn):
    with connect() as con:
        if not con.execute('SELECT 1 FROM subcontractors WHERE id=?', (data.subcontractor_id,)).fetchone():
            raise HTTPException(404, 'Entreprise introuvable')
        cur = con.execute('INSERT INTO documents(subcontractor_id,kind,expiry,reference) VALUES (?,?,?,?)',
          (data.subcontractor_id, data.kind.strip(), data.expiry.isoformat(), data.reference.strip()))
        return {'id': cur.lastrowid}

@app.delete('/api/documents/{item_id}')
def delete_document(item_id: int):
    with connect() as con:
        cur = con.execute('DELETE FROM documents WHERE id=?', (item_id,))
        if not cur.rowcount:
            raise HTTPException(404, 'Document introuvable')
    return {'ok': True}

@app.get('/api/overview')
def overview():
    with connect() as con:
        companies = con.execute('SELECT COUNT(*) FROM subcontractors').fetchone()[0]
        docs = [r['expiry'] for r in con.execute('SELECT expiry FROM documents')]
    return {'companies': companies, 'documents': len(docs), 'expired': sum(status(d)=='expired' for d in docs), 'soon': sum(status(d)=='soon' for d in docs)}

@app.get('/api/reminders')
def reminders():
    with connect() as con:
        rows = con.execute('''SELECT s.name, s.contact, s.email, d.kind, d.expiry FROM documents d
          JOIN subcontractors s ON s.id=d.subcontractor_id ORDER BY d.expiry''').fetchall()
    return [{'name':r['name'], 'email':r['email'], 'kind':r['kind'], 'expiry':r['expiry'],
      'message':f"Bonjour, le document « {r['kind']} » de {r['name']} arrive à échéance le {r['expiry']} (ou est déjà expiré). Pourriez-vous nous transmettre une version à jour ? Merci."}
      for r in rows if status(r['expiry']) != 'valid']
