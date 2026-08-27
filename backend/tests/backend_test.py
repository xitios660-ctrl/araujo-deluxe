import os
import pytest
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://dente-preview.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"
TZ = ZoneInfo("America/Sao_Paulo")
ADMIN_PASSWORD = "1234"


def _next_weekday_date(target_weekday=None):
    """Return next date (YYYY-MM-DD) that is a business day. target_weekday: 0..5"""
    now = datetime.now(TZ)
    for i in range(1, 30):
        d = now + timedelta(days=i)
        if d.weekday() != 6:  # not Sunday
            if target_weekday is None or d.weekday() == target_weekday:
                return d.strftime("%Y-%m-%d")
    return None


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


# --- Public: services ---
def test_services_list():
    r = requests.get(f"{API}/services")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 10
    cats = {s["category"] for s in data}
    assert {"cilios", "sobrancelhas", "unhas"}.issubset(cats)
    for s in data:
        assert "price" in s and isinstance(s["price"], (int, float))


# --- Business hours ---
def test_business_hours():
    r = requests.get(f"{API}/business-hours")
    assert r.status_code == 200
    j = r.json()
    assert j["timezone"] == "America/Sao_Paulo"
    days = {d["weekday"]: d for d in j["days"]}
    assert days[0]["slots"] == ["09:00", "11:00", "15:30", "17:00"]
    assert days[5]["slots"] == ["09:00", "11:00", "14:00", "16:00", "18:00"]
    assert days[6]["slots"] == []
    assert days[6]["open"] is False


# --- Availability ---
def test_availability_weekday():
    d = _next_weekday_date(target_weekday=0)  # next Monday
    r = requests.get(f"{API}/availability", params={"date": d})
    assert r.status_code == 200
    j = r.json()
    assert j["open"] is True
    times = [s["time"] for s in j["slots"]]
    assert times == ["09:00", "11:00", "15:30", "17:00"]


def test_availability_sunday_closed():
    now = datetime.now(TZ)
    # find next Sunday
    for i in range(1, 15):
        d = now + timedelta(days=i)
        if d.weekday() == 6:
            date_str = d.strftime("%Y-%m-%d")
            break
    r = requests.get(f"{API}/availability", params={"date": date_str})
    assert r.status_code == 200
    j = r.json()
    assert j["open"] is False
    assert j["slots"] == []


def test_availability_invalid_date():
    r = requests.get(f"{API}/availability", params={"date": "invalid"})
    assert r.status_code == 400


# --- Booking creation + double-booking ---
@pytest.fixture(scope="module")
def booking_slot():
    """Find a future date+time not already booked."""
    now = datetime.now(TZ)
    for i in range(2, 40):
        d = now + timedelta(days=i)
        if d.weekday() == 6:
            continue
        date_str = d.strftime("%Y-%m-%d")
        r = requests.get(f"{API}/availability", params={"date": date_str})
        j = r.json()
        for s in j["slots"]:
            if s["available"]:
                return date_str, s["time"]
    pytest.skip("No available slot found")


def test_create_booking_and_double_book(booking_slot):
    date_str, time_str = booking_slot
    payload = {
        "service_id": "designer-simples",
        "date": date_str,
        "time": time_str,
        "client_name": "TEST_Cliente",
        "client_phone": "11987654321",
        "notes": "teste automatizado",
    }
    r = requests.post(f"{API}/bookings", json=payload)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["service_id"] == "designer-simples"
    assert j["date"] == date_str and j["time"] == time_str
    assert j["code"].startswith("AD-")
    assert j["status"] in ("pendente", "confirmada")
    # Second attempt same slot -> 409
    r2 = requests.post(f"{API}/bookings", json=payload)
    assert r2.status_code == 409, f"expected 409, got {r2.status_code}: {r2.text}"


def test_create_booking_invalid_service():
    d = _next_weekday_date()
    r = requests.post(f"{API}/bookings", json={
        "service_id": "nao-existe",
        "date": d,
        "time": "09:00",
        "client_name": "TEST_X",
        "client_phone": "11987654321",
    })
    assert r.status_code == 404


# --- Auth ---
def test_login_wrong_password():
    r = requests.post(f"{API}/auth/login", json={"password": "wrong-xyz-999"})
    assert r.status_code in (401, 429)


def test_login_success_returns_token():
    r = requests.post(f"{API}/auth/login", json={"password": ADMIN_PASSWORD})
    assert r.status_code == 200
    j = r.json()
    assert "access_token" in j and isinstance(j["access_token"], str)
    assert j["user"]["role"] == "admin"


# --- Admin endpoints protected ---
def test_admin_bookings_requires_auth():
    r = requests.get(f"{API}/admin/bookings")
    assert r.status_code == 401


def test_admin_stats_requires_auth():
    r = requests.get(f"{API}/admin/stats")
    assert r.status_code == 401


def test_admin_bookings_with_token(admin_token):
    r = requests.get(f"{API}/admin/bookings", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_admin_stats_with_token(admin_token):
    r = requests.get(f"{API}/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    j = r.json()
    for k in ("today", "upcoming", "pending", "month_revenue", "total_clients"):
        assert k in j


def test_admin_agenda_with_token(admin_token):
    d = _next_weekday_date()
    r = requests.get(f"{API}/admin/agenda", params={"date": d},
                     headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    j = r.json()
    assert j["date"] == d and "slots" in j
