from fastapi import APIRouter

router = APIRouter(prefix="/api")


# NOTE: Intentionally unauthenticated.
# Frontend needs feature flags before login to show/hide UI elements.
@router.get("/config/features")
async def get_feature_flags():
    from config import APP_MODE, ENABLE_QUICK_LOGIN, ENABLE_ONBOARDING_V2, ENABLE_DEFECTS_V2, ENABLE_DEMO_USERS
    from contractor_ops.billing import BILLING_V1_ENABLED
    return {
        "feature_flags": {
            "app_mode": APP_MODE,
            "enable_quick_login": ENABLE_QUICK_LOGIN,
            "onboarding_v2": ENABLE_ONBOARDING_V2,
            "billing_v1_enabled": BILLING_V1_ENABLED,
            "defects_v2": ENABLE_DEFECTS_V2,
            "enable_demo_users": ENABLE_DEMO_USERS,
        }
    }
