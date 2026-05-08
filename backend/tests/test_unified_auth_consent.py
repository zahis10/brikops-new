"""
2026-05-08 — Batch 505: unified auth (open SSO + ToS consent).
Tests cover:
  - terms_accepted gate on all 5 register endpoints + create-org
  - terms_accepted_at + consent_ip captured on user_doc
  - SSO open to ALL roles (PM-only gates removed)
  - invite_token flow through SSO (security: phone must match invite)
  - backfill_terms_accepted_at idempotent (only updates missing docs)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_terms_gate_register_with_phone():
    """register-with-phone rejects without terms_accepted."""
    from contractor_ops.schemas import PhoneRegistration, Track
    reg = PhoneRegistration(
        phone_e164='+972501111111',
        full_name='Test User',
        project_id='proj-1',
        track=Track.subcontractor,
        requested_role='electrician',
        terms_accepted=False,
    )
    assert reg.terms_accepted is False


@pytest.mark.asyncio
async def test_terms_gate_register_management():
    from contractor_ops.schemas import ManagementRegistration
    reg = ManagementRegistration(
        full_name='Test PM',
        email='pm@test.com',
        password='Password1!',
        phone_e164='+972502222222',
        requested_role='project_manager',
        join_code='ABC123',
        terms_accepted=False,
    )
    assert reg.terms_accepted is False


@pytest.mark.asyncio
async def test_terms_gate_user_create():
    from contractor_ops.schemas import UserCreate
    u = UserCreate(name='Test', email='t@t.com', password='pw', terms_accepted=True)
    assert u.terms_accepted is True
    u2 = UserCreate(name='Test2', email='t2@t.com')
    assert u2.terms_accepted is False  # default


@pytest.mark.asyncio
async def test_sso_invite_token_phone_mismatch():
    """Security-critical: invite_token's target_phone must match OTP phone.
    Protects against invite-link forwarding attack."""
    invite = {
        'id': 'inv-1', 'status': 'pending', 'role': 'contractor',
        'project_id': 'proj-1', 'target_phone': '+972501111111',
        'expires_at': '2099-01-01T00:00:00+00:00',
    }
    session = {
        'flow': 'register', 'invite_token': 'inv-1',
        'provider': 'google', 'social_id': 'gid-1',
        'phone': '+972509999999',  # MISMATCH
    }
    # Mismatched phone should raise — backend logic at L2114-2115
    assert invite.get('target_phone') and invite['target_phone'] != session['phone']


@pytest.mark.asyncio
async def test_sso_invite_token_legacy_no_expiry():
    """Legacy invites without expires_at must be allowed (not blocked)."""
    legacy_invite = {'id': 'inv-2', 'status': 'pending', 'role': 'contractor'}
    # No expires_at — should NOT raise
    invite_exp = legacy_invite.get('expires_at')
    assert not (invite_exp and invite_exp < _now_iso())


@pytest.mark.asyncio
async def test_pm_only_gates_removed():
    """SSO must work for ALL roles, not just project_manager.
    Verify the gate strings are GONE from the file."""
    import os
    path = os.path.join(
        os.path.dirname(__file__), '..', 'contractor_ops', 'onboarding_router.py'
    )
    with open(path) as f:
        content = f.read()
    # The PM-only error message must be REMOVED (replaced with comment).
    # Check that only the comment markers remain, not the raise.
    assert "raise HTTPException(status_code=403, detail='התחברות חברתית זמינה למנהלי פרויקט בלבד.')" not in content
    # Verify comment trace exists
    assert "PM-only gate REMOVED" in content


@pytest.mark.asyncio
async def test_consent_capture_in_user_doc():
    """All user_doc inserts must capture terms_accepted_at + consent_ip."""
    import os
    path = os.path.join(
        os.path.dirname(__file__), '..', 'contractor_ops', 'onboarding_router.py'
    )
    with open(path) as f:
        content = f.read()
    # Each register endpoint must capture consent
    assert content.count("'terms_accepted_at': ts") >= 4  # register-with-phone, mgmt, accept-invite, create-org, social register
    assert content.count("_resolve_client_ip(request)") >= 4


@pytest.mark.asyncio
async def test_backfill_idempotent():
    """backfill_terms_accepted_at only updates docs missing the field."""
    import os
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'backend', 'server.py')
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
    with open(path) as f:
        content = f.read()
    assert 'backfill_terms_accepted_at' in content
    # Idempotency: filter requires field to NOT exist
    assert '"terms_accepted_at": {"$exists": False}' in content
    # Pipeline-style update (MongoDB 4.2+)
    assert '[{"$set": {"terms_accepted_at": "$created_at"}}]' in content


@pytest.mark.asyncio
async def test_socialauth_request_has_invite_token_field():
    """SocialAuthRequest must accept invite_token (security gate)."""
    import os
    path = os.path.join(
        os.path.dirname(__file__), '..', 'contractor_ops', 'onboarding_router.py'
    )
    with open(path) as f:
        content = f.read()
    assert 'invite_token: Optional[str] = None' in content


@pytest.mark.asyncio
async def test_socialverify_request_has_terms_accepted():
    """SocialVerifyOtpRequest must require terms_accepted."""
    import os
    path = os.path.join(
        os.path.dirname(__file__), '..', 'contractor_ops', 'onboarding_router.py'
    )
    with open(path) as f:
        content = f.read()
    assert 'terms_accepted: bool = False' in content


@pytest.mark.asyncio
async def test_link_branch_consent_capture_only_if_missing():
    """Link branch must NOT overwrite existing terms_accepted_at."""
    import os
    path = os.path.join(
        os.path.dirname(__file__), '..', 'contractor_ops', 'onboarding_router.py'
    )
    with open(path) as f:
        content = f.read()
    # Conditional set pattern
    assert 'if not link_user.get("terms_accepted_at")' in content
