import math
import uuid
from copy import deepcopy

from fastapi import HTTPException


DEFAULT_SPARE_CATEGORIES = [
    {'name': 'ריצוף יבש', 'measure': 'tiles'},
    {'name': 'ריצוף מרפסות', 'measure': 'cartons'},
    {'name': 'חיפוי אמבטיות', 'measure': 'cartons'},
    {'name': 'ריצוף אמבטיות', 'measure': 'cartons'},
    {'name': 'חיפוי מטבח', 'measure': 'cartons'},
]
MEASURES = {'tiles', 'cartons', 'sqm'}


def default_spare_settings():
    return {
        'categories': deepcopy(DEFAULT_SPARE_CATEGORIES),
        'profiles': [],
        'margin_pct': 10,
    }


def _integer(value, message):
    if isinstance(value, bool):
        raise HTTPException(status_code=422, detail=message)
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(status_code=422, detail=message)
    if isinstance(value, float) and not value.is_integer():
        raise HTTPException(status_code=422, detail=message)
    return normalized


def validate_spare_settings(body):
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail='הגדרות ריצוף ספייר חייבות להיות אובייקט')

    raw_categories = body.get('categories')
    if not isinstance(raw_categories, list) or not 1 <= len(raw_categories) <= 20:
        raise HTTPException(status_code=422, detail='יש להגדיר בין 1 ל-20 קטגוריות')

    categories = []
    category_names = set()
    for raw in raw_categories:
        if not isinstance(raw, dict):
            raise HTTPException(status_code=422, detail='קטגוריה חייבת להיות אובייקט')
        name = raw.get('name')
        if not isinstance(name, str) or not name.strip():
            raise HTTPException(status_code=422, detail='שם קטגוריה הוא שדה חובה')
        name = name.strip()
        if len(name) > 50:
            raise HTTPException(status_code=422, detail='שם קטגוריה ארוך מדי (עד 50 תווים)')
        name_key = name.casefold()
        if name_key in category_names:
            raise HTTPException(status_code=422, detail=f'שם קטגוריה כפול: {name}')
        measure = raw.get('measure')
        if measure not in MEASURES:
            raise HTTPException(status_code=422, detail='יחידת מידה לא חוקית')
        category_names.add(name_key)
        categories.append({'name': name, 'measure': measure})

    raw_profiles = body.get('profiles', [])
    if not isinstance(raw_profiles, list) or len(raw_profiles) > 10:
        raise HTTPException(status_code=422, detail='ניתן להגדיר עד 10 פרופילים')

    exact_category_names = {category['name'] for category in categories}
    profiles = []
    profile_names = set()
    profile_ids = set()
    for raw in raw_profiles:
        if not isinstance(raw, dict):
            raise HTTPException(status_code=422, detail='פרופיל חייב להיות אובייקט')
        name = raw.get('name')
        if not isinstance(name, str) or not name.strip():
            raise HTTPException(status_code=422, detail='שם פרופיל הוא שדה חובה')
        name = name.strip()
        if len(name) > 40:
            raise HTTPException(status_code=422, detail='שם פרופיל ארוך מדי (עד 40 תווים)')
        name_key = name.casefold()
        if name_key in profile_names:
            raise HTTPException(status_code=422, detail=f'שם פרופיל כפול: {name}')
        profile_names.add(name_key)

        profile_id = raw.get('id')
        if profile_id is None:
            profile_id = str(uuid.uuid4())
        elif not isinstance(profile_id, str):
            raise HTTPException(status_code=422, detail='מזהה פרופיל אינו חוקי')
        else:
            try:
                uuid.UUID(profile_id)
            except ValueError:
                raise HTTPException(status_code=422, detail='מזהה פרופיל אינו חוקי')
        if profile_id in profile_ids:
            raise HTTPException(status_code=422, detail='מזהה פרופיל כפול')
        profile_ids.add(profile_id)

        raw_targets = raw.get('targets', {})
        if not isinstance(raw_targets, dict):
            raise HTTPException(status_code=422, detail='יעדי פרופיל חייבים להיות אובייקט')
        targets = {}
        for category_name, value in raw_targets.items():
            if category_name not in exact_category_names:
                continue
            target = _integer(value, 'יעד חייב להיות מספר שלם')
            if not 0 <= target <= 10000:
                raise HTTPException(status_code=422, detail='יעד חייב להיות בין 0 ל-10000')
            targets[category_name] = target
        profiles.append({'id': profile_id, 'name': name, 'targets': targets})

    margin_pct = _integer(body.get('margin_pct', 10), 'אחוז גבולי חייב להיות מספר שלם')
    if not 0 <= margin_pct <= 100:
        raise HTTPException(status_code=422, detail='אחוז גבולי חייב להיות בין 0 ל-100')

    return {
        'categories': categories,
        'profiles': profiles,
        'margin_pct': margin_pct,
    }


def compute_spare_status(unit_doc, spare_settings):
    settings = spare_settings or default_spare_settings()
    profiles = settings.get('profiles') or []
    profile_id = unit_doc.get('spare_profile_id')
    profile = next(
        (item for item in profiles if isinstance(item, dict) and item.get('id') == profile_id),
        None,
    )

    entries = {}
    custom_names = []
    for entry in unit_doc.get('spare_tiles') or []:
        if not isinstance(entry, dict) or not isinstance(entry.get('type'), str):
            continue
        entry_name = entry['type']
        if entry_name not in entries:
            custom_names.append(entry_name)
        entries[entry_name] = entry

    configured = []
    configured_names = set()
    for category in settings.get('categories') or []:
        if not isinstance(category, dict) or not isinstance(category.get('name'), str):
            continue
        configured.append((category['name'], category.get('measure')))
        configured_names.add(category['name'])
    configured.extend((name, None) for name in custom_names if name not in configured_names)

    rows = []
    targets = profile.get('targets', {}) if profile else {}
    margin_pct = settings.get('margin_pct', 10)
    for name, measure in configured:
        entry = entries.get(name)
        count = entry.get('count', 0) if entry else 0
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 0
        notes = entry.get('notes') if entry else None
        entered = entry is not None and (count > 0 or bool(notes))
        actual = count if entered else None
        target = targets.get(name) if profile else None
        missing = None
        if not target or target <= 0:
            status = 'no_target'
        elif not entered:
            status = 'not_entered'
        elif actual < target:
            status = 'short'
            missing = target - actual
        elif actual < target + max(1, math.ceil(target * margin_pct / 100)):
            status = 'borderline'
        else:
            status = 'ok'
        rows.append({
            'name': name,
            'measure': measure,
            'target': target,
            'actual': actual,
            'status': status,
            'missing': missing,
        })

    if not profile:
        overall = 'no_profile'
    else:
        statuses = {row['status'] for row in rows}
        overall = next(
            status for status in ('short', 'not_entered', 'borderline', 'ok', 'no_target')
            if status in statuses
        )
    return {
        'profile': {'id': profile['id'], 'name': profile['name']} if profile else None,
        'overall': overall,
        'categories': rows,
    }