from datetime import date, timedelta
from app.main import status

def test_status():
    assert status((date.today()-timedelta(days=1)).isoformat()) == 'expired'
    assert status(date.today().isoformat()) == 'soon'
    assert status((date.today()+timedelta(days=30)).isoformat()) == 'soon'
    assert status((date.today()+timedelta(days=31)).isoformat()) == 'valid'
