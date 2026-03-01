import logging
import uuid
import time as _time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_shared_sms_httpx = None

def _get_sms_httpx():
    global _shared_sms_httpx
    import httpx
    if _shared_sms_httpx is None or _shared_sms_httpx.is_closed:
        _shared_sms_httpx = httpx.AsyncClient(timeout=15)
    return _shared_sms_httpx


class SMSClient:
    def __init__(self, account_sid: str = '', auth_token: str = '',
                 from_number: str = '', messaging_service_sid: str = '', db=None):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.messaging_service_sid = messaging_service_sid
        self.db = db
        self.enabled = bool(account_sid and auth_token and (from_number or messaging_service_sid))

    async def send_sms(self, to_phone: str, text: str, context: str = '') -> dict:
        ts = datetime.now(timezone.utc).isoformat()
        sender = self.messaging_service_sid or self.from_number
        event = {
            'id': str(uuid.uuid4()),
            'to_phone': to_phone,
            'from_phone': sender,
            'text': text[:1600],
            'context': context,
            'status': 'pending',
            'provider': 'twilio',
            'provider_message_id': '',
            'error': '',
            'created_at': ts,
        }

        if not self.enabled:
            event['status'] = 'skipped_disabled'
            event['error'] = 'Twilio not configured'
            logger.info(f"[SMS] DRY-RUN to={to_phone} context={context} (Twilio disabled)")
            if self.db is not None:
                try:
                    await self.db.sms_events.insert_one(event)
                except Exception as e:
                    logger.error(f"[SMS] failed to save sms_event: {e}")
            return event

        try:
            import httpx
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            data = {
                'To': to_phone,
                'Body': text,
            }
            if self.messaging_service_sid:
                data['MessagingServiceSid'] = self.messaging_service_sid
            else:
                data['From'] = self.from_number

            client = _get_sms_httpx()
            resp = await client.post(url, data=data, auth=(self.account_sid, self.auth_token))

            if resp.status_code in (200, 201):
                resp_data = resp.json()
                event['status'] = 'sent'
                event['provider_message_id'] = resp_data.get('sid', '')
                logger.info(f"[SMS] sent to={to_phone} sid={event['provider_message_id']} context={context}")
            else:
                event['status'] = 'failed'
                event['error'] = resp.text[:500]
                logger.error(f"[SMS] failed to={to_phone}: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            event['status'] = 'failed'
            event['error'] = str(e)[:500]
            logger.error(f"[SMS] exception sending to={to_phone}: {e}")

        if self.db is not None:
            try:
                await self.db.sms_events.insert_one(event)
            except Exception as e:
                logger.error(f"[SMS] failed to save sms_event: {e}")

        return event
