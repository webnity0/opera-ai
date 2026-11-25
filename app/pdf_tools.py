"""Conservative text extraction; suggestions are never treated as verified dates."""
import io
import re
import unicodedata
from datetime import date
from pypdf import PdfReader

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 30

def validate_pdf(data):
    if not data or len(data) > MAX_BYTES:
        raise ValueError('PDF limité à 10 Mo.')
    if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-4096:]:
        raise ValueError('Fichier PDF invalide.')
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ValueError('PDF protégé par mot de passe non accepté.')
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise ValueError('PDF limité à 30 pages.')
        root = reader.trailer['/Root']
        names = root.get('/Names', {})
        if hasattr(names, 'get_object'): names = names.get_object()
        if any(k in root for k in ('/OpenAction', '/AA', '/AcroForm')) or any(k in names for k in ('/EmbeddedFiles','/JavaScript')):
            raise ValueError('PDF interactif non accepté.')
        return reader
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('PDF illisible.') from exc

def analyze_pdf(data):
    reader = validate_pdf(data)
    parts = []
    for page in reader.pages[:10]:
        try:
            contents = page.get_contents()
            if contents and len(contents.get_data()) > 2_000_000:
                continue
            parts.append((page.extract_text() or '')[:12000])
        except Exception:
            continue
    text = '\n'.join(parts)[:60000]
    plain = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    kinds = [('decennale','Assurance décennale'),('vigilance','Attestation de vigilance URSSAF'),('urssaf','Attestation URSSAF'),('kbis','Extrait Kbis'),('responsabilite civile','Responsabilité civile'),('assurance','Attestation d’assurance')]
    kind = next((label for key,label in kinds if key in plain), '')
    candidates = []
    for m in re.finditer(r'(?:date\s+d[’\']?\s*expiration|expiration|echeance|valable\s+jusqu[’\']?\s*au|validite\s+jusqu[’\']?\s*au|fin\s+de\s+validite)\s*[:\-]?\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})', plain):
        try:
            value = date(int(m[3]),int(m[2]),int(m[1])).isoformat()
            if value not in candidates: candidates.append(value)
        except ValueError: pass
    return {'kind':kind,'expiry':candidates[0] if len(candidates)==1 else '', 'candidate_dates':candidates,'text_found':bool(text.strip()),'pages':len(reader.pages),'method':'text_rules','warning':'Suggestions à vérifier sur le document original. Les PDF scannés nécessitent une saisie manuelle.'}
