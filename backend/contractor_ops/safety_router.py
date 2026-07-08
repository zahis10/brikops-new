"""Facade — the safety package split (batch refactor-safety-split).

The 3,397-line monolith moved to contractor_ops/safety/ (12 section modules,
single shared APIRouter, registration order preserved). This module keeps the
old import path working so server.py and all consumers stay untouched.

Re-export surface = the STEP 0 consumer audit (explicit names, no import *):
  server.py                      → router, ensure_safety_indexes
  safety_registration_router.py  → SAFETY_WRITERS, _hash_id_number, _new_id
  tests/probe_p3c_*.py           → trainings coroutines + models + scaffolding
"""
from contractor_ops.safety import router, ensure_safety_indexes  # noqa: F401
from contractor_ops.safety._shared import (  # noqa: F401
    SAFETY_WRITERS,
    SAFETY_DELETERS,
    _hash_id_number,
    _new_id,
    get_db,
    _now,
    _audit,
    _check_project_access,
    require_roles,
    check_upload_rate_limit,
    check_upload_bytes,
    check_storage_quota,
    record_upload,
)
from contractor_ops.safety.trainings import (  # noqa: F401
    SafetyTrainingCreate,
    SafetyTrainingUpdate,
    create_training,
    list_trainings,
    update_training,
    sign_training,
)
