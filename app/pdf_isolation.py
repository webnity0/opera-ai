import json, os, sys, subprocess, signal
from pathlib import Path
from threading import BoundedSemaphore
from .pdf_tools import MAX_BYTES
_slots=BoundedSemaphore(1)

def process_pdf(data, mode):
    if not data or len(data)>MAX_BYTES: raise ValueError('PDF limité à 10 Mo.')
    if not _slots.acquire(blocking=False): raise RuntimeError('Analyse occupée, réessayez dans quelques instants.')
    try:
        # Do not pass database URLs, billing keys or session secrets to the parser.
        env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','TESSDATA_PREFIX','SYSTEMROOT','WINDIR','TEMP','TMP')}
        with subprocess.Popen([sys.executable,'-m','app.pdf_worker',mode],cwd=Path(__file__).resolve().parent.parent,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=os.name=='posix') as proc:
            try: out,_=proc.communicate(data,timeout=45)
            except subprocess.TimeoutExpired:
                if os.name=='posix':
                    try: os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                else: proc.kill()
                proc.communicate(); raise ValueError('Temps maximal de traitement PDF dépassé.')
            if proc.returncode: raise ValueError('PDF trop complexe ou illisible.')
        try: response=json.loads(out)
        except (ValueError,UnicodeError): raise ValueError('PDF illisible.')
        if 'error' in response: raise ValueError(response['error'])
        return response['result']
    finally: _slots.release()
