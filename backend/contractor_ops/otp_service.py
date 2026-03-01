import os
import hashlib
import secrets
import logging
import uuid
import time as _time
from datetime import datetime, timezone, timedelta
from .msg_logger import log_msg_delivery, log_msg_queued, mask_phone

logger = logging.getLogger(__name__)

STUB_CODE = "000000"


class OTPService:
    def __init__(self, db, sms_client=None,
                 ttl_seconds=600, max_attempts=5, rate_limit_seconds=90,
                 resend_max_15min=3, resend_max_daily=10,
                 sms_mode='stub', app_mode='dev'):
        self.db = db
        self.sms_client = sms_client
        self.code_length = 6
        self.ttl_seconds = ttl_seconds
        self.max_attempts = max_attempts
        self.rate_limit_seconds = rate_limit_seconds
        self.resend_max_15min = resend_max_15min
        self.resend_max_daily = resend_max_daily
        self.sms_mode = sms_mode
        self.app_mode = app_mode
        self.lockout_minutes = 15

    def _generate_code(self):
        if self.sms_mode == 'stub':
            return STUB_CODE
        return ''.join([str(secrets.randbelow(10)) for _ in range(self.code_length)])

    def _hash_code(self, code):
        return hashlib.sha256(code.encode('utf-8')).hexdigest()

    def _verify_code(self, code, hashed):
        return self._hash_code(code) == hashed

    async def _check_daily_limit(self, phone_e164):
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        count = await self.db.otp_metrics.count_documents({
            'phone': phone_e164,
            'event': 'otp_sms_sent',
            'timestamp': {'$gte': day_start},
        })
        return count < self.resend_max_daily

    async def _check_15min_limit(self, phone_e164):
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        count = await self.db.otp_metrics.count_documents({
            'phone': phone_e164,
            'event': 'otp_sms_sent',
            'timestamp': {'$gte': cutoff},
        })
        return count < self.resend_max_15min

    async def _log_metric(self, event, phone_e164, extra=None):
        doc = {
            'event': event,
            'phone': phone_e164,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            doc.update(extra)
        try:
            await self.db.otp_metrics.insert_one(doc)
        except Exception as e:
            logger.warning(f"[OTP-METRIC] Failed to log {event}: {e}")

    async def request_otp(self, phone_e164):
        t_total = _time.perf_counter()
        now = datetime.now(timezone.utc)
        rid = str(uuid.uuid4())[:8]

        masked = mask_phone(phone_e164)
        logger.info(
            f"[OTP-REQUEST] rid={rid} phone={masked} "
            f"SMS_MODE={self.sms_mode} APP_MODE={self.app_mode}"
        )

        existing = await self.db.otp_codes.find_one(
            {'phone': phone_e164, 'locked_until': {'$gt': now.isoformat()}},
            {'_id': 0}
        )
        if existing:
            return {
                'success': False,
                'error': 'too_many_attempts',
                'locked_until': existing.get('locked_until', ''),
                'message': 'חשבון נעול. נסה שוב מאוחר יותר.'
            }

        last_otp = await self.db.otp_codes.find_one(
            {'phone': phone_e164},
            {'_id': 0},
        )

        if last_otp and last_otp.get('last_sent_at'):
            last_sent = datetime.fromisoformat(last_otp['last_sent_at'])
            elapsed = (now - last_sent).total_seconds()
            if elapsed < self.rate_limit_seconds:
                wait_secs = int(self.rate_limit_seconds - elapsed)
                ds = last_otp.get('delivery_status', '')
                if ds in ('queued', 'sent') and elapsed < 15:
                    return {
                        'success': True,
                        'status': 'queued',
                        'rid': last_otp.get('rid', rid),
                        'expires_in': self.ttl_seconds,
                        'message': 'קוד אימות כבר בדרך',
                        'retry_after': wait_secs,
                        'idempotent': True,
                    }
                return {
                    'success': False,
                    'error': 'rate_limited',
                    'message': f'נא להמתין {wait_secs} שניות לפני שליחה חוזרת.',
                    'wait_seconds': wait_secs,
                }

        if not await self._check_15min_limit(phone_e164):
            return {
                'success': False,
                'error': 'rate_limited',
                'message': 'יותר מדי בקשות. נסה שוב בעוד מספר דקות.',
            }

        if not await self._check_daily_limit(phone_e164):
            return {
                'success': False,
                'error': 'rate_limited',
                'message': 'הגעת למגבלה היומית. נסה שוב מחר.',
            }

        code = self._generate_code()
        hashed = self._hash_code(code)
        expires_at = (now + timedelta(seconds=self.ttl_seconds)).isoformat()

        await self.db.otp_codes.delete_many({'phone': phone_e164})

        otp_doc = {
            'id': str(uuid.uuid4()),
            'rid': rid,
            'phone': phone_e164,
            'hashed_code': hashed,
            'expires_at': expires_at,
            'attempts': 0,
            'locked_until': None,
            'last_sent_at': now.isoformat(),
            'created_at': now.isoformat(),
            'delivery_status': 'queued',
            'channel_used': 'pending',
        }
        await self.db.otp_codes.insert_one(otp_doc)

        total_ms = round((_time.perf_counter() - t_total) * 1000, 1)
        logger.info(
            f"[OTP-PERF] rid={rid} total_ms={total_ms} phone={masked} status=queued"
        )
        log_msg_queued(msg_type="otp", rid=rid, phone_masked=masked)

        result = {
            'success': True,
            'status': 'queued',
            'rid': rid,
            'expires_in': self.ttl_seconds,
            'message': 'קוד אימות נשלח',
        }

        if self.sms_mode == 'stub' and self.app_mode == 'dev':
            result['otp_debug_code'] = code

        result['_code'] = code

        return result

    async def deliver_otp_background(self, phone_e164: str, code: str, rid: str):
        masked = mask_phone(phone_e164)
        channel_used = 'stub'
        delivery_status = 'sent'
        provider_message_id = ''

        try:
            if self.sms_mode == 'stub':
                if self.app_mode == 'dev':
                    logger.info(f"[OTP-STUB] rid={rid} phone={masked} code={code}")
                else:
                    logger.info(f"[OTP-STUB] rid={rid} phone={masked} (code hidden in non-dev)")
                log_msg_delivery(
                    msg_type="otp", rid=rid, channel="stub", result="sent",
                    phone_masked=masked,
                )
                await self._log_metric('otp_sms_sent', phone_e164, {'channel': 'stub', 'rid': rid})
            else:
                if not self.sms_client or not self.sms_client.enabled:
                    logger.error(f"[OTP] rid={rid} SMS client not configured, cannot send OTP to {masked}")
                    delivery_status = 'failed'
                    channel_used = 'none'
                    log_msg_delivery(
                        msg_type="otp", rid=rid, channel="sms", result="failed",
                        error_code="sms_not_configured", phone_masked=masked,
                    )
                    await self._log_metric('otp_verify_failed', phone_e164, {'reason': 'sms_not_configured', 'rid': rid})
                else:
                    text = f"BrikOps: קוד האימות שלך הוא {code}. בתוקף {self.ttl_seconds // 60} דקות."
                    logger.info(f"[OTP] rid={rid} sending SMS to {masked}")

                    t_sms = _time.perf_counter()
                    result = await self.sms_client.send_sms(phone_e164, text, context='otp')
                    sms_ms = round((_time.perf_counter() - t_sms) * 1000, 1)

                    if result.get('status') == 'sent':
                        channel_used = 'sms'
                        provider_message_id = result.get('provider_message_id', '')
                        logger.info(f"[OTP] rid={rid} SMS sent to {masked} sid={provider_message_id} ms={sms_ms}")
                        log_msg_delivery(
                            msg_type="otp", rid=rid, channel="sms", result="sent",
                            external_ms=sms_ms,
                            provider_status=provider_message_id[:20] if provider_message_id else "",
                            phone_masked=masked,
                        )
                        await self._log_metric('otp_sms_sent', phone_e164, {'channel': 'sms', 'rid': rid, 'sms_ms': sms_ms})
                    else:
                        channel_used = 'none'
                        delivery_status = 'failed'
                        error_msg = result.get('error', '')[:100]
                        logger.error(f"[OTP] rid={rid} SMS failed for {masked}: {error_msg}")
                        log_msg_delivery(
                            msg_type="otp", rid=rid, channel="sms", result="failed",
                            external_ms=sms_ms, error_code=error_msg,
                            phone_masked=masked,
                        )
                        await self._log_metric('otp_verify_failed', phone_e164, {'reason': f'sms_failed:{error_msg}', 'rid': rid})

            await self.db.otp_codes.update_one(
                {'rid': rid},
                {'$set': {
                    'delivery_status': delivery_status,
                    'channel_used': channel_used,
                    'provider_message_id': provider_message_id,
                    'delivered_at': datetime.now(timezone.utc).isoformat(),
                }}
            )

        except Exception as e:
            logger.exception(f"[OTP-DELIVERY] rid={rid} phone={masked} EXCEPTION: {str(e)[:200]}")
            log_msg_delivery(
                msg_type="otp", rid=rid, channel="none", result="failed",
                error_code=f"exception:{str(e)[:80]}", phone_masked=masked,
            )
            try:
                await self.db.otp_codes.update_one(
                    {'rid': rid},
                    {'$set': {'delivery_status': 'failed', 'delivery_error': str(e)[:200]}}
                )
            except Exception:
                pass

    async def verify_otp(self, phone_e164, code):
        now = datetime.now(timezone.utc)
        masked = mask_phone(phone_e164)
        logger.info(f"[OTP-VERIFY] phone={masked}")

        otp_doc = await self.db.otp_codes.find_one(
            {'phone': phone_e164},
            {'_id': 0}
        )

        if not otp_doc:
            logger.warning(f"[OTP-VERIFY] no_otp_found for {masked}")
            await self._log_metric('otp_verify_failed', phone_e164, {'reason': 'no_otp'})
            return {'success': False, 'error': 'no_otp', 'message': 'לא נמצא קוד אימות. בקש קוד חדש.'}

        if otp_doc.get('locked_until') and otp_doc['locked_until'] > now.isoformat():
            await self._log_metric('otp_verify_failed', phone_e164, {'reason': 'locked'})
            return {
                'success': False,
                'error': 'locked',
                'message': 'חשבון נעול. נסה שוב מאוחר יותר.',
                'locked_until': otp_doc['locked_until']
            }

        if otp_doc['expires_at'] < now.isoformat():
            await self.db.otp_codes.delete_one({'phone': phone_e164})
            await self._log_metric('otp_verify_failed', phone_e164, {'reason': 'expired'})
            return {'success': False, 'error': 'expired', 'message': 'קוד אימות פג תוקף. בקש קוד חדש.'}

        attempts = otp_doc.get('attempts', 0) + 1

        if not self._verify_code(code, otp_doc['hashed_code']):
            update = {'$set': {'attempts': attempts}}
            if attempts >= self.max_attempts:
                locked_until = (now + timedelta(minutes=self.lockout_minutes)).isoformat()
                update['$set']['locked_until'] = locked_until
                await self.db.otp_codes.update_one({'phone': phone_e164}, update)
                await self._log_metric('otp_verify_failed', phone_e164, {'reason': 'locked_max_attempts', 'attempts': attempts})
                return {
                    'success': False,
                    'error': 'locked',
                    'message': f'יותר מדי ניסיונות. החשבון ננעל ל-{self.lockout_minutes} דקות.',
                    'locked_until': locked_until
                }

            await self.db.otp_codes.update_one({'phone': phone_e164}, update)
            remaining = self.max_attempts - attempts
            await self._log_metric('otp_verify_failed', phone_e164, {'reason': 'invalid_code', 'attempts': attempts})
            return {
                'success': False,
                'error': 'invalid_code',
                'message': f'קוד שגוי. נותרו {remaining} ניסיונות.',
                'remaining_attempts': remaining
            }

        await self.db.otp_codes.update_one(
            {'phone': phone_e164},
            {'$set': {'verified_at': datetime.now(timezone.utc).isoformat()}}
        )
        await self.db.otp_codes.delete_one({'phone': phone_e164})
        await self._log_metric('otp_verify_success', phone_e164)
        logger.info(f"[OTP-VERIFY] SUCCESS phone={masked}")

        return {'success': True, 'message': 'אומת בהצלחה'}
