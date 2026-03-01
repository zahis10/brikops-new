"""API-level integration tests for unit plans endpoints.

Hits real GET/POST /api/projects/{pid}/units/{uid}/plans endpoints
against the running server, validating RBAC (403), project↔unit
scoping (404), discipline validation (422), and happy-path (200).

Requires the dev server running on localhost:8000 with seed data.
"""
import pytest
import httpx
import os
import sys
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

BASE = os.getenv('TEST_API_BASE', 'http://localhost:8000')

PROJECT_A_ID = None
PROJECT_B_ID = None
UNIT_A_ID = None


def _auth(token):
    return {'Authorization': f'Bearer {token}'}


def _login(email, password):
    r = httpx.post(f'{BASE}/api/auth/login', json={'email': email, 'password': password})
    if r.status_code != 200:
        pytest.skip(f'Login failed for {email}: {r.status_code}')
    return r.json()['token']


def _get_projects(token):
    r = httpx.get(f'{BASE}/api/projects', headers=_auth(token))
    if r.status_code != 200 or not r.json():
        pytest.skip('No projects available')
    return r.json()


def _get_unit_in_project(project_id):
    from pymongo import MongoClient
    db = MongoClient('mongodb://127.0.0.1:27017')['contractor_ops']
    unit = db.units.find_one({'project_id': project_id}, {'_id': 0, 'id': 1})
    return unit['id'] if unit else None


def _make_test_file():
    return ('file', ('test_plan.pdf', io.BytesIO(b'%PDF-1.4 test content'), 'application/pdf'))


def _cleanup_test_plans():
    try:
        from pymongo import MongoClient
        db = MongoClient('mongodb://127.0.0.1:27017')['contractor_ops']
        result = db.unit_plans.delete_many({'note': {'$regex': '^__integration_test__'}})
        return result.deleted_count
    except Exception:
        return -1


@pytest.fixture(scope='module')
def admin_token():
    return _login('admin@contractor-ops.com', 'admin123')


@pytest.fixture(scope='module')
def pm_token():
    return _login('pm@contractor-ops.com', 'pm123')


@pytest.fixture(scope='module')
def contractor_token():
    return _login('contractor1@contractor-ops.com', 'cont123')


@pytest.fixture(scope='module')
def viewer_token():
    return _login('viewer@contractor-ops.com', 'view123')


@pytest.fixture(scope='module')
def mgmt_token():
    return _login('sitemanager@contractor-ops.com', 'mgmt123')


@pytest.fixture(scope='module')
def project_ids(admin_token):
    projects = _get_projects(admin_token)
    if len(projects) < 2:
        pytest.skip('Need at least 2 projects for cross-project tests')
    return projects[0]['id'], projects[1]['id']


@pytest.fixture(scope='module')
def unit_a_id(project_ids):
    uid = _get_unit_in_project(project_ids[0])
    if not uid:
        pytest.skip('No units in project A')
    return uid


@pytest.fixture(scope='module', autouse=True)
def cleanup():
    _cleanup_test_plans()
    yield
    _cleanup_test_plans()


class TestHappyPath:
    """Upload a plan and verify it appears in the list."""

    def test_admin_upload_returns_200(self, admin_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.post(
            f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans',
            headers=_auth(admin_token),
            files=[_make_test_file()],
            data={'discipline': 'electrical', 'note': '__integration_test__admin'},
        )
        assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.text}'
        body = r.json()
        assert body['discipline'] == 'electrical'
        assert body['project_id'] == pid
        assert body['unit_id'] == unit_a_id
        assert 'file_url' in body
        assert 'id' in body

    def test_list_after_upload_shows_plan(self, admin_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.get(
            f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans',
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        plans = r.json()
        assert isinstance(plans, list)
        assert len(plans) >= 1
        found = [p for p in plans if p.get('note', '').startswith('__integration_test__')]
        assert len(found) >= 1, 'Uploaded test plan not found in listing'

    def test_list_with_discipline_filter(self, admin_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.get(
            f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans',
            headers=_auth(admin_token),
            params={'discipline': 'electrical'},
        )
        assert r.status_code == 200
        plans = r.json()
        for p in plans:
            assert p['discipline'] == 'electrical'


class TestProjectUnitMismatch:
    """Unit from project A used with project B ID → 404."""

    def test_list_mismatch_returns_404(self, admin_token, project_ids, unit_a_id):
        pid_b = project_ids[1]
        r = httpx.get(
            f'{BASE}/api/projects/{pid_b}/units/{unit_a_id}/plans',
            headers=_auth(admin_token),
        )
        assert r.status_code == 404, f'Expected 404, got {r.status_code}: {r.text}'

    def test_upload_mismatch_returns_404(self, admin_token, project_ids, unit_a_id):
        pid_b = project_ids[1]
        r = httpx.post(
            f'{BASE}/api/projects/{pid_b}/units/{unit_a_id}/plans',
            headers=_auth(admin_token),
            files=[_make_test_file()],
            data={'discipline': 'plumbing', 'note': '__integration_test__mismatch'},
        )
        assert r.status_code == 404, f'Expected 404, got {r.status_code}: {r.text}'

    def test_mismatch_response_body(self, admin_token, project_ids, unit_a_id):
        pid_b = project_ids[1]
        r = httpx.get(
            f'{BASE}/api/projects/{pid_b}/units/{unit_a_id}/plans',
            headers=_auth(admin_token),
        )
        assert r.status_code == 404
        body = r.json()
        assert 'detail' in body


class TestRBACUpload:
    """Verify upload RBAC: privileged roles → 200, restricted roles → 403."""

    def test_pm_can_upload(self, pm_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.post(
            f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans',
            headers=_auth(pm_token),
            files=[_make_test_file()],
            data={'discipline': 'plumbing', 'note': '__integration_test__pm'},
        )
        assert r.status_code == 200, f'PM upload failed: {r.status_code}: {r.text}'

    def test_management_team_can_upload(self, mgmt_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.post(
            f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans',
            headers=_auth(mgmt_token),
            files=[_make_test_file()],
            data={'discipline': 'architecture', 'note': '__integration_test__mgmt'},
        )
        assert r.status_code == 200, f'Management upload failed: {r.status_code}: {r.text}'

    def test_contractor_cannot_upload(self, contractor_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.post(
            f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans',
            headers=_auth(contractor_token),
            files=[_make_test_file()],
            data={'discipline': 'electrical', 'note': '__integration_test__contractor'},
        )
        assert r.status_code == 403, f'Contractor should get 403, got {r.status_code}: {r.text}'

    def test_contractor_upload_error_body(self, contractor_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.post(
            f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans',
            headers=_auth(contractor_token),
            files=[_make_test_file()],
            data={'discipline': 'electrical', 'note': '__integration_test__contractor2'},
        )
        assert r.status_code == 403
        body = r.json()
        assert 'detail' in body


class TestRBACList:
    """All project members can list plans (200)."""

    def test_admin_can_list(self, admin_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.get(f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans', headers=_auth(admin_token))
        assert r.status_code == 200

    def test_pm_can_list(self, pm_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.get(f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans', headers=_auth(pm_token))
        assert r.status_code == 200

    def test_contractor_can_list(self, contractor_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.get(f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans', headers=_auth(contractor_token))
        assert r.status_code == 200

    def test_management_can_list(self, mgmt_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.get(f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans', headers=_auth(mgmt_token))
        assert r.status_code == 200


class TestNoAccess:
    """User with no project membership gets blocked."""

    def test_viewer_no_membership_list_blocked(self, viewer_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.get(f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans', headers=_auth(viewer_token))
        assert r.status_code == 403, f'Viewer with no membership should get 403, got {r.status_code}'

    def test_viewer_no_membership_upload_blocked(self, viewer_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.post(
            f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans',
            headers=_auth(viewer_token),
            files=[_make_test_file()],
            data={'discipline': 'electrical', 'note': '__integration_test__viewer'},
        )
        assert r.status_code == 403, f'Viewer with no membership should get 403, got {r.status_code}'

    def test_no_token_blocked(self, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.get(f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans')
        assert r.status_code in (401, 403, 422), f'No auth should be blocked, got {r.status_code}'


class TestDisciplineValidation:
    """Invalid discipline → 422."""

    def test_invalid_discipline_rejected(self, admin_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.post(
            f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans',
            headers=_auth(admin_token),
            files=[_make_test_file()],
            data={'discipline': 'invalid_discipline', 'note': '__integration_test__bad_disc'},
        )
        assert r.status_code == 422, f'Invalid discipline should get 422, got {r.status_code}: {r.text}'

    def test_empty_discipline_rejected(self, admin_token, project_ids, unit_a_id):
        pid = project_ids[0]
        r = httpx.post(
            f'{BASE}/api/projects/{pid}/units/{unit_a_id}/plans',
            headers=_auth(admin_token),
            files=[_make_test_file()],
            data={'discipline': '', 'note': '__integration_test__empty_disc'},
        )
        assert r.status_code == 422, f'Empty discipline should get 422, got {r.status_code}'
