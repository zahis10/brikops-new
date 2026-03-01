"""Regression test: invite contractor with custom project trade_key.

Bug fixed in M4.6: POST /api/projects/{id}/invites rejected custom
project-level trade_key values (e.g. "מעליות") because validation
only checked BUCKET_LABELS (14 global trades). Now it also checks
the project_trades collection.

Additional isolation test: a custom trade created in Project A must
NOT be accepted when inviting in Project B.

Deterministic phones: each test uses a unique phone with the prefix
+972508880xxx. A setup fixture cleans up matching invites in MongoDB
before the run so tests are idempotent.
"""
import pytest
import httpx
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

BASE = os.getenv('TEST_API_BASE', 'http://localhost:8000')
PHONE_PREFIX = '+972508880'
TEST_TRADE = 'בדיקת_regression'


def _phone(suffix: int) -> str:
    return f'{PHONE_PREFIX}{suffix:03d}'


def _auth(token):
    return {'Authorization': f'Bearer {token}'}


def _login(email, password):
    r = httpx.post(f'{BASE}/api/auth/login', json={'email': email, 'password': password})
    if r.status_code != 200:
        pytest.skip(f'Login failed for {email}: {r.status_code}')
    return r.json()['token']


def _get_first_project(token):
    r = httpx.get(f'{BASE}/api/projects', headers=_auth(token))
    if r.status_code != 200 or not r.json():
        pytest.skip('No projects available')
    return r.json()[0]['id']


def _cleanup_test_invites():
    """Remove invites with our test phone prefix directly from MongoDB."""
    try:
        from pymongo import MongoClient
        db = MongoClient('mongodb://127.0.0.1:27017')['contractor_ops']
        result = db.invites.delete_many({
            'target_phone': {'$regex': f'^\\{PHONE_PREFIX}'}
        })
        return result.deleted_count
    except Exception:
        return -1


@pytest.fixture(scope='module')
def admin_token():
    return _login('admin@contractor-ops.com', 'admin123')


@pytest.fixture(scope='module')
def project_a(admin_token):
    return _get_first_project(admin_token)


@pytest.fixture(scope='module')
def project_b(admin_token):
    """Create (or reuse) a second project for isolation tests."""
    r = httpx.get(f'{BASE}/api/projects', headers=_auth(admin_token))
    projects = r.json() if r.status_code == 200 else []
    if len(projects) >= 2:
        return projects[1]['id']
    r = httpx.post(
        f'{BASE}/api/projects',
        headers=_auth(admin_token),
        json={
            'name': 'פרויקט isolation test',
            'code': 'ISO-001',
            'description': 'isolation regression',
            'client_name': 'test',
            'start_date': '2026-01-01',
            'end_date': '2027-01-01',
        },
    )
    if r.status_code not in (200, 201):
        pytest.skip(f'Cannot create project B: {r.status_code}')
    return r.json()['id']


@pytest.fixture(scope='module')
def custom_trade_key(admin_token, project_a):
    r = httpx.post(
        f'{BASE}/api/projects/{project_a}/trades',
        headers=_auth(admin_token),
        json={'label_he': TEST_TRADE},
    )
    if r.status_code == 409:
        return TEST_TRADE
    assert r.status_code == 200
    return r.json()['key']


@pytest.fixture(scope='module', autouse=True)
def cleanup_before_and_after():
    """Clean test invites from DB before and after test run."""
    _cleanup_test_invites()
    yield
    _cleanup_test_invites()


class TestInviteCustomTrade:
    """Regression: invite endpoint must accept custom project trade keys."""

    def test_invite_with_custom_project_trade_succeeds(self, admin_token, project_a, custom_trade_key):
        r = httpx.post(
            f'{BASE}/api/projects/{project_a}/invites',
            headers=_auth(admin_token),
            json={
                'phone': _phone(1),
                'full_name': 'קבלן regression',
                'role': 'contractor',
                'trade_key': custom_trade_key,
            },
        )
        assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.text}'
        data = r.json()
        assert data['trade_key'] == custom_trade_key
        assert data['role'] == 'contractor'

    def test_invite_with_global_trade_still_works(self, admin_token, project_a):
        r = httpx.post(
            f'{BASE}/api/projects/{project_a}/invites',
            headers=_auth(admin_token),
            json={
                'phone': _phone(2),
                'full_name': 'קבלן גלובלי',
                'role': 'contractor',
                'trade_key': 'electrical',
            },
        )
        assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.text}'

    def test_invite_with_nonexistent_trade_rejected(self, admin_token, project_a):
        r = httpx.post(
            f'{BASE}/api/projects/{project_a}/invites',
            headers=_auth(admin_token),
            json={
                'phone': _phone(3),
                'full_name': 'קבלן שגוי',
                'role': 'contractor',
                'trade_key': 'nonexistent_trade_xyz_999',
            },
        )
        assert r.status_code == 422
        assert 'מקצוע לא תקין' in r.json()['detail']

    def test_invite_contractor_without_trade_rejected(self, admin_token, project_a):
        r = httpx.post(
            f'{BASE}/api/projects/{project_a}/invites',
            headers=_auth(admin_token),
            json={
                'phone': _phone(4),
                'full_name': 'קבלן בלי מקצוע',
                'role': 'contractor',
            },
        )
        assert r.status_code == 422
        assert 'מקצוע הוא שדה חובה' in r.json()['detail']


class TestInviteTradeIsolation:
    """Custom trade in Project A must NOT be valid for invites in Project B."""

    def test_custom_trade_from_project_a_rejected_in_project_b(
        self, admin_token, project_a, project_b, custom_trade_key
    ):
        assert project_a != project_b, 'Need two distinct projects for isolation test'

        trades_b = httpx.get(
            f'{BASE}/api/projects/{project_b}/trades',
            headers=_auth(admin_token),
        ).json().get('trades', [])
        assert not any(
            t['key'] == custom_trade_key for t in trades_b
        ), f'Trade {custom_trade_key} should not exist in Project B'

        r = httpx.post(
            f'{BASE}/api/projects/{project_b}/invites',
            headers=_auth(admin_token),
            json={
                'phone': _phone(5),
                'full_name': 'קבלן isolation',
                'role': 'contractor',
                'trade_key': custom_trade_key,
            },
        )
        assert r.status_code == 422, (
            f'Project-B invite with Project-A trade should be 422, got {r.status_code}: {r.text}'
        )
        assert 'מקצוע לא תקין' in r.json()['detail']

    def test_global_trade_works_in_project_b(self, admin_token, project_b):
        r = httpx.post(
            f'{BASE}/api/projects/{project_b}/invites',
            headers=_auth(admin_token),
            json={
                'phone': _phone(6),
                'full_name': 'קבלן גלובלי B',
                'role': 'contractor',
                'trade_key': 'plumbing',
            },
        )
        assert r.status_code == 200, f'Global trade should work in any project, got {r.status_code}: {r.text}'
