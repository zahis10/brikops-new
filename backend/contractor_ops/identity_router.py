import logging
import re
import uuid
import bcrypt
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from contractor_ops.router import get_current_user, get_db
from contractor_ops.identity_service import get_account_status, complete_account, is_management_user
from config import ENABLE_COMPLETE_ACCOUNT_GATE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["identity"])

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

ALLOWED_IDENTITY_EVENTS = {
    'identity_banner_shown',
    'identity_banner_dismissed',
    'identity_modal_shown',
}

_COMMON_PASSWORDS = {
    '123456', '1234567', '12345678', '123456789', '1234567890',
    '111111', '000000', 'password', 'qwerty', 'abcdef',
    'abcd1234', 'password1', 'abc123', 'admin123', '11111111',
}


def _verify_password_sync(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def _hash_password_sync(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _validate_new_password(password: str):
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail='סיסמה חייבת להכיל לפחות 8 תווים')
    if not re.search(r'[a-zA-Zא-ת]', password):
        raise HTTPException(status_code=400, detail='סיסמה חייבת לכלול לפחות אות אחת')
    if not re.search(r'[0-9]', password):
        raise HTTPException(status_code=400, detail='סיסמה חייבת לכלול לפחות מספר אחד')
    if password.lower() in _COMMON_PASSWORDS:
        raise HTTPException(status_code=400, detail='סיסמה זו נפוצה מדי, יש לבחור סיסמה חזקה יותר')


async def _require_management(user_id: str):
    if not await is_management_user(user_id):
        raise HTTPException(status_code=403, detail='אין הרשאה')


async def _verify_current_password(user: dict, current_password: str):
    pw_hash = user.get('password_hash')
    if not pw_hash:
        raise HTTPException(status_code=400, detail='לא הוגדרה סיסמה לחשבון זה. יש להשלים חשבון תחילה.')

    import asyncio
    loop = asyncio.get_event_loop()
    valid = await loop.run_in_executor(None, _verify_password_sync, current_password, pw_hash)
    if not valid:
        raise HTTPException(status_code=401, detail='סיסמה נוכחית שגויה')


@router.get("/account-status")
async def account_status(user: dict = Depends(get_current_user)):
    status = await get_account_status(user, ENABLE_COMPLETE_ACCOUNT_GATE)
    return status


class CompleteAccountRequest(BaseModel):
    email: str
    password: str


@router.post("/complete-account")
async def complete_account_endpoint(req: CompleteAccountRequest, user: dict = Depends(get_current_user)):
    email = req.email.strip().lower()
    if not email or not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail='כתובת מייל לא תקינה')

    password = req.password
    if len(password) < 8:
        raise HTTPException(status_code=400, detail='סיסמה חייבת להכיל לפחות 8 תווים')

    result = await complete_account(user['id'], email, password)
    if result.get('error'):
        raise HTTPException(status_code=409, detail=result['error'])

    return {'ok': True, 'account_status': await get_account_status(
        {**user, 'email': email, 'password_hash': 'set', 'account_complete': True},
        ENABLE_COMPLETE_ACCOUNT_GATE
    )}


class IdentityEventRequest(BaseModel):
    action: str
    payload: Optional[Dict[str, Any]] = None


@router.post("/identity-event")
async def log_identity_event(req: IdentityEventRequest, user: dict = Depends(get_current_user)):
    if req.action not in ALLOWED_IDENTITY_EVENTS:
        raise HTTPException(status_code=400, detail='אירוע לא מוכר')

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.audit_events.insert_one({
        'id': uuid.uuid4().hex,
        'entity_type': 'user',
        'entity_id': user['id'],
        'action': req.action,
        'actor_id': user['id'],
        'payload': req.payload or {},
        'created_at': now,
    })

    return {'ok': True}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    user_id = user['id']
    await _require_management(user_id)

    db = get_db()
    full_user = await db.users.find_one({'id': user_id}, {'_id': 0, 'password_hash': 1, 'session_version': 1})
    if not full_user:
        raise HTTPException(status_code=404, detail='משתמש לא נמצא')

    await _verify_current_password(full_user, req.current_password)
    _validate_new_password(req.new_password)

    import asyncio
    loop = asyncio.get_event_loop()
    new_hash = await loop.run_in_executor(None, _hash_password_sync, req.new_password)

    old_sv = full_user.get('session_version', 0)
    new_sv = old_sv + 1
    now = datetime.now(timezone.utc).isoformat()

    await db.users.update_one(
        {'id': user_id},
        {'$set': {'password_hash': new_hash, 'session_version': new_sv, 'updated_at': now}, '$unset': {'password': ''}}
    )

    await db.audit_events.insert_one({
        'id': uuid.uuid4().hex,
        'entity_type': 'user',
        'entity_id': user_id,
        'action': 'account_password_changed',
        'actor_id': user_id,
        'payload': {'old_session_version': old_sv, 'new_session_version': new_sv},
        'created_at': now,
    })

    logger.info(f"[ACCOUNT] password_changed user={user_id} sv={old_sv}->{new_sv}")

    return {'ok': True, 'force_relogin': True}


class ChangeEmailRequest(BaseModel):
    current_password: str
    new_email: str


@router.post("/change-email")
async def change_email(req: ChangeEmailRequest, user: dict = Depends(get_current_user)):
    user_id = user['id']
    await _require_management(user_id)

    new_email = req.new_email.strip().lower()
    if not new_email or not EMAIL_RE.match(new_email):
        raise HTTPException(status_code=400, detail='כתובת אימייל לא תקינה')

    db = get_db()
    full_user = await db.users.find_one({'id': user_id}, {'_id': 0, 'password_hash': 1, 'email': 1})
    if not full_user:
        raise HTTPException(status_code=404, detail='משתמש לא נמצא')

    await _verify_current_password(full_user, req.current_password)

    old_email = full_user.get('email') or ''

    if new_email == old_email:
        raise HTTPException(status_code=400, detail='כתובת האימייל החדשה זהה לנוכחית')

    duplicate = await db.users.find_one(
        {'email': new_email, 'id': {'$ne': user_id}},
        {'_id': 1}
    )
    if duplicate:
        raise HTTPException(status_code=409, detail='כתובת אימייל כבר רשומה במערכת')

    now = datetime.now(timezone.utc).isoformat()

    await db.users.update_one(
        {'id': user_id},
        {'$set': {'email': new_email, 'email_verified': False, 'updated_at': now}}
    )

    await db.audit_events.insert_one({
        'id': uuid.uuid4().hex,
        'entity_type': 'user',
        'entity_id': user_id,
        'action': 'account_email_changed',
        'actor_id': user_id,
        'payload': {'old_email': old_email, 'new_email': new_email},
        'created_at': now,
    })

    logger.info(f"[ACCOUNT] email_changed user={user_id} old={old_email[:3]}*** new={new_email[:3]}***")

    return {'ok': True, 'email': new_email}
