import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent

_pre_app_mode = os.environ.get('APP_MODE', '').strip()
if _pre_app_mode == 'dev':
    _dotenv_path = ROOT_DIR / '.env'
    if _dotenv_path.exists():
        load_dotenv(_dotenv_path, override=False)
        logger.info("[CONFIG] Loaded .env (APP_MODE=dev)")
    else:
        logger.info("[CONFIG] APP_MODE=dev but no .env file found, skipping dotenv")
else:
    logger.info(f"[CONFIG] APP_MODE='{_pre_app_mode}' (not dev) — .env NOT loaded (prod-safe default)")

_SENSITIVE_KEYS = frozenset({
    'JWT_SECRET', 'AWS_SECRET_ACCESS_KEY', 'AWS_ACCESS_KEY_ID',
    'DATABASE_URL', 'PGPASSWORD', 'SESSION_SECRET', 'EMERGENT_LLM_KEY',
    'PAYPLUS_API_KEY', 'PAYPLUS_SECRET_KEY',
})


def _require(key: str, min_length: int = 1) -> str:
    value = os.environ.get(key, '').strip()
    if not value or len(value) < min_length:
        msg = f"FATAL: Required env var '{key}' is missing or too short (min {min_length} chars). App cannot start."
        logger.critical(msg)
        print(msg, file=sys.stderr)
        sys.exit(1)
    return value


def _require_choice(key: str, choices: tuple) -> str:
    value = _require(key)
    if value not in choices:
        msg = f"FATAL: env var '{key}' must be one of {choices}, got '{value}'. App cannot start."
        logger.critical(msg)
        print(msg, file=sys.stderr)
        sys.exit(1)
    return value


APP_ID = _require('APP_ID')
APP_MODE = os.environ.get('APP_MODE', 'prod').strip()
if APP_MODE not in ('dev', 'prod'):
    logger.warning(f"[CONFIG] APP_MODE='{APP_MODE}' invalid, defaulting to 'prod'")
    APP_MODE = 'prod'
JWT_SECRET = _require('JWT_SECRET', min_length=32)
JWT_SECRET_VERSION = _require('JWT_SECRET_VERSION')
MONGO_URL = _require('MONGO_URL')
DB_NAME = _require('DB_NAME')

JWT_ALGORITHM = 'HS256'
JWT_ALLOWED_ALGORITHMS = ['HS256']
JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', '720'))
JWT_SUPER_ADMIN_EXPIRATION_MINUTES = 30
JWT_CLOCK_SKEW_SECONDS = 60
JWT_RENEWAL_THRESHOLD_DAYS = 15

WHATSAPP_ENABLED = os.environ.get('WHATSAPP_ENABLED', 'false').lower() == 'true'
ENABLE_REMINDER_SCHEDULER = os.environ.get('ENABLE_REMINDER_SCHEDULER', 'true').lower() == 'true'
WA_INVITE_ENABLED = os.environ.get('WA_INVITE_ENABLED', 'false').lower() == 'true'
WHATSAPP_PROVIDER = os.environ.get('WHATSAPP_PROVIDER', 'meta')
WA_ACCESS_TOKEN = os.environ.get('WA_ACCESS_TOKEN', '')
WA_PHONE_NUMBER_ID = os.environ.get('WA_PHONE_NUMBER_ID', '')
WA_TEMPLATE_NEW_DEFECT = os.environ.get('WA_TEMPLATE_NEW_DEFECT', '')
WA_TEMPLATE_LANG = os.environ.get('WA_TEMPLATE_LANG', 'he')
WA_TEMPLATE_INVITE = os.environ.get('WA_TEMPLATE_INVITE', '')
WA_TEMPLATE_INVITE_LANG = os.environ.get('WA_TEMPLATE_INVITE_LANG', 'he')

WA_DEFECT_TEMPLATES = {
    'he': {'name': os.environ.get('WA_DEFECT_TEMPLATE_HE', 'brikops_defect_new_he_v2'), 'lang': 'he'},
    'en': {'name': os.environ.get('WA_DEFECT_TEMPLATE_EN', 'brikops_defect_new_en_v2'), 'lang': 'en'},
    'ar': {'name': os.environ.get('WA_DEFECT_TEMPLATE_AR', 'brikops_defect_new_ar_v2'), 'lang': 'ar'},
    'zh': {'name': os.environ.get('WA_DEFECT_TEMPLATE_ZH', 'brikops_defect_new_zh_v2'), 'lang': 'zh_CN'},
}
WA_DEFECT_DEFAULT_LANG = 'he'
ALLOWED_LANGUAGES = ['he', 'en', 'ar', 'zh']
WA_TEMPLATE_PARAM_MODE = os.environ.get('WA_TEMPLATE_PARAM_MODE', 'named')
WA_QC_REJECT_TEMPLATE_HE = os.environ.get('WA_QC_REJECT_TEMPLATE_HE', 'qc_item_rejected_he')
WA_QC_REJECT_TEMPLATE_LANG = 'he'
WA_REMINDER_TEMPLATE_HE = os.environ.get('WA_REMINDER_TEMPLATE_HE', 'brikops_contractor_reminder_he')
WA_DIGEST_TEMPLATE_HE = os.environ.get('WA_DIGEST_TEMPLATE_HE', 'brikops_daily_digest_he')
CRON_SECRET = os.environ.get('CRON_SECRET', '')
OTP_SMS_FALLBACK_SECONDS = int(os.environ.get('OTP_SMS_FALLBACK_SECONDS', '25'))
WA_WEBHOOK_VERIFY_TOKEN = os.environ.get('WA_WEBHOOK_VERIFY_TOKEN', '')
META_APP_SECRET = os.environ.get('META_APP_SECRET', '')

OWNER_PHONE = os.environ.get('OWNER_PHONE', '')

def _mask_phone(phone: str) -> str:
    if not phone:
        return '<empty>'
    return '****' + phone[-4:] if len(phone) >= 4 else '****'

def _parse_super_admin_phones() -> tuple:
    from contractor_ops.phone_utils import normalize_israeli_phone
    phones = set()
    raw_single = os.environ.get('SUPER_ADMIN_PHONE', OWNER_PHONE).strip()
    raw_multi = os.environ.get('SUPER_ADMIN_PHONES', '').strip()
    raw_list = []
    source = 'none'
    if raw_multi:
        raw_list = [p.strip() for p in raw_multi.split(',') if p.strip()]
        source = 'SUPER_ADMIN_PHONES'
    elif raw_single:
        raw_list = [p.strip() for p in raw_single.split(',') if p.strip()]
        source = 'SUPER_ADMIN_PHONE'
    for raw_phone in raw_list:
        try:
            norm = normalize_israeli_phone(raw_phone)
            if norm.get('phone_e164'):
                phones.add(norm['phone_e164'])
        except Exception:
            logger.warning(f"[SA_PHONES] failed to normalize env phone {_mask_phone(raw_phone)}, skipping")
    masked = ','.join(_mask_phone(p) for p in phones)
    print(f"[SA_PHONES] count={len(phones)} source={source} phones={masked}", flush=True)
    return phones, source

SUPER_ADMIN_PHONES, SA_PHONES_SOURCE = _parse_super_admin_phones()
SUPER_ADMIN_PHONE = next(iter(SUPER_ADMIN_PHONES), '')

def is_super_admin_phone(phone_raw: str) -> dict:
    from contractor_ops.phone_utils import normalize_israeli_phone
    if not phone_raw:
        return {'matched': False, 'norm': None, 'reason': 'empty_phone'}
    try:
        result = normalize_israeli_phone(phone_raw)
        norm = result.get('phone_e164', '')
    except Exception:
        return {'matched': False, 'norm': None, 'reason': 'normalize_failed'}
    matched = norm in SUPER_ADMIN_PHONES
    return {'matched': matched, 'norm': norm, 'reason': None}

OTP_PROVIDER = os.environ.get('OTP_PROVIDER', 'mock')

OTP_TTL_SECONDS = int(os.environ.get('OTP_TTL_SECONDS', '600'))
OTP_MAX_ATTEMPTS = int(os.environ.get('OTP_MAX_ATTEMPTS', '3'))
OTP_RATE_LIMIT_SECONDS = int(os.environ.get('OTP_RATE_LIMIT_SECONDS', '90'))

SMS_MODE = os.environ.get('SMS_MODE', 'stub' if APP_MODE == 'dev' else 'live')
if APP_MODE == 'prod' and SMS_MODE == 'stub':
    logger.critical("[CONFIG] FATAL: SMS_MODE=stub is forbidden in production!")
    print("FATAL: SMS_MODE=stub is forbidden in production!", file=sys.stderr)
    sys.exit(1)

OTP_RESEND_MAX_15MIN = int(os.environ.get('OTP_RESEND_MAX_15MIN', '3'))
OTP_RESEND_MAX_DAILY = int(os.environ.get('OTP_RESEND_MAX_DAILY', '10'))

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_FROM_NUMBER = os.environ.get('TWILIO_FROM_NUMBER', '')
TWILIO_MESSAGING_SERVICE_SID = os.environ.get('TWILIO_MESSAGING_SERVICE_SID', '')
SMS_ENABLED = os.environ.get('SMS_ENABLED', 'false').lower() == 'true'

ENABLE_DEMO_USERS = os.environ.get('ENABLE_DEMO_USERS', 'true' if APP_MODE == 'dev' else 'false').lower() == 'true'
_demo_pw_raw = os.environ.get('DEMO_DEFAULT_PASSWORD', '')
if ENABLE_DEMO_USERS and APP_MODE != 'dev' and not _demo_pw_raw:
    logging.getLogger('config').error(
        "[DEMO-SAFETY] ENABLE_DEMO_USERS=true in non-dev mode but DEMO_DEFAULT_PASSWORD "
        "is not set. Demo user seeding DISABLED for safety. Set DEMO_DEFAULT_PASSWORD "
        "explicitly to enable demo accounts in this environment."
    )
    ENABLE_DEMO_USERS = False
DEMO_DEFAULT_PASSWORD = _demo_pw_raw or 'BrikOpsDemo2026!'
DEMO_RESET_PASSWORDS = os.environ.get('DEMO_RESET_PASSWORDS', 'false').lower() == 'true'

ENABLE_QUICK_LOGIN = os.environ.get('ENABLE_QUICK_LOGIN', 'true' if APP_MODE == 'dev' else 'false').lower() == 'true'
ENABLE_DEBUG_ENDPOINTS = os.environ.get('ENABLE_DEBUG_ENDPOINTS', 'true' if APP_MODE == 'dev' else 'false').lower() == 'true'

ENABLE_ONBOARDING_V2 = os.environ.get('ENABLE_ONBOARDING_V2', 'true' if APP_MODE == 'dev' else 'false').lower() == 'true'
ENABLE_AUTO_TRIAL = os.environ.get('ENABLE_AUTO_TRIAL', 'true').lower() == 'true'
ENABLE_DEFECTS_V2 = os.environ.get('ENABLE_DEFECTS_V2', 'true' if APP_MODE == 'dev' else 'false').lower() == 'true'

_gate_raw = os.environ.get('ENABLE_COMPLETE_ACCOUNT_GATE', 'off').strip().lower()
if _gate_raw not in ('off', 'soft', 'enforce'):
    logger.warning(f"[CONFIG] ENABLE_COMPLETE_ACCOUNT_GATE='{_gate_raw}' invalid, defaulting to 'off'")
    _gate_raw = 'off'
ENABLE_COMPLETE_ACCOUNT_GATE = _gate_raw

GOOGLE_CLIENT_ID_WEB = os.getenv("GOOGLE_CLIENT_ID_WEB", "")
GOOGLE_CLIENT_ID_IOS = os.getenv("GOOGLE_CLIENT_ID_IOS", "")
GOOGLE_CLIENT_ID_ANDROID = os.getenv("GOOGLE_CLIENT_ID_ANDROID", "")
APPLE_BUNDLE_ID = os.getenv("APPLE_BUNDLE_ID", "com.brikops.app")
APPLE_SERVICES_ID = os.getenv("APPLE_SERVICES_ID", "")  # e.g. "com.brikops.app.signin" — required for web flow

# Audiences accepted when verifying Apple ID tokens
APPLE_AUDIENCES = [a for a in [APPLE_BUNDLE_ID, APPLE_SERVICES_ID] if a]

STEPUP_CHANNEL = os.environ.get('STEPUP_CHANNEL', 'email')
STEPUP_EMAIL = os.environ.get('STEPUP_EMAIL', '')
STEPUP_TTL_SECONDS = int(os.environ.get('STEPUP_TTL_SECONDS', '300'))
STEPUP_GRANT_SECONDS = int(os.environ.get('STEPUP_GRANT_SECONDS', '600'))
STEPUP_MAX_ATTEMPTS = int(os.environ.get('STEPUP_MAX_ATTEMPTS', '5'))
STEPUP_RATE_LIMIT_SECONDS = int(os.environ.get('STEPUP_RATE_LIMIT_SECONDS', '60'))
STEPUP_LOG_FALLBACK_ENABLED = os.environ.get('STEPUP_LOG_FALLBACK_ENABLED', 'false').lower() == 'true'
STEPUP_FALLBACK_RATE_LIMIT = int(os.environ.get('STEPUP_FALLBACK_RATE_LIMIT', '3'))
STEPUP_FALLBACK_WINDOW_SECONDS = int(os.environ.get('STEPUP_FALLBACK_WINDOW_SECONDS', '600'))

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
SMTP_FROM = os.environ.get('SMTP_FROM', '') or SMTP_USER
SMTP_FROM_NAME = os.environ.get('SMTP_FROM_NAME', 'BrikOps')
SMTP_REPLY_TO = os.environ.get('SMTP_REPLY_TO', 'support@brikops.com')

RESET_TOKEN_TTL_MINUTES = int(os.environ.get('RESET_TOKEN_TTL_MINUTES', '60'))
PASSWORD_RESET_BASE_URL = os.environ.get('PASSWORD_RESET_BASE_URL', 'https://app.brikops.com')
FRONTEND_BASE_URL = os.environ.get('FRONTEND_BASE_URL', 'https://app.brikops.com')

GI_BASE_URL = os.environ.get('GI_BASE_URL', '')
GI_API_KEY_ID = os.environ.get('GI_API_KEY_ID', '')
GI_API_SECRET = os.environ.get('GI_API_SECRET', '')
GI_WEBHOOK_SECRET = os.environ.get('GI_WEBHOOK_SECRET', '')

PAYPLUS_API_KEY = os.environ.get('PAYPLUS_API_KEY', '')
PAYPLUS_SECRET_KEY = os.environ.get('PAYPLUS_SECRET_KEY', '')
PAYPLUS_PAYMENT_PAGE_UID = os.environ.get('PAYPLUS_PAYMENT_PAGE_UID', '')
PAYPLUS_TERMINAL_UID = os.environ.get('PAYPLUS_TERMINAL_UID', '')
PAYPLUS_CASHIER_UID = os.environ.get('PAYPLUS_CASHIER_UID', '')
PAYPLUS_ENV = os.environ.get('PAYPLUS_ENV', 'sandbox')
PAYPLUS_CALLBACK_URL = os.environ.get('PAYPLUS_CALLBACK_URL', '')

FOUNDER_PLAN_ENABLED = os.environ.get('FOUNDER_PLAN_ENABLED', 'true').lower() == 'true'
FOUNDER_MAX_SLOTS = int(os.environ.get('FOUNDER_MAX_SLOTS', '30'))


def log_sanitized_startup():
    logger.info("=" * 60)
    logger.info("BrikOps Isolation Guard - Startup Check")
    logger.info("=" * 60)
    logger.info(f"  APP_ID:             {APP_ID}")
    logger.info(f"  APP_MODE:           {APP_MODE}")
    logger.info(f"  DB_NAME:            {DB_NAME}")
    _mu = MONGO_URL
    logger.info(f"  MONGO_URL:          is_set={bool(_mu)} len={len(_mu)} starts_mongo={_mu.startswith('mongodb')} has_at={'@' in _mu} has_srv={'mongodb+srv://' in _mu}")
    logger.info(f"  JWT_SECRET:         ****{JWT_SECRET[-4:]}")
    logger.info(f"  JWT_SECRET_VERSION: {JWT_SECRET_VERSION}")
    logger.info(f"  JWT_ALGORITHM:      {JWT_ALGORITHM}")
    logger.info(f"  JWT_ADMIN_EXP:      {JWT_SUPER_ADMIN_EXPIRATION_MINUTES}min")
    for key in sorted(os.environ.keys()):
        if key in _SENSITIVE_KEYS:
            logger.debug(f"  [ENV] {key} = ***REDACTED***")
    logger.info(f"  WHATSAPP_ENABLED:   {WHATSAPP_ENABLED}")
    logger.info(f"  WA_INVITE_ENABLED:  {WA_INVITE_ENABLED}")
    logger.info(f"  OTP_SMS_FALLBACK:   {OTP_SMS_FALLBACK_SECONDS}s")
    logger.info(f"  WHATSAPP_PROVIDER:  {WHATSAPP_PROVIDER}")
    logger.info(f"  WA_PHONE_NUMBER_ID: {'...' + WA_PHONE_NUMBER_ID[-6:] if len(WA_PHONE_NUMBER_ID) > 6 else WA_PHONE_NUMBER_ID or 'NOT SET'}")
    waba_id = os.environ.get('WABA_ID', '')
    logger.info(f"  WABA_ID:            {'...' + waba_id[-6:] if len(waba_id) > 6 else waba_id or 'NOT SET'}")
    logger.info(f"  WA_ACCESS_TOKEN:    {'SET (' + str(len(WA_ACCESS_TOKEN)) + ' chars)' if WA_ACCESS_TOKEN else 'NOT SET'}")
    logger.info(f"  OWNER_PHONE:        {'****' + OWNER_PHONE[-4:] if OWNER_PHONE else 'NOT SET'}")
    logger.info(f"  SUPER_ADMIN_PHONES: {len(SUPER_ADMIN_PHONES)} configured")
    logger.info(f"  OTP_PROVIDER:       {OTP_PROVIDER}")
    logger.info(f"  OTP_TTL_SECONDS:    {OTP_TTL_SECONDS}")
    logger.info(f"  META_APP_SECRET:    {'SET' if META_APP_SECRET else 'NOT SET'}")
    logger.info(f"  TWILIO configured:  {bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)}")
    logger.info(f"  SMS_ENABLED:        {SMS_ENABLED}")
    logger.info(f"  SMS_MODE:           {SMS_MODE}")
    logger.info(f"  TWILIO_MSG_SVC:     {'SET' if TWILIO_MESSAGING_SERVICE_SID else 'NOT SET'}")
    logger.info(f"  ENABLE_DEMO_USERS:  {ENABLE_DEMO_USERS}")
    logger.info(f"  DEMO_RESET_PW:      {DEMO_RESET_PASSWORDS}")
    logger.info(f"  ENABLE_QUICK_LOGIN: {ENABLE_QUICK_LOGIN}")
    logger.info(f"  ENABLE_DEBUG_EP:    {ENABLE_DEBUG_ENDPOINTS}")
    logger.info(f"  ONBOARDING_V2:     {ENABLE_ONBOARDING_V2}")
    logger.info(f"  AUTO_TRIAL:        {ENABLE_AUTO_TRIAL}")
    logger.info(f"  DEFECTS_V2:        {ENABLE_DEFECTS_V2}")
    logger.info(f"  STEPUP_CHANNEL:     {STEPUP_CHANNEL}")
    logger.info(f"  STEPUP_EMAIL:       {'****' + STEPUP_EMAIL[-10:] if len(STEPUP_EMAIL) > 10 else STEPUP_EMAIL or 'NOT SET'}")
    logger.info(f"  STEPUP_TTL:         {STEPUP_TTL_SECONDS}s")
    logger.info(f"  STEPUP_GRANT:       {STEPUP_GRANT_SECONDS}s")
    logger.info(f"  SMTP_HOST:          {SMTP_HOST}")
    logger.info(f"  SMTP_PORT:          {SMTP_PORT}")
    logger.info(f"  SMTP_USER:          {'****' + SMTP_USER[-10:] if len(SMTP_USER) > 10 else SMTP_USER or 'NOT SET'}")
    logger.info(f"  SMTP_PASS:          {'SET' if SMTP_PASS else 'NOT SET'}")
    logger.info(f"  GI_BASE_URL:        {GI_BASE_URL or 'NOT SET'}")
    logger.info(f"  GI_API_KEY_ID:      {'SET' if GI_API_KEY_ID else 'NOT SET'}")
    logger.info(f"  GI_API_SECRET:      {'SET' if GI_API_SECRET else 'NOT SET'}")
    logger.info(f"  PAYPLUS_ENV:        {PAYPLUS_ENV}")
    logger.info(f"  PAYPLUS_API_KEY:    {'SET (' + str(len(PAYPLUS_API_KEY)) + ' chars)' if PAYPLUS_API_KEY else 'NOT SET'}")
    logger.info(f"  PAYPLUS_SECRET_KEY: {'SET' if PAYPLUS_SECRET_KEY else 'NOT SET'}")
    logger.info(f"  PAYPLUS_PAGE_UID:   {'SET' if PAYPLUS_PAYMENT_PAGE_UID else 'NOT SET'}")
    logger.info(f"  PAYPLUS_TERM_UID:   {'SET' if PAYPLUS_TERMINAL_UID else 'NOT SET'}")
    logger.info(f"  PAYPLUS_CALLBACK:   {PAYPLUS_CALLBACK_URL or 'NOT SET'}")
    logger.info("=" * 60)
    logger.info("Isolation guard PASSED — all required vars present.")
    logger.info("=" * 60)


log_sanitized_startup()
