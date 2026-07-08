"""FUNCTIONAL probes for hotfix-validation-handler (dev-mode 422, not 500).

Verification-only. Boots the REAL FastAPI app (server.py) in-process with
ENABLE_SAFETY_MODULE=true + APP_MODE=dev and fires REAL HTTP requests through
fastapi.testclient — the REAL _validation_exception_handler handles them.
Scaffolding NOT under test (disclosed): get_current_user is dependency-overridden
to a PM user (validation errors are raised during body parsing, before any
endpoint/DB logic runs).
"""
import os
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["APP_MODE"] = "dev"
# Force local Mongo — the workspace shell env may carry an Atlas SRV URL that
# does not resolve here; the probe must be hermetic to this environment.
os.environ["MONGO_URL"] = "mongodb://localhost:27017"
os.environ["DB_NAME"] = "contractor_ops"

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import server
from contractor_ops.router import get_current_user

server.app.dependency_overrides[get_current_user] = lambda: {"id": "probe-pm", "role": "project_manager"}
client = TestClient(server.app, raise_server_exceptions=False)

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def msg_of(body):
    try:
        return " | ".join(str(d.get("msg", "")) for d in body.get("detail", []))
    except Exception:
        return str(body)[:200]


# V1 — equipment check with performed_at="not-a-date"
r1 = client.post(
    "/api/safety/probe-proj/equipment/probe-eq/checks",
    json={"check_name": "בדיקת תקינות", "performed_at": "not-a-date"},
)
b1 = r1.json() if r1.headers.get("content-type", "").startswith("application/json") else {}
record("V1 equipment check bad performed_at → 422 (was 500)",
       r1.status_code == 422, f"status={r1.status_code}")
record("V1 detail[0].msg carries 'תאריך ביצוע לא תקין'",
       "תאריך ביצוע לא תקין" in msg_of(b1), f"msg={msg_of(b1)[:120]}")

# V2 — tour create with malformed tour_date
r2 = client.post(
    "/api/safety/probe-proj/tours",
    json={"tour_type": "officer_monthly", "tour_date": "07/07/2026"},
)
b2 = r2.json() if r2.headers.get("content-type", "").startswith("application/json") else {}
record("V2 tour bad tour_date → 422 with Hebrew msg",
       r2.status_code == 422 and ("תאריך" in msg_of(b2)),
       f"status={r2.status_code} msg={msg_of(b2)[:120]}")

# V3 — plain missing-required-field error: shape unchanged
r3 = client.post("/api/safety/probe-proj/trainings", json={})
b3 = r3.json() if r3.headers.get("content-type", "").startswith("application/json") else {}
shape_ok = (
    r3.status_code == 422
    and isinstance(b3.get("detail"), list)
    and all({"loc", "msg", "type"} <= set(d.keys()) for d in b3["detail"])
)
record("V3 missing required fields → 422, standard detail list shape",
       shape_ok, f"status={r3.status_code} n_errors={len(b3.get('detail', []))}")

print("\n" + "=" * 60)
passed = sum(1 for _, ok, _ in RESULTS if ok)
print(f"RESULT: {passed}/{len(RESULTS)} probes passed")
sys.exit(0 if passed == len(RESULTS) else 1)
