"""Optional bounded local OCR, no external document transmission."""
import shutil
import subprocess
import tempfile
from pathlib import Path
from threading import BoundedSemaphore

_slots = BoundedSemaphore(1)

def available():
    return bool(shutil.which('pdftoppm') and shutil.which('tesseract'))

def extract_scan(data, pages):
    if not available() or not _slots.acquire(blocking=False):
        return ''
    try:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            source = path / 'input.pdf'
            source.write_bytes(data)
            subprocess.run(['pdftoppm','-f','1','-l',str(min(pages,2)),'-scale-to','1800','-gray','-png',str(source),str(path/'page')], check=True, timeout=12, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            parts=[]
            for image in sorted(path.glob('page-*.png')):
                result=subprocess.run(['tesseract',str(image),'stdout','-l','fra+eng'],check=True,timeout=12,capture_output=True)
                parts.append(result.stdout.decode('utf-8','replace')[:12000])
            return '\n'.join(parts)
    except (OSError, subprocess.SubprocessError):
        return ''
    finally:
        _slots.release()
