"""Contractor hardening tests — verifies strict access control for contractors.

Tests:
1. Contractor list ignores query params → always returns only their assigned tasks
2. Contractor GET /tasks/{id} for unassigned task → 404
3. Contractor POST contractor-proof for own task → 200 + status pending_manager_approval
4. Contractor POST contractor-proof for unassigned task → 404
5. Manager can see proof attachment after contractor submits

Requires the dev server running on localhost:8000 with seed data.
"""
import pytest
import httpx
import os
import sys
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

BASE = os.getenv('TEST_API_BASE', 'http://localhost:8000')


def _auth(token):
    return {'Authorization': f'Bearer {token}'}


def _login(email, password):
    r = httpx.post(f'{BASE}/api/auth/login', json={'email': email, 'password': password})
    if r.status_code != 200:
        pytest.skip(f'Login failed for {email}: {r.status_code}')
    return r.json()['token'], r.json()['user']['id']


def _get_db():
    from pymongo import MongoClient
    return MongoClient('mongodb://127.0.0.1:27017')['contractor_ops']


@pytest.fixture(scope='module')
def contractor1():
    token, uid = _login('contractor1@contractor-ops.com', 'cont123')
    return {'token': token, 'id': uid}


@pytest.fixture(scope='module')
def pm():
    token, uid = _login('pm@contractor-ops.com', 'pm123')
    return {'token': token, 'id': uid}


@pytest.fixture(scope='module')
def admin():
    token, uid = _login('admin@contractor-ops.com', 'admin123')
    return {'token': token, 'id': uid}


@pytest.fixture(scope='module')
def project_id(admin):
    r = httpx.get(f'{BASE}/api/projects', headers=_auth(admin['token']))
    assert r.status_code == 200
    projects = r.json()
    if not projects:
        pytest.skip('No projects available')
    return projects[0]['id']


@pytest.fixture(scope='module')
def contractor_tasks(contractor1, project_id):
    r = httpx.get(f'{BASE}/api/tasks', params={'project_id': project_id}, headers=_auth(contractor1['token']))
    assert r.status_code == 200
    tasks = r.json().get('items', r.json()) if isinstance(r.json(), dict) else r.json()
    if not tasks:
        pytest.skip('No tasks assigned to contractor')
    return tasks


@pytest.fixture(scope='module')
def pm_tasks(pm, project_id):
    r = httpx.get(f'{BASE}/api/tasks', params={'project_id': project_id}, headers=_auth(pm['token']))
    assert r.status_code == 200
    data = r.json()
    return data.get('items', data) if isinstance(data, dict) else data


class TestContractorListHardening:
    def test_contractor_list_only_own_tasks(self, contractor1, project_id, contractor_tasks):
        for t in contractor_tasks:
            assert t['assignee_id'] == contractor1['id']

    def test_contractor_list_ignores_assignee_param(self, contractor1, project_id):
        r = httpx.get(
            f'{BASE}/api/tasks',
            params={'project_id': project_id, 'assignee_id': 'fake-other-user-id'},
            headers=_auth(contractor1['token']),
        )
        assert r.status_code == 200
        data = r.json()
        items = data.get('items', data) if isinstance(data, dict) else data
        for t in items:
            assert t['assignee_id'] == contractor1['id']

    def test_contractor_list_no_params_still_filtered(self, contractor1, project_id):
        r = httpx.get(
            f'{BASE}/api/tasks',
            params={'project_id': project_id},
            headers=_auth(contractor1['token']),
        )
        assert r.status_code == 200
        data = r.json()
        items = data.get('items', data) if isinstance(data, dict) else data
        for t in items:
            assert t['assignee_id'] == contractor1['id']


class TestContractorTaskDetailHardening:
    def test_contractor_own_task_accessible(self, contractor1, contractor_tasks):
        own_task_id = contractor_tasks[0]['id']
        r = httpx.get(f'{BASE}/api/tasks/{own_task_id}', headers=_auth(contractor1['token']))
        assert r.status_code == 200
        assert r.json()['id'] == own_task_id

    def test_contractor_unassigned_task_returns_404(self, contractor1, pm_tasks):
        other_task = next((t for t in pm_tasks if t.get('assignee_id') != contractor1['id']), None)
        if not other_task:
            pytest.skip('All tasks assigned to contractor1')
        r = httpx.get(f'{BASE}/api/tasks/{other_task["id"]}', headers=_auth(contractor1['token']))
        assert r.status_code == 404
        assert 'לא נמצא' in r.json().get('detail', '')


class TestContractorProofWorkflow:
    """Tests proof submission + manager visibility as a single ordered workflow.
    Uses a fixture to reset one contractor task to in_progress before each test,
    and cleans up test artifacts afterward.
    """

    @pytest.fixture(autouse=True)
    def _setup_proofable_task(self, contractor1, project_id):
        db = _get_db()
        task = db.tasks.find_one({
            'project_id': project_id,
            'assignee_id': contractor1['id'],
        })
        if not task:
            pytest.skip('No contractor task found')
        self.task_id = task['id']
        self._original_status = task['status']
        db.tasks.update_one({'id': self.task_id}, {'$set': {'status': 'in_progress'}})
        db.task_updates.delete_many({'task_id': self.task_id, 'content': '__test_proof__'})
        yield
        db.tasks.update_one({'id': self.task_id}, {'$set': {'status': self._original_status}})
        db.task_updates.delete_many({'task_id': self.task_id, 'content': '__test_proof__'})

    def test_proof_submit_and_manager_visibility(self, contractor1, pm):
        """Single test: contractor submits proof → status changes → manager sees proof update."""
        file_data = ('file', ('proof.jpg', io.BytesIO(b'\xff\xd8\xff\xe0 fake jpeg'), 'image/jpeg'))
        r = httpx.post(
            f'{BASE}/api/tasks/{self.task_id}/contractor-proof',
            headers=_auth(contractor1['token']),
            files=[file_data],
            data={'note': '__test_proof__'},
        )
        assert r.status_code == 200
        body = r.json()
        assert body['success'] is True
        assert body['task']['status'] == 'pending_manager_approval'
        assert 'proof_url' in body

        r2 = httpx.get(
            f'{BASE}/api/tasks/{self.task_id}/updates',
            headers=_auth(pm['token']),
        )
        assert r2.status_code == 200
        updates = r2.json()
        proof_updates = [
            u for u in updates
            if u.get('attachment_url') and u.get('content') == '__test_proof__'
        ]
        assert len(proof_updates) == 1, 'Manager should see exactly one contractor proof update'

    def test_contractor_proof_unassigned_task_returns_404(self, contractor1, pm_tasks):
        other_task = next((t for t in pm_tasks if t.get('assignee_id') != contractor1['id']), None)
        if not other_task:
            pytest.skip('All tasks assigned to contractor1')
        file_data = ('file', ('proof.jpg', io.BytesIO(b'\xff\xd8\xff\xe0 fake jpeg'), 'image/jpeg'))
        r = httpx.post(
            f'{BASE}/api/tasks/{other_task["id"]}/contractor-proof',
            headers=_auth(contractor1['token']),
            files=[file_data],
            data={'note': '__test_proof__'},
        )
        assert r.status_code == 404
