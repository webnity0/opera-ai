# Never run automated tests against a deployment database.
import os
import tempfile
from pathlib import Path
import atexit
_tmp = tempfile.TemporaryDirectory(prefix='opera-test-')
atexit.register(_tmp.cleanup)
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_tmp.name) / 'test.db')
os.environ['COOKIE_SECURE'] = '0'
os.environ.pop('RENDER', None)

import pytest
@pytest.fixture(autouse=True)
def reset_test_rate_limits():
    from app.main import _attempts
    _attempts.clear()
