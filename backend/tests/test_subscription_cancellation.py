"""Tests for subscription cancel + reactivate endpoints."""
import asyncio
import sys
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/home/runner/workspace/backend")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _future_iso(days=30):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _past_iso(days=5):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


class StubRequest:
    """Minimal stub for FastAPI Request — only .json() is awaited."""
    def __init__(self, body_dict=None):
        self._body = body_dict or {}

    async def json(self):
        return self._body


def _make_super_admin_user(uid="test-cancel-sa"):
    return {
        "id": uid,
        "email": f"{uid}@local",
        "platform_role": "super_admin",
        "role": "super_admin",
    }


def _make_plain_user(uid="test-cancel-plain"):
    return {
        "id": uid,
        "email": f"{uid}@local",
        "platform_role": "none",
        "role": "user",
    }


def _enable_billing_v1(monkeypatch):
    from contractor_ops import billing as billing_module
    monkeypatch.setattr(billing_module, "BILLING_V1_ENABLED", True, raising=False)


def _seed_org(sync_db, org_id):
    sync_db.organizations.update_one(
        {"id": org_id},
        {"$set": {"id": org_id, "name": f"TestOrg-{org_id}", "billing": {}, "tax_id": ""}},
        upsert=True,
    )


def _seed_active_sub(sync_db, org_id, paid_until, auto_renew=True, cancelled_at=None, expires_at=None, plan_id="standard"):
    doc = {
        "id": f"sub-{org_id}",
        "org_id": org_id,
        "plan_id": plan_id,
        "status": "active",
        "auto_renew": auto_renew,
        "paid_until": paid_until,
    }
    if cancelled_at is not None:
        doc["cancelled_at"] = cancelled_at
    if expires_at is not None:
        doc["expires_at"] = expires_at
    sync_db.subscriptions.update_one(
        {"org_id": org_id},
        {"$set": doc},
        upsert=True,
    )


def _cleanup(sync_db, org_id):
    sync_db.subscriptions.delete_many({"org_id": org_id})
    sync_db.organizations.delete_many({"id": org_id})
    sync_db.audit_events.delete_many({"org_id": org_id})


def _wire_mdb(set_billing_db, set_router_db):
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
    mdb = client["contractor_ops"]
    set_billing_db(mdb)
    set_router_db(mdb)
    return mdb

def test_cancel_sets_auto_renew_to_false_and_expires_at(monkeypatch):
    _enable_billing_v1(monkeypatch)
    from contractor_ops import billing_router as br
    from contractor_ops.billing import set_billing_db
    from contractor_ops.router import set_db as set_router_db

    sync_db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    org_id = "test-cancel-1-sets-fields"
    paid_until = _future_iso(30)
    _cleanup(sync_db, org_id)
    _seed_org(sync_db, org_id)
    _seed_active_sub(sync_db, org_id, paid_until=paid_until, auto_renew=True)

    user = _make_super_admin_user("test-cancel-1-sa")

    async def run():
        _wire_mdb(set_billing_db, set_router_db)
        result = await br.billing_cancel_subscription(
            org_id, StubRequest({"reason": "test cancel 1"}), user=user
        )
        assert result.get("cancelled_at"), "cancelled_at missing in response"
        assert result.get("access_until") == paid_until, (
            f"access_until should be paid_until, got {result.get('access_until')!r} vs {paid_until!r}"
        )

    try:
        asyncio.run(run())
        sub = sync_db.subscriptions.find_one({"org_id": org_id})
        assert sub is not None, "sub disappeared"
        assert sub.get("auto_renew") is False, f"auto_renew should be False, got {sub.get('auto_renew')!r}"
        assert sub.get("cancelled_at"), "cancelled_at not persisted"
        assert sub.get("expires_at") == paid_until, (
            f"expires_at should snapshot paid_until, got {sub.get('expires_at')!r}"
        )
        assert sub.get("cancelled_reason") == "test cancel 1"
    finally:
        _cleanup(sync_db, org_id)

def test_cancel_does_NOT_call_payplus_api(monkeypatch):
    _enable_billing_v1(monkeypatch)
    from contractor_ops import billing_router as br
    from contractor_ops import payplus_service
    from contractor_ops.billing import set_billing_db
    from contractor_ops.router import set_db as set_router_db

    def _fail_loudly(*args, **kwargs):
        raise AssertionError("PayPlus API must NOT be called during cancellation")

    monkeypatch.setattr(payplus_service, "charge_token", _fail_loudly, raising=False)
    if hasattr(payplus_service, "create_payment_page"):
        monkeypatch.setattr(payplus_service, "create_payment_page", _fail_loudly, raising=False)
    if hasattr(payplus_service, "verify_webhook_signature"):
        monkeypatch.setattr(payplus_service, "verify_webhook_signature", _fail_loudly, raising=False)

    sync_db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    org_id = "test-cancel-2-no-payplus"
    _cleanup(sync_db, org_id)
    _seed_org(sync_db, org_id)
    _seed_active_sub(sync_db, org_id, paid_until=_future_iso(30), auto_renew=True)

    user = _make_super_admin_user("test-cancel-2-sa")

    async def run():
        _wire_mdb(set_billing_db, set_router_db)
        result = await br.billing_cancel_subscription(
            org_id, StubRequest({"reason": ""}), user=user
        )
        assert result.get("cancelled_at"), "cancellation failed unexpectedly"

    try:
        asyncio.run(run())
    finally:
        _cleanup(sync_db, org_id)

def test_cancel_inserts_audit_event_with_reason(monkeypatch):
    _enable_billing_v1(monkeypatch)
    from contractor_ops import billing_router as br
    from contractor_ops.billing import set_billing_db
    from contractor_ops.router import set_db as set_router_db

    sync_db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    org_id = "test-cancel-3-audit"
    _cleanup(sync_db, org_id)
    _seed_org(sync_db, org_id)
    _seed_active_sub(sync_db, org_id, paid_until=_future_iso(30), auto_renew=True)

    user = _make_super_admin_user("test-cancel-3-sa")
    reason_text = "too expensive"

    async def run():
        _wire_mdb(set_billing_db, set_router_db)
        await br.billing_cancel_subscription(
            org_id, StubRequest({"reason": reason_text}), user=user
        )

    try:
        asyncio.run(run())
        events = list(sync_db.audit_events.find({
            "org_id": org_id,
            "event_type": "subscription_cancelled",
        }))
        assert len(events) >= 1, f"expected ≥1 subscription_cancelled audit_event, got {len(events)}"
        details = events[0].get("details", {})
        assert details.get("reason") == reason_text, (
            f"audit_event.details.reason should be {reason_text!r}, got {details.get('reason')!r}"
        )
        assert details.get("sub_id") == f"sub-{org_id}"
        assert details.get("plan_id") == "standard"
        assert events[0].get("user_id") == user["id"]
    finally:
        _cleanup(sync_db, org_id)

def test_cancel_idempotent_on_already_cancelled(monkeypatch):
    _enable_billing_v1(monkeypatch)
    from contractor_ops import billing_router as br
    from contractor_ops.billing import set_billing_db
    from contractor_ops.router import set_db as set_router_db

    sync_db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    org_id = "test-cancel-4-idempotent"
    paid_until = _future_iso(30)
    cancelled_at = _now_iso()
    _cleanup(sync_db, org_id)
    _seed_org(sync_db, org_id)
    _seed_active_sub(
        sync_db, org_id,
        paid_until=paid_until,
        auto_renew=False,
        cancelled_at=cancelled_at,
        expires_at=paid_until,
    )

    user = _make_super_admin_user("test-cancel-4-sa")

    async def run():
        _wire_mdb(set_billing_db, set_router_db)
        result = await br.billing_cancel_subscription(
            org_id, StubRequest({"reason": "second call"}), user=user
        )
        assert result.get("already_cancelled") is True, (
            f"second cancel should return already_cancelled=True, got {result!r}"
        )
        assert result.get("cancelled_at") == cancelled_at
        assert result.get("access_until") == paid_until

    try:
        asyncio.run(run())
        sub = sync_db.subscriptions.find_one({"org_id": org_id})
        assert sub.get("cancelled_reason") in (None, "", "too expensive"), (
            "second cancel must NOT overwrite cancelled_reason"
        )
        assert sub.get("cancelled_at") == cancelled_at, (
            "second cancel must NOT overwrite cancelled_at"
        )
    finally:
        _cleanup(sync_db, org_id)

def test_cancel_blocked_for_non_billing_admin(monkeypatch):
    _enable_billing_v1(monkeypatch)
    from fastapi import HTTPException
    from contractor_ops import billing_router as br
    from contractor_ops.billing import set_billing_db
    from contractor_ops.router import set_db as set_router_db

    sync_db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    org_id = "test-cancel-5-rbac"
    user = _make_plain_user("test-cancel-5-plain")
    _cleanup(sync_db, org_id)
    sync_db.organization_memberships.delete_many({"user_id": user["id"], "org_id": org_id})
    _seed_org(sync_db, org_id)
    _seed_active_sub(sync_db, org_id, paid_until=_future_iso(30), auto_renew=True)

    async def run():
        _wire_mdb(set_billing_db, set_router_db)
        try:
            await br.billing_cancel_subscription(
                org_id, StubRequest({"reason": ""}), user=user
            )
        except HTTPException as e:
            assert e.status_code == 403, f"expected 403, got {e.status_code} ({e.detail!r})"
            return
        raise AssertionError("cancel must raise 403 for plain user with no billing role")

    try:
        asyncio.run(run())
    finally:
        _cleanup(sync_db, org_id)
        sync_db.organization_memberships.delete_many({"user_id": user["id"], "org_id": org_id})

def test_reactivate_before_expiry_works(monkeypatch):
    _enable_billing_v1(monkeypatch)
    from contractor_ops import billing_router as br
    from contractor_ops.billing import set_billing_db
    from contractor_ops.router import set_db as set_router_db

    sync_db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    org_id = "test-reactivate-6"
    paid_until = _future_iso(30)
    _cleanup(sync_db, org_id)
    _seed_org(sync_db, org_id)
    _seed_active_sub(
        sync_db, org_id,
        paid_until=paid_until,
        auto_renew=False,
        cancelled_at=_now_iso(),
        expires_at=paid_until,
    )

    user = _make_super_admin_user("test-reactivate-6-sa")

    async def run():
        _wire_mdb(set_billing_db, set_router_db)
        result = await br.billing_reactivate_subscription(
            org_id, StubRequest({}), user=user
        )
        assert result.get("reactivated_at"), "reactivated_at missing"
        assert result.get("next_charge_date") == paid_until

    try:
        asyncio.run(run())
        sub = sync_db.subscriptions.find_one({"org_id": org_id})
        assert sub.get("auto_renew") is True, f"auto_renew should be True, got {sub.get('auto_renew')!r}"
        assert "cancelled_at" not in sub, f"cancelled_at should be unset, got {sub.get('cancelled_at')!r}"
        assert "cancelled_reason" not in sub, "cancelled_reason should be unset"
        assert "expires_at" not in sub, "expires_at should be unset"
    finally:
        _cleanup(sync_db, org_id)

def test_reactivate_after_expiry_returns_410(monkeypatch):
    _enable_billing_v1(monkeypatch)
    from fastapi import HTTPException
    from contractor_ops import billing_router as br
    from contractor_ops.billing import set_billing_db
    from contractor_ops.router import set_db as set_router_db

    sync_db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    org_id = "test-reactivate-7-expired"
    expired_at = _past_iso(5)
    _cleanup(sync_db, org_id)
    _seed_org(sync_db, org_id)
    _seed_active_sub(
        sync_db, org_id,
        paid_until=expired_at,
        auto_renew=False,
        cancelled_at=_past_iso(35),
        expires_at=expired_at,
    )

    user = _make_super_admin_user("test-reactivate-7-sa")

    async def run():
        _wire_mdb(set_billing_db, set_router_db)
        try:
            await br.billing_reactivate_subscription(
                org_id, StubRequest({}), user=user
            )
        except HTTPException as e:
            assert e.status_code == 410, f"expected 410, got {e.status_code} ({e.detail!r})"
            assert "פג" in str(e.detail), f"detail should mention expired, got {e.detail!r}"
            return
        raise AssertionError("reactivate must raise 410 Gone for expired sub")

    try:
        asyncio.run(run())
    finally:
        _cleanup(sync_db, org_id)


def test_renewal_cron_skips_cancelled_subs(monkeypatch):
    _enable_billing_v1(monkeypatch)
    from contractor_ops.billing import set_billing_db
    from contractor_ops.router import set_db as set_router_db

    sync_db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    org_renew = "test-cron-8-renew"
    org_cancelled = "test-cron-8-cancelled"
    paid_until = _future_iso(30)
    for o in (org_renew, org_cancelled):
        _cleanup(sync_db, o)
        _seed_org(sync_db, o)
    _seed_active_sub(sync_db, org_renew, paid_until=paid_until, auto_renew=True)
    _seed_active_sub(
        sync_db, org_cancelled,
        paid_until=paid_until,
        auto_renew=False,
        cancelled_at=_now_iso(),
        expires_at=paid_until,
    )

    async def run():
        mdb = _wire_mdb(set_billing_db, set_router_db)
        # This is the EXACT filter used by the renewal cron at
        # backend/contractor_ops/billing_router.py:~931 — must stay byte-identical.
        all_subs = await mdb.subscriptions.find(
            {'status': {'$in': ['active', 'past_due']}, 'auto_renew': True},
            {'_id': 0, 'org_id': 1, 'paid_until': 1, 'status': 1, 'auto_renew': 1}
        ).to_list(10000)
        org_ids = [s["org_id"] for s in all_subs]
        assert org_renew in org_ids, (
            f"auto_renew=True sub must appear in cron query, but {org_renew} not in {org_ids[:5]}..."
        )
        assert org_cancelled not in org_ids, (
            f"auto_renew=False sub must NOT appear in cron query, but {org_cancelled} did"
        )

    try:
        asyncio.run(run())
    finally:
        for o in (org_renew, org_cancelled):
            _cleanup(sync_db, o)
