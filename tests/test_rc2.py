import io
import shutil
import pytest
from PIL import Image, ImageDraw, ImageFont
from app.pdf_tools import analyze_pdf, analyze_text
from fastapi.testclient import TestClient
from app.main import app

def test_explicit_dates():
    assert analyze_text('Expiration: 2027-12-31')['expiry']=='2027-12-31'
    assert analyze_text('Expiration: 2027-12-31\nExpiration: 01/01/2028')['expiry']==''
    assert analyze_text('Date de naissance : 01/01/2020')['expiry']==''

def test_health():
    assert TestClient(app).get('/health').json()['version']=='2.0-rc8'

@pytest.mark.skipif(not shutil.which('tesseract') or not shutil.which('pdftoppm'),reason='OCR optional')
def test_scanned_pdf():
    im=Image.new('RGB',(1400,900),'white')
    font=ImageFont.truetype('DejaVuSans.ttf',44)
    draw=ImageDraw.Draw(im)
    draw.text((80,100),'Assurance decennale',font=font,fill='black')
    draw.text((80,230),'Expiration: 31/12/2027',font=font,fill='black')
    out=io.BytesIO();im.save(out,format='PDF',resolution=150)
    result=analyze_pdf(out.getvalue())
    assert result['method']=='ocr_rules',result
    assert result['expiry']=='2027-12-31',result
