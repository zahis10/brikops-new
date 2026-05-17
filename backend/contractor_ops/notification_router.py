from fastapi import APIRouter, HTTPException, Request, Response
from typing import Optional, List, Callable
import logging
import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from contractor_ops.schemas import NotificationJobResponse, ManualNotifyRequest
from contractor_ops.notification_service import NotificationEngine
from contractor_ops.task_image_guard import require_task_image
from contractor_ops.rate_limit import check_reminder_rate_limit

logger = logging.getLogger(__name__)

_engine: Optional[NotificationEngine] = None
_wa_verify_token: str = ""
_meta_app_secret: str = ""


def set_engine(engine: NotificationEngine):
    global _engine
    _engine = engine


def set_wa_verify_token(token: str):
    global _wa_verify_token
    _wa_verify_token = token


def set_meta_app_secret(secret: str):
    global _meta_app_secret
    _meta_app_secret = secret
    if not secret:
        logger.warning("[WA:WEBHOOK] META_APP_SECRET not configured — signature verification DISABLED")


def get_engine() -> NotificationEngine:
    if _engine is None:
        raise RuntimeError("NotificationEngine not initialized")
    return _engine


def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    if not _meta_app_secret:
        logger.warning("[WEBHOOK] META_APP_SECRET not configured — rejecting webhook request")
        return False
    expected = hmac.new(
        _meta_app_secret.encode('utf-8'),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    provided = signature_header.replace('sha256=', '')
    return hmac.compare_digest(expected, provided)


def create_notification_router(require_roles_fn: Callable, get_current_user_fn: Callable) -> APIRouter:
    from fastapi import Depends

    router = APIRouter(prefix="/api")

    @router.post("/tasks/{task_id}/notify")
    async def manual_notify(task_id: str, body: ManualNotifyRequest,
                            user: dict = Depends(require_roles_fn('project_manager', 'management_team'))):
        engine = get_engine()
        db = engine.db

        task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
        if not task:
            raise HTTPException(status_code=404, detail='Task not found')

        if not task.get('assignee_id') and not task.get('company_id'):
            raise HTTPException(status_code=400, detail='Task has no assignee or company assigned')

        # Rate limit: shared budget with contractor reminders + digest
        # (HIGH-N1 followup 2026-05-17 — anti-spam for compromised PM accounts)
        project_id = task.get('project_id')
        if project_id:
            rate_key = f"{user['id']}:{project_id}"
            if not await check_reminder_rate_limit(
                "manual_reminder", rate_key, max_requests=10, window_seconds=3600
            ):
                raise HTTPException(
                    status_code=429,
                    detail="יותר מדי תזכורות ידניות בשעה האחרונה — חכה לפני שליחה נוספת",
                )

        await require_task_image(db, task_id)

        job = await engine.enqueue(
            task_id=task_id,
            event_type='manual_send',
            created_by=user['id'],
            custom_message=body.message or '',
        )
        if not job:
            raise HTTPException(status_code=400, detail='Could not enqueue notification (no target phone found)')

        result = await engine.process_job(job)
        return {
            'success': True,
            'job_id': job.get('id'),
            'status': result.get('status'),
            'message': 'הודעה נשלחה בהצלחה' if result.get('status') == 'sent' else f"סטטוס: {result.get('status')}",
        }

    @router.get("/tasks/{task_id}/notifications", response_model=List[NotificationJobResponse])
    async def task_notifications(task_id: str,
                                 user: dict = Depends(get_current_user_fn)):
        engine = get_engine()
        db = engine.db

        task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
        if not task:
            raise HTTPException(status_code=404, detail='Task not found')

        if user['role'] == 'viewer':
            raise HTTPException(status_code=403, detail='Viewers cannot access notification history')
        if user['role'] == 'contractor':
            if task.get('assignee_id') != user['id'] and task.get('company_id') != user.get('company_id'):
                raise HTTPException(status_code=403, detail='Access denied to this task notifications')

        jobs = await db.notification_jobs.find(
            {'task_id': task_id}, {'_id': 0}
        ).sort('created_at', -1).to_list(100)
        return [NotificationJobResponse(**j) for j in jobs]

    @router.post("/notifications/{job_id}/retry")
    async def retry_notification(job_id: str,
                                 user: dict = Depends(require_roles_fn('project_manager', 'management_team'))):
        engine = get_engine()
        db = engine.db

        job_doc = await db.notification_jobs.find_one({'id': job_id}, {'_id': 0})

        # Rate limit: shared budget with contractor reminders + digest
        # (HIGH-N1 followup 2026-05-17)
        if job_doc and job_doc.get('task_id'):
            task_for_rl = await db.tasks.find_one(
                {'id': job_doc['task_id']},
                {'_id': 0, 'project_id': 1},
            )
            project_id = (task_for_rl or {}).get('project_id')
            if project_id:
                rate_key = f"{user['id']}:{project_id}"
                if not await check_reminder_rate_limit(
                    "manual_reminder", rate_key, max_requests=10, window_seconds=3600
                ):
                    raise HTTPException(
                        status_code=429,
                        detail="יותר מדי תזכורות ידניות בשעה האחרונה — חכה לפני שליחה נוספת",
                    )
            await require_task_image(db, job_doc['task_id'])

        result = await engine.retry_job(job_id, actor_id=user['id'])
        if not result:
            raise HTTPException(status_code=404, detail='Notification job not found')
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])

        return {
            'success': True,
            'job_id': job_id,
            'status': result.get('status'),
        }

    @router.get("/webhooks/whatsapp")
    async def whatsapp_webhook_verify(request: Request):
        params = request.query_params
        mode = params.get('hub.mode')
        token = params.get('hub.verify_token')
        challenge = params.get('hub.challenge')

        token_match = (token == _wa_verify_token) if _wa_verify_token else False
        logger.info(f"[WA] verify request: mode={mode} challenge_present={bool(challenge)} token_match={token_match} verify_token_set={bool(_wa_verify_token)}")

        if mode == 'subscribe' and token_match and challenge:
            logger.info("[WA] webhook verified successfully")
            return Response(content=challenge, media_type="text/plain")

        logger.warning(f"[WA] verify FAILED: mode={mode} token_match={token_match}")
        raise HTTPException(status_code=403, detail='Verification failed')

    @router.post("/webhooks/whatsapp")
    async def whatsapp_webhook_receive(request: Request):
        engine = get_engine()
        db = engine.db

        raw_body = await request.body()

        sig_header = request.headers.get('X-Hub-Signature-256', '')
        logger.info(f"[WA:WEBHOOK] received body_len={len(raw_body)} has_signature={bool(sig_header)} content_type={request.headers.get('content-type', '')}")
        if not _meta_app_secret:
            logger.error("[WA] META_APP_SECRET not configured — rejecting webhook request")
            raise HTTPException(status_code=503, detail='Webhook signature verification not configured')
        if not sig_header:
            logger.error("[WA] signature_missing - X-Hub-Signature-256 header absent, rejecting request")
            raise HTTPException(status_code=401, detail='Missing signature')
        if not _verify_signature(raw_body, sig_header):
            logger.error("[WA] signature_invalid - HMAC mismatch, rejecting request")
            raise HTTPException(status_code=401, detail='Invalid signature')
        logger.info("[WA] signature_valid")

        try:
            import json
            body = json.loads(raw_body)
        except Exception:
            raise HTTPException(status_code=400, detail='Invalid JSON')

        meta_object = body.get('object', '')
        entries = body.get('entry', [])
        processed = []
        events_saved = 0
        duplicates_skipped = 0

        for entry in entries:
            entry_id = entry.get('id', '')
            changes = entry.get('changes', [])

            for change in changes:
                value = change.get('value', {})
                metadata = value.get('metadata', {})
                phone_number_id = metadata.get('phone_number_id', '')

                statuses = value.get('statuses', [])
                for status_update in statuses:
                    provider_id = status_update.get('id', '')
                    wa_status = status_update.get('status', '')
                    recipient = status_update.get('recipient_id', '')

                    event_doc = {
                        'id': str(uuid.uuid4()),
                        'received_at': datetime.now(timezone.utc).isoformat(),
                        'provider': 'meta_whatsapp',
                        'meta_object': meta_object,
                        'entry_id': entry_id,
                        'phone_number_id': phone_number_id,
                        'event_type': 'status',
                        'wa_message_id': provider_id,
                        'from_phone': '',
                        'to_phone': recipient,
                        'status': wa_status,
                        'raw_payload': status_update,
                    }
                    try:
                        # Atomic upsert — race-safe dedup.
                        # Matches audit recommendation: (wa_message_id, event_type, status) is the unique key.
                        # See Batch S5a fix for code-audit CRITICAL finding 2026-04-24.
                        result = await db.whatsapp_events.update_one(
                            {
                                'wa_message_id': provider_id,
                                'event_type': 'status',
                                'status': wa_status,
                            },
                            {'$setOnInsert': event_doc},
                            upsert=True,
                        )
                        if result.upserted_id is None:
                            duplicates_skipped += 1
                            logger.info(f"[WA] duplicate status event skipped: {provider_id}/{wa_status}")
                            continue
                        events_saved += 1
                    except Exception as e:
                        logger.error(f"[WA] failed to save status event: {e}")
                        continue

                    masked_recipient = (recipient[:3] + '****' + recipient[-4:]) if len(recipient) > 8 else '****'
                    logger.info(f"[WA] status_update wa_id={provider_id} status={wa_status} to={masked_recipient}")

                    status_map = {
                        'sent': 'sent',
                        'delivered': 'delivered',
                        'read': 'read',
                        'failed': 'failed',
                    }
                    mapped_status = status_map.get(wa_status)
                    if mapped_status and provider_id:
                        result = await engine.process_webhook(provider_id, mapped_status)
                        if result:
                            processed.append(result)

                messages = value.get('messages', [])
                for msg in messages:
                    msg_id = msg.get('id', '')
                    from_phone = msg.get('from', '')
                    msg_type = msg.get('type', '')
                    msg_text = ''
                    if msg_type == 'text':
                        msg_text = msg.get('text', {}).get('body', '')

                    event_doc = {
                        'id': str(uuid.uuid4()),
                        'received_at': datetime.now(timezone.utc).isoformat(),
                        'provider': 'meta_whatsapp',
                        'meta_object': meta_object,
                        'entry_id': entry_id,
                        'phone_number_id': phone_number_id,
                        'event_type': 'message',
                        'wa_message_id': msg_id,
                        'from_phone': from_phone,
                        'to_phone': phone_number_id,
                        'status': '',
                        'message_type': msg_type,
                        'message_text': msg_text[:500] if msg_text else '',
                        'raw_payload': msg,
                    }
                    try:
                        result = await db.whatsapp_events.update_one(
                            {
                                'wa_message_id': msg_id,
                                'event_type': 'message',
                                'status': '',
                            },
                            {'$setOnInsert': event_doc},
                            upsert=True,
                        )
                        if result.upserted_id is None:
                            duplicates_skipped += 1
                            logger.info(f"[WA] duplicate message event skipped: {msg_id}")
                            continue
                        events_saved += 1
                    except Exception as e:
                        logger.error(f"[WA] failed to save message event: {e}")
                        continue

                    masked_from = (from_phone[:3] + '****' + from_phone[-4:]) if len(from_phone) > 8 else '****'
                    logger.info(f"[WA] incoming_message from={masked_from} wa_id={msg_id} type={msg_type} text={msg_text[:80]}")

        logger.info(f"[WA] webhook processed: {len(processed)} status updates linked, {events_saved} events saved to DB, {duplicates_skipped} duplicates skipped")
        return {
            'processed': len(processed),
            'events_saved': events_saved,
            'duplicates_skipped': duplicates_skipped,
            'results': processed,
        }

    return router


async def ensure_indexes(db):
    """Create unique compound index on whatsapp_events for atomic upsert dedup.

    Per Batch S5a fix (code-audit 2026-04-24): the (wa_message_id, event_type, status)
    tuple is the idempotency key for WhatsApp webhook events. This index makes the
    upsert in whatsapp_webhook_receive race-safe at the DB level.
    """
    try:
        await db.whatsapp_events.create_index(
            [('wa_message_id', 1), ('event_type', 1), ('status', 1)],
            unique=True,
            name='wa_message_id_event_type_status_unique',
            background=True,
        )
        logger.info("WhatsApp events indexes ensured")
    except Exception as e:
        logger.warning(f"WhatsApp events index creation: {e}")
