import logging

logger = logging.getLogger(__name__)

_db = None


def set_plans_db(db):
    global _db
    _db = db


def get_db():
    if _db is None:
        raise RuntimeError("Billing plans DB not initialized")
    return _db


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


PROJECT_LICENSE_FIRST = 450
PROJECT_LICENSE_ADDITIONAL = 450
PRICE_PER_UNIT = 15

FOUNDER_PLAN = {
    "plan_id": "founder_6m",
    "name": "מנוי מייסדים",
    "monthly_price": 499,
    "locked_months": 6,
}


def calculate_monthly(
    units: int,
    plan_id: str = None,
    manual_override: dict = None,
    project_index: int = 1,
) -> int:
    if manual_override and manual_override.get("total_monthly"):
        return manual_override["total_monthly"]
    if plan_id == "founder_6m":
        return 499
    license_fee = PROJECT_LICENSE_FIRST if project_index <= 1 \
        else PROJECT_LICENSE_ADDITIONAL
    return license_fee + (units * PRICE_PER_UNIT)


def get_pricing_breakdown(
    units: int,
    plan_id: str = None,
    manual_override: dict = None,
    project_index: int = 1,
) -> dict:
    if manual_override and manual_override.get("total_monthly"):
        return {
            "total_monthly": manual_override["total_monthly"],
            "breakdown": "תמחור מותאם",
            "is_override": True,
        }
    if plan_id == "founder_6m":
        return {
            "plan": "מנוי מייסדים",
            "total_monthly": 499,
            "breakdown": "מנוי מייסדים — 499₪/חודש",
        }
    license_fee = PROJECT_LICENSE_FIRST if project_index <= 1 \
        else PROJECT_LICENSE_ADDITIONAL
    unit_cost = units * PRICE_PER_UNIT
    total = license_fee + unit_cost
    return {
        "license_fee": license_fee,
        "price_per_unit": PRICE_PER_UNIT,
        "units": units,
        "unit_cost": unit_cost,
        "total_monthly": total,
        "breakdown": f"רישיון {license_fee}₪ + {units}×{PRICE_PER_UNIT}₪",
    }


def calculate_org_monthly(
    projects: list,
    plan_id: str = None,
    manual_override: dict = None,
) -> int:
    if manual_override and manual_override.get("total_monthly"):
        return manual_override["total_monthly"]
    if plan_id == "founder_6m":
        return 499
    sorted_projects = sorted(projects, key=lambda p: p.get("created_at", ""))
    total = 0
    for i, proj in enumerate(sorted_projects):
        total += calculate_monthly(
            units=proj.get("units_count", 0),
            project_index=i + 1,
        )
    return total


async def seed_default_plans():
    pass


async def list_plans(active_only: bool = False) -> list:
    return [{
        'id': 'standard',
        'name': 'רישיון פרויקט',
        'license_first': PROJECT_LICENSE_FIRST,
        'license_additional': PROJECT_LICENSE_ADDITIONAL,
        'price_per_unit': PRICE_PER_UNIT,
        'is_active': True,
    }]


async def get_plan(plan_id: str):
    if plan_id == "founder_6m":
        return {
            'id': 'founder_6m',
            'name': 'מנוי מייסדים',
            'monthly_price': 499,
            'is_active': True,
        }
    return {
        'id': 'standard',
        'name': 'רישיון פרויקט',
        'license_first': PROJECT_LICENSE_FIRST,
        'license_additional': PROJECT_LICENSE_ADDITIONAL,
        'price_per_unit': PRICE_PER_UNIT,
        'is_active': True,
    }
