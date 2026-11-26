"""Conservative text extraction; suggestions are never treated as verified dates."""
import io
import re
import unicodedata
from datetime import date
from pypdf import PdfReader
from .ocr_tools import extract_scan

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
        if '/EmbeddedFiles' in names or '/AF' in root:
            raise ValueError('PDF avec pièce jointe intégrée non accepté. Exportez une copie PDF simple depuis votre lecteur (conservez l’original signé).')
        if any(k in root for k in ('/OpenAction', '/AA', '/AcroForm')) or '/JavaScript' in names:
            raise ValueError('PDF interactif non accepté : formulaire ou action active.')
        for page in reader.pages:
            if '/AA' in page: raise ValueError('Action active sur une page PDF non acceptée.')
            for annotation in page.get('/Annots', []):
                a=annotation.get_object()
                if '/AA' in a or '/A' in a or a.get('/Subtype') in ('/FileAttachment','/RichMedia','/Screen','/Movie','/Sound','/Widget'):
                    raise ValueError('Annotation interactive non acceptée.')
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
    method = 'text_rules'
    if not text.strip():
        text = extract_scan(data, len(reader.pages))
        if text.strip(): method = 'ocr_rules'
    return analyze_text(text, len(reader.pages), method)

def analyze_text(text, pages=1, method='text_rules'):
    plain = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    kinds = [('decennale','Assurance décennale'),('vigilance','Attestation de vigilance URSSAF'),('urssaf','Attestation URSSAF'),('kbis','Extrait Kbis'),('responsabilite civile','Responsabilité civile'),('assurance','Attestation d’assurance')]
    kind = next((label for key,label in kinds if key in plain), '')
    candidates = []
    for m in re.finditer(r'(?:date\s+d[’\']?\s*expiration|expiration|echeance|valable\s+jusqu[’\']?\s*au|validite\s+jusqu[’\']?\s*au|fin\s+de\s+validite)\s*[:\-]?\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})', plain):
        try:
            value = date(int(m[3]),int(m[2]),int(m[1])).isoformat()
            if value not in candidates: candidates.append(value)
        except ValueError: pass
    # Accept only explicit end-of-validity dates, never infer legal deadlines.
    for m in re.finditer(r'(?:expiration|echeance|valable jusqu[’\']?\s*au|fin de validite)\s*[:\-]?\s*(\d{4})-(\d{2})-(\d{2})', plain):
        try:
            value=date(int(m[1]),int(m[2]),int(m[3])).isoformat()
            if value not in candidates: candidates.append(value)
        except ValueError: pass
    reference_matches = re.findall(r'(?:num[eé]ro|n[°º]|r[eé]f[eé]rence)\s*(?:de\s+)?(?:contrat|police|attestation)\s*[:#]?[ \t]*([A-Z0-9][A-Z0-9./-]{3,49})', text, re.I)
    references=list(dict.fromkeys(reference_matches))
    sirets=list(dict.fromkeys(re.sub(r'\s','',m) for m in re.findall(r'(?<!\d)\d{3}\s?\d{3}\s?\d{3}\s?\d{5}(?!\d)',text)))
    return {'siret_candidates':sirets[:10], 'reference':references[0] if len(references)==1 else '', 'kind':kind,'expiry':candidates[0] if len(candidates)==1 else '', 'candidate_dates':candidates,'text_found':bool(text.strip()),'pages':pages,'method':method,'warning':'Suggestions à vérifier sur le document original. Si aucune date fiable ne ressort, renseignez-la manuellement.'}
