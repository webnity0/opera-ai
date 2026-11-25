"""Bound PDF parsing resources in a child process; not a full sandbox."""
import json, sys

def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768*1024**2,768*1024**2))
        resource.setrlimit(resource.RLIMIT_CPU,(20,22))
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    except ImportError:
        pass
    from .pdf_tools import analyze_pdf, validate_pdf, MAX_BYTES
    try:
        data=sys.stdin.buffer.read(MAX_BYTES+1)
        result=analyze_pdf(data) if sys.argv[1]=='analyze' else bool(validate_pdf(data))
        print(json.dumps({'result':result}))
    except ValueError as e:
        print(json.dumps({'error':str(e)}))

if __name__=='__main__': main()
