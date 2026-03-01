"""Phone change tests: admin recovery + self-serve OTP flow + conflict checks."""
import pytest
import httpx
import uuid

BASE = "http://localhost:8000"


def _login(email, password):
    r = httpx.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        pytest.skip(f"Cannot login as {email}")
    data = r.json()
    user = data.get("user", {})
    user['platform_role'] = data.get('platform_role', user.get('platform_role', 'none'))
    return {"Authorization": f"Bearer {data['token']}"}, user


@pytest.fixture(scope="module")
def super_admin():
    headers, user = _login("superadmin@brikops.dev", "super123")
    if user.get('platform_role') != 'super_admin':
        pytest.skip("Super admin not available")
    return headers, user


@pytest.fixture(scope="module")
def pm():
    headers, user = _login("pm@contractor-ops.com", "pm123")
    return headers, user


@pytest.fixture(scope="module")
def contractor():
    headers, user = _login("contractor1@contractor-ops.com", "cont123")
    return headers, user


class TestAdminUsersAPI:

    def test_admin_list_users(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/users", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert 'users' in data
        assert 'total' in data
        assert data['total'] > 0

    def test_admin_list_users_search(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/users?q=pm", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert 'users' in data

    def test_admin_get_user_detail(self, super_admin, pm):
        headers, _ = super_admin
        _, pm_user = pm
        r = httpx.get(f"{BASE}/api/admin/users/{pm_user['id']}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert 'org_memberships' in data
        assert 'project_memberships' in data

    def test_admin_users_blocked_for_non_admin(self, pm):
        headers, _ = pm
        r = httpx.get(f"{BASE}/api/admin/users", headers=headers)
        assert r.status_code == 403

    def test_admin_user_detail_blocked_for_non_admin(self, pm, contractor):
        headers, _ = pm
        _, cont_user = contractor
        r = httpx.get(f"{BASE}/api/admin/users/{cont_user['id']}", headers=headers)
        assert r.status_code == 403


class TestAdminPhoneChange:

    def test_admin_change_phone_requires_note(self, super_admin, contractor):
        headers, _ = super_admin
        _, cont_user = contractor
        r = httpx.put(
            f"{BASE}/api/admin/users/{cont_user['id']}/phone",
            json={"phone": "0509999999", "note": ""},
            headers=headers,
        )
        assert r.status_code == 400
        assert 'סיבה' in r.json()['detail']

    def test_admin_change_phone_conflict_409(self, super_admin, pm, contractor):
        headers, _ = super_admin
        _, pm_user = pm
        _, cont_user = contractor
        pm_phone = pm_user.get('phone_e164') or pm_user.get('phone')
        if not pm_phone:
            pytest.skip("PM has no phone")
        r = httpx.put(
            f"{BASE}/api/admin/users/{cont_user['id']}/phone",
            json={"phone": pm_phone, "note": "test conflict"},
            headers=headers,
        )
        assert r.status_code == 409
        assert 'כבר קיים' in r.json()['detail']

    def test_admin_change_phone_blocked_for_non_admin(self, pm, contractor):
        headers, _ = pm
        _, cont_user = contractor
        r = httpx.put(
            f"{BASE}/api/admin/users/{cont_user['id']}/phone",
            json={"phone": "0501111111", "note": "test"},
            headers=headers,
        )
        assert r.status_code == 403


class TestSelfServePhoneChange:

    def test_self_serve_request_otp(self, pm):
        headers, _ = pm
        unique_phone = f"054{str(uuid.uuid4().int)[:7]}"
        r = httpx.post(
            f"{BASE}/api/auth/change-phone/request",
            json={"phone": unique_phone},
            headers=headers,
        )
        assert r.status_code == 200

    def test_self_serve_conflict_409(self, pm, super_admin):
        headers, _ = pm
        _, sa_user = super_admin
        sa_phone = sa_user.get('phone_e164')
        if not sa_phone:
            pytest.skip("Super admin has no phone")
        r = httpx.post(
            f"{BASE}/api/auth/change-phone/request",
            json={"phone": sa_phone},
            headers=headers,
        )
        assert r.status_code == 409
        assert 'כבר רשום' in r.json()['detail']

    def test_self_serve_verify_bad_code(self, pm):
        headers, _ = pm
        r = httpx.post(
            f"{BASE}/api/auth/change-phone/verify",
            json={"phone": "0541234567", "code": "000000"},
            headers=headers,
        )
        assert r.status_code in (400, 422)

    def test_self_serve_requires_auth(self):
        r = httpx.post(
            f"{BASE}/api/auth/change-phone/request",
            json={"phone": "0541234567"},
        )
        assert r.status_code in (401, 403)

    def test_verify_returns_force_logout(self, pm):
        headers, _ = pm
        unique_phone = f"054{uuid.uuid4().hex[:7]}"
        httpx.post(
            f"{BASE}/api/auth/change-phone/request",
            json={"phone": unique_phone},
            headers=headers,
        )
        r = httpx.post(
            f"{BASE}/api/auth/change-phone/verify",
            json={"phone": unique_phone, "code": "123456"},
            headers=headers,
        )
        if r.status_code == 200:
            assert r.json().get('force_logout') is True


class TestRBACvsBilling:

    def test_viewer_gets_403_not_402_on_write(self):
        """Viewer must get 403 (RBAC) not 402 (billing) on write endpoints."""
        r = httpx.post(f"{BASE}/api/auth/login", json={
            "email": "viewer@contractor-ops.com", "password": "view123"
        })
        if r.status_code != 200:
            pytest.skip("Viewer login failed")
        viewer_headers = {"Authorization": f"Bearer {r.json()['token']}"}
        r2 = httpx.post(f"{BASE}/api/projects", json={
            "name": "RBAC test", "code": f"RT{uuid.uuid4().hex[:4].upper()}"
        }, headers=viewer_headers)
        assert r2.status_code == 403, f"Expected 403, got {r2.status_code}. Viewer should get RBAC block, not billing."
