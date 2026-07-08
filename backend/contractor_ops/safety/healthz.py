"""Batch refactor-safety-split — section moved verbatim from safety_router.py (lines 152-163). MOVE, never edit."""
from contractor_ops.safety._shared import (  # noqa: F401
    Depends,
    get_current_user,
    router,
)

# =====================================================================
# healthz (Part 1)
# =====================================================================
@router.get("/healthz")
async def healthz(user: dict = Depends(get_current_user)):
    """
    Liveness check for Safety module.
    Requires auth — never expose module existence to unauthenticated scanners.
    """
    return {"ok": True, "module": "safety", "enabled": True}


