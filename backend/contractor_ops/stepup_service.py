import uuid
import secrets
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

import bcrypt

from config import (
    STEPUP_CHANNEL, STEPUP_EMAIL, STEPUP_TTL_SECONDS,
    STEPUP_GRANT_SECONDS, STEPUP_MAX_ATTEMPTS, STEPUP_RATE_LIMIT_SECONDS,
    STEPUP_LOG_FALLBACK_ENABLED, STEPUP_FALLBACK_RATE_LIMIT,
    STEPUP_FALLBACK_WINDOW_SECONDS,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, APP_MODE,
    SMTP_FROM, SMTP_FROM_NAME, SMTP_REPLY_TO,
)

logger = logging.getLogger(__name__)

_db_ref = None


def set_stepup_db(db):
    global _db_ref
    _db_ref = db


def _get_db():
    if _db_ref is not None:
        return _db_ref
    try:
        from contractor_ops.router import get_db
        return get_db()
    except Exception:
        return None


def _now() -> datetime:
    return datetime.utcnow()


def _now_ts() -> float:
    return _now().timestamp()


async def _hash_code(code: str) -> str:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: bcrypt.hashpw(code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    )


async def _verify_code(code: str, hashed: str) -> bool:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: bcrypt.checkpw(code.encode('utf-8'), hashed.encode('utf-8'))
    )


def _redact_smtp_error(e: Exception) -> str:
    error_class = type(e).__name__
    smtp_code = getattr(e, 'smtp_code', '')
    if smtp_code:
        return f"{error_class}:{smtp_code}"
    return error_class


def _send_email(to_email: str, code: str) -> dict:
    if not SMTP_USER or not SMTP_PASS:
        return {'success': False, 'error': 'SMTP not configured', 'smtp_error_redacted': 'SMTPNotConfigured'}

    msg = MIMEMultipart('alternative')
    msg['From'] = f'{SMTP_FROM_NAME} <{SMTP_FROM}>'
    msg['To'] = to_email
    msg['Reply-To'] = SMTP_REPLY_TO
    msg['Subject'] = 'BrikOps - קוד אימות מנהל'

    text_body = f'קוד האימות שלך: {code}\nתוקף: {STEPUP_TTL_SECONDS // 60} דקות.\nאל תשתף קוד זה עם אף אחד.'
    html_body = f'''
    <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 400px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1a1a2e;">BrikOps - אימות מנהל</h2>
        <p>קוד האימות שלך:</p>
        <div style="background: #f0f0f0; padding: 16px; text-align: center; font-size: 28px; font-weight: bold; letter-spacing: 6px; border-radius: 8px; margin: 16px 0;">
            {code}
        </div>
        <p style="color: #666; font-size: 13px;">תוקף: {STEPUP_TTL_SECONDS // 60} דקות. אל תשתף קוד זה.</p>
    </div>
    '''
    from contractor_ops.email_templates import wrap_email
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(wrap_email(html_body, 'default'), 'html', 'utf-8'))

    try:
        logger.info(f"[SMTP-CONNECT] host={SMTP_HOST} port={SMTP_PORT} user={SMTP_USER[:4]}*** from={SMTP_FROM}")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        logger.info(f"[SMTP-SEND] from_name={SMTP_FROM_NAME} from_email={SMTP_FROM} reply_to={SMTP_REPLY_TO}")
        return {'success': True}
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPException, Exception) as e:
        redacted = _redact_smtp_error(e)
        logger.error(f"SMTP failed: {redacted} host={SMTP_HOST} user={SMTP_USER[:4]}***")
        return {'success': False, 'error': f'SMTP failed: {redacted}', 'smtp_error_redacted': redacted}


async def _check_rate_limit(db, user_id: str) -> bool:
    now = _now()
    cutoff = now - timedelta(seconds=STEPUP_RATE_LIMIT_SECONDS)
    recent = await db.stepup_challenges.find_one({
        'user_id': user_id,
        'created_at': {'$gte': cutoff},
    }, sort=[('created_at', -1)])
    return recent is None


async def _check_fallback_rate_limit(db, user_id: str) -> bool:
    now = _now()
    cutoff = now - timedelta(seconds=STEPUP_FALLBACK_WINDOW_SECONDS)
    count = await db.stepup_challenges.count_documents({
        'user_id': user_id,
        'delivery_channel': 'log_fallback',
        'created_at': {'$gte': cutoff},
    })
    return count < STEPUP_FALLBACK_RATE_LIMIT


async def create_challenge(
    user_id: str,
    session_version: int,
    platform_role: str = '',
    request_id: str = '',
    ip: str = '',
    ua: str = '',
) -> dict:
    db = _get_db()
    if db is None:
        return {'success': False, 'error': 'db_unavailable', 'message': 'שגיאה פנימית.'}

    if not await _check_rate_limit(db, user_id):
        return {
            'success': False,
            'error': 'rate_limited',
            'message': 'נסה שוב בעוד דקה.',
        }

    target_email = STEPUP_EMAIL
    if not target_email:
        return {'success': False, 'error': 'no_email', 'message': 'כתובת אימייל לא הוגדרה.'}

    code = f"{secrets.randbelow(1000000):06d}"

    send_result = _send_email(target_email, code)

    if not send_result['success']:
        smtp_error_redacted = send_result.get('smtp_error_redacted', 'unknown')
        logger.error(f"Step-up email failed for user {user_id}: {smtp_error_redacted}")

        if not STEPUP_LOG_FALLBACK_ENABLED:
            return {
                'success': False,
                'error': 'smtp_unavailable',
                'message': f'Step-Up לא זמין — שגיאת SMTP ({smtp_error_redacted}). יש לתקן הגדרות SMTP.',
            }

        if platform_role != 'super_admin':
            return {
                'success': False,
                'error': 'smtp_unavailable',
                'message': f'Step-Up לא זמין — שגיאת SMTP ({smtp_error_redacted}). יש לתקן הגדרות SMTP.',
            }

        if not await _check_fallback_rate_limit(db, user_id):
            return {
                'success': False,
                'error': 'rate_limited',
                'message': 'חרגת ממגבלת Break-glass. נסה שוב בעוד 10 דקות.',
            }

        challenge_id = str(uuid.uuid4())
        hashed = await _hash_code(code)
        now = _now()

        await db.stepup_challenges.insert_one({
            'challenge_id': challenge_id,
            'user_id': user_id,
            'session_version': session_version,
            'code_hash': hashed,
            'attempts': 0,
            'created_at': now,
            'expires_at': now + timedelta(seconds=STEPUP_TTL_SECONDS),
            'used': False,
            'delivery_channel': 'log_fallback',
        })

        logger.warning(
            f"[STEPUP-FALLBACK] request_id={request_id} "
            f"smtp_error={smtp_error_redacted} — code delivery failed, check admin fallback"
        )

        try:
            await db.audit_events.insert_one({
                'action': 'stepup_fallback_log_used',
                'actor_id': user_id,
                'entity_type': 'stepup',
                'entity_id': challenge_id,
                'payload': {
                    'request_id': request_id,
                    'ip': ip,
                    'user_agent': ua,
                    'smtp_error': smtp_error_redacted,
                    'delivery_channel': 'log_fallback',
                },
                'created_at': now,
            })
        except Exception as ae:
            logger.error(f"Audit write failed for stepup_fallback_log_used: {type(ae).__name__}")

        return {
            'success': True,
            'challenge_id': challenge_id,
            'masked_email': 'לוגים (Break-glass)',
            'ttl_seconds': STEPUP_TTL_SECONDS,
            'fallback': True,
        }

    challenge_id = str(uuid.uuid4())
    hashed = await _hash_code(code)
    now = _now()

    await db.stepup_challenges.insert_one({
        'challenge_id': challenge_id,
        'user_id': user_id,
        'session_version': session_version,
        'code_hash': hashed,
        'attempts': 0,
        'created_at': now,
        'expires_at': now + timedelta(seconds=STEPUP_TTL_SECONDS),
        'used': False,
        'delivery_channel': 'email',
    })

    masked_email = target_email[:3] + '***' + target_email[target_email.index('@'):]
    if APP_MODE == 'dev':
        logger.info(f"Step-up challenge created for user {user_id}, challenge_id={challenge_id}")

    return {
        'success': True,
        'challenge_id': challenge_id,
        'masked_email': masked_email,
        'ttl_seconds': STEPUP_TTL_SECONDS,
    }


async def verify_challenge(challenge_id: str, code: str, user_id: str, session_version: int) -> dict:
    db = _get_db()
    if db is None:
        return {'success': False, 'error': 'db_unavailable', 'message': 'שגיאה פנימית.'}

    challenge = await db.stepup_challenges.find_one({
        'challenge_id': challenge_id,
        'used': False,
    })
    if not challenge:
        return {'success': False, 'error': 'invalid_challenge', 'message': 'קוד לא תקף או פג תוקף.'}

    if challenge['user_id'] != user_id:
        return {'success': False, 'error': 'user_mismatch', 'message': 'קוד לא תקף.'}

    if challenge['session_version'] != session_version:
        await db.stepup_challenges.update_one(
            {'challenge_id': challenge_id}, {'$set': {'used': True}})
        return {'success': False, 'error': 'session_changed', 'message': 'הסשן השתנה. התחבר מחדש.'}

    now = _now()
    expires_at = challenge['expires_at']
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
        expires_at = expires_at.replace(tzinfo=None)
    if expires_at < now:
        await db.stepup_challenges.update_one(
            {'challenge_id': challenge_id}, {'$set': {'used': True}})
        return {'success': False, 'error': 'expired', 'message': 'קוד פג תוקף. בקש קוד חדש.'}

    if challenge.get('attempts', 0) >= STEPUP_MAX_ATTEMPTS:
        await db.stepup_challenges.update_one(
            {'challenge_id': challenge_id}, {'$set': {'used': True}})
        return {'success': False, 'error': 'max_attempts', 'message': 'חרגת ממספר הניסיונות. בקש קוד חדש.'}

    await db.stepup_challenges.update_one(
        {'challenge_id': challenge_id}, {'$inc': {'attempts': 1}})

    if not await _verify_code(code, challenge['code_hash']):
        remaining = STEPUP_MAX_ATTEMPTS - challenge.get('attempts', 0) - 1
        return {
            'success': False,
            'error': 'wrong_code',
            'message': f'קוד שגוי. נותרו {remaining} ניסיונות.',
        }

    await db.stepup_challenges.update_one(
        {'challenge_id': challenge_id}, {'$set': {'used': True}})

    grant_now = _now()
    grant_key = f"{user_id}:{session_version}"
    await db.stepup_grants.update_one(
        {'grant_key': grant_key},
        {'$set': {
            'grant_key': grant_key,
            'user_id': user_id,
            'session_version': session_version,
            'granted_at': grant_now,
            'expires_at': grant_now + timedelta(seconds=STEPUP_GRANT_SECONDS),
        }},
        upsert=True,
    )

    return {
        'success': True,
        'grant_ttl_seconds': STEPUP_GRANT_SECONDS,
        'message': 'אימות הצליח.',
    }


async def has_valid_grant(user_id: str, session_version: int) -> bool:
    db = _get_db()
    if db is None:
        return False
    grant_key = f"{user_id}:{session_version}"
    now = _now()
    grant = await db.stepup_grants.find_one({
        'grant_key': grant_key,
        'expires_at': {'$gte': now},
    })
    return grant is not None


async def revoke_grants(user_id: str):
    db = _get_db()
    if db is None:
        return
    await db.stepup_grants.delete_many({'user_id': user_id})


async def ensure_indexes(db):
    try:
        await db.stepup_challenges.create_index('challenge_id', unique=True)
        await db.stepup_challenges.create_index('expires_at', expireAfterSeconds=0)
        await db.stepup_challenges.create_index([('user_id', 1), ('created_at', -1)])
        await db.stepup_grants.create_index('grant_key', unique=True)
        await db.stepup_grants.create_index('expires_at', expireAfterSeconds=0)
        logger.info("Step-up indexes ensured")
    except Exception as e:
        logger.warning(f"Step-up index creation: {e}")
