from fastapi import APIRouter

router = APIRouter(prefix="/api")


# NOTE: Intentionally unauthenticated.
# Frontend needs feature flags before login to show/hide UI elements.
@router.get("/config/features")
async def get_feature_flags():
    from config import ENABLE_ONBOARDING_V2, ENABLE_DEFECTS_V2
    from contractor_ops.billing import BILLING_V1_ENABLED
    return {
        "feature_flags": {
            "onboarding_v2": ENABLE_ONBOARDING_V2,
            "billing_v1_enabled": BILLING_V1_ENABLED,
            "defects_v2": ENABLE_DEFECTS_V2,
        }
    }
