import os
import re
import hashlib
import uuid
import logging
import asyncio
import time as _time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

import httpx

from .msg_logger import log_msg_delivery, log_msg_queued, mask_phone, DeliveryTimer

logger = logging.getLogger(__name__)


def _make_absolute_url(relative_path: str) -> str:
    if not relative_path:
        return ""
    if relative_path.startswith("http://") or relative_path.startswith("https://"):
        return relative_path
    if relative_path.startswith("s3://"):
        from services.object_storage import generate_url
        resolved = generate_url(relative_path)
        if resolved and resolved.startswith("https://"):
            return resolved
        logger.warning(f"[NOTIFY] s3:// resolve failed for {relative_path[:40]}, got {str(resolved)[:40]}")
        return ""
    domain = os.environ.get('PUBLIC_APP_URL', '').rstrip('/')
    if not domain:
        domain = os.environ.get('APP_BASE_URL', '')
    if not domain:
        raw = os.environ.get('REPLIT_DOMAINS', os.environ.get('REPLIT_DEV_DOMAIN', ''))
        if raw:
            if ',' in raw:
                raw = raw.split(',')[0]
            domain = f"https://{raw}"
    if not domain:
        return relative_path
    return f"{domain.rstrip('/')}/{relative_path.lstrip('/')}"

E164_PATTERN = re.compile(r'^\+[1-9]\d{6,14}$')

_WA_FALLBACK_IMAGE_RAW = os.environ.get('WA_FALLBACK_IMAGE_URL', 's3://public/assets/brikops-logo.png')


def _resolve_fallback_image() -> str:
    from services.object_storage import generate_url
    raw = _WA_FALLBACK_IMAGE_RAW
    if raw.startswith('s3://'):
        return generate_url(raw)
    return raw


WA_FALLBACK_IMAGE_URL = _WA_FALLBACK_IMAGE_RAW


def validate_e164(phone: str) -> bool:
    if not phone:
        return False
    return bool(E164_PATTERN.match(phone))


def generate_idempotency_key(task_id: str, event_type: str, assignee_id: str, timestamp: Optional[datetime] = None) -> str:
    ts = timestamp or datetime.now(timezone.utc)
    minute_bucket = ts.strftime('%Y%m%d%H%M')
    raw = f"{task_id}:{event_type}:{assignee_id}:{minute_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def build_whatsapp_payload(task: dict, project: dict = None, building: dict = None,
                           floor: dict = None, unit: dict = None,
                           assignee: dict = None, company: dict = None,
                           task_link: str = "", custom_message: str = "") -> dict:
    category_labels = {
        'electrical': 'חשמל', 'plumbing': 'אינסטלציה', 'hvac': 'מיזוג',
        'painting': 'צביעה', 'flooring': 'ריצוף', 'carpentry': 'נגרות',
        'masonry': 'בנייה', 'windows': 'חלונות', 'doors': 'דלתות', 'general': 'כללי',
    }
    priority_labels = {
        'low': 'נמוך', 'medium': 'בינוני', 'high': 'גבוה', 'critical': 'קריטי',
    }
    status_labels = {
        'open': 'פתוח', 'assigned': 'שויך', 'in_progress': 'בביצוע',
        'waiting_verify': 'ממתין לאימות', 'closed': 'סגור', 'reopened': 'נפתח מחדש',
        'pending_contractor_proof': 'ממתין להוכחת קבלן',
        'pending_manager_approval': 'ממתין לאישור מנהל',
    }

    payload = {
        'task_id': task.get('id', ''),
        'title': task.get('title', ''),
        'description': task.get('description', ''),
        'category': category_labels.get(task.get('category', ''), task.get('category', '')),
        'priority': priority_labels.get(task.get('priority', ''), task.get('priority', '')),
        'status': status_labels.get(task.get('status', ''), task.get('status', '')),
        'due_date': task.get('due_date', ''),
        'project_name': project.get('name', '') if project else '',
        'building_name': building.get('name', '') if building else '',
        'floor_name': floor.get('name', '') if floor else '',
        'unit_no': unit.get('unit_no', '') if unit else '',
        'assignee_name': assignee.get('name', '') if assignee else '',
        'company_name': company.get('name', '') if company else '',
        'short_ref': task.get('short_ref', task.get('id', '')[:8]),
        'display_number': task.get('display_number'),
        'task_link': task_link,
        'custom_message': custom_message,
    }
    return payload


def format_text_message(payload: dict) -> str:
    lines = [
        f"📋 *ליקוי חדש - {payload.get('title', '')}*",
        "",
        f"🏗️ פרויקט: {payload.get('project_name', '')}",
        f"🏢 בניין: {payload.get('building_name', '')}",
        f"🔢 קומה: {payload.get('floor_name', '')}",
        f"🚪 דירה: {payload.get('unit_no', '')}",
        "",
        f"📂 קטגוריה: {payload.get('category', '')}",
        f"⚡ עדיפות: {payload.get('priority', '')}",
        f"📊 סטטוס: {payload.get('status', '')}",
    ]
    if payload.get('due_date'):
        lines.append(f"📅 תאריך יעד: {payload['due_date']}")
    if payload.get('description'):
        lines.append(f"\n📝 תיאור: {payload['description']}")
    if payload.get('custom_message'):
        lines.append(f"\n💬 הודעה: {payload['custom_message']}")
    if payload.get('pm_name') or payload.get('pm_phone'):
        pm_info = payload.get('pm_name', '')
        if payload.get('pm_phone'):
            pm_info += f" ({payload['pm_phone']})" if pm_info else payload['pm_phone']
        lines.append(f"\n👷 מנהל: {pm_info}")
    if payload.get('task_link'):
        link = payload['task_link']
        if '?' not in link:
            link = f"{link}/?src=wa"
        lines.append(f"\n🔗 לצפייה בליקוי: {link}")
    return "\n".join(lines)


def _now():
    return datetime.now(timezone.utc).isoformat()


class WhatsAppClient:
    def __init__(self, access_token: str = "", phone_number_id: str = "",
                 template_name: str = "", template_lang: str = "he",
                 enabled: bool = False):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.template_name = template_name
        self.template_lang = template_lang
        self.enabled = enabled
        self.api_url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"

    async def send_message(self, to_phone: str, payload: dict, defect_lang: str = None) -> dict:
        from config import WA_DEFECT_TEMPLATES, WA_DEFECT_DEFAULT_LANG

        if not self.enabled:
            logger.info(f"[DRY-RUN] WhatsApp message to {to_phone} — skipped (WHATSAPP_ENABLED=false)")
            dry_run_payload = {
                "dry_run": True,
                "message": "WhatsApp disabled, message logged only",
                "would_send": {
                    "to": to_phone,
                    "text": format_text_message(payload),
                    "image_url": payload.get('image_url'),
                },
            }
            logger.info(f"[DRY-RUN] Payload: {dry_run_payload}")
            return dry_run_payload

        if not validate_e164(to_phone):
            raise ValueError(f"Invalid E.164 phone number: {to_phone}")

        to_digits = to_phone.lstrip('+')
        image_url = payload.get('image_url')
        task_id = payload.get('task_id', '')

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        lang_key = defect_lang or WA_DEFECT_DEFAULT_LANG
        tpl_info = WA_DEFECT_TEMPLATES.get(lang_key)
        if not tpl_info and lang_key != 'en':
            logger.info(f"[WA] Language {lang_key} not found, falling back to en for task_id={task_id}")
            lang_key = 'en'
            tpl_info = WA_DEFECT_TEMPLATES.get(lang_key)

        if tpl_info:
            tpl_name = tpl_info['name']
            tpl_lang = tpl_info['lang']

            components = []

            fallback_image = _resolve_fallback_image()
            if image_url and image_url.startswith('https://'):
                effective_image = image_url
                image_source = 'task_attachment'
            elif fallback_image and fallback_image.startswith('https://'):
                effective_image = fallback_image
                image_source = 'fallback'
            else:
                effective_image = None
                image_source = 'none'

            if effective_image:
                components.append({
                    "type": "header",
                    "parameters": [
                        {"type": "image", "image": {"link": effective_image}}
                    ]
                })
            logger.info(f"[WA:IMAGE] task_id={task_id} source={image_source} url={str(effective_image)[:80] if effective_image else 'none'}")

            location_parts = [payload.get('project_name', '')]
            building = payload.get('building_name', '')
            unit = payload.get('unit_no', '')
            floor = payload.get('floor_name', '')
            sub_parts = []
            if building:
                sub_parts.append(building)
            if floor:
                sub_parts.append(f"קומה {floor}")
            if unit:
                sub_parts.append(f"דירה {unit}")
            if sub_parts:
                location_parts.append(' / '.join(sub_parts))
            location = ' - '.join(p for p in location_parts if p) or ''

            from config import WA_TEMPLATE_PARAM_MODE
            display_number = payload.get('display_number')
            if display_number:
                ref_text = f"#{display_number}"
            else:
                task_id_val = payload.get('task_id', '')
                ref_text = f"#{payload.get('short_ref') or task_id_val[:8]}"
            ref_param = {"type": "text", "text": ref_text}
            location_param = {"type": "text", "text": location}
            issue_param = {"type": "text", "text": payload.get('title', '')}
            if WA_TEMPLATE_PARAM_MODE == 'named':
                ref_param["parameter_name"] = "ref"
                location_param["parameter_name"] = "location"
                issue_param["parameter_name"] = "issue"
            components.append({
                "type": "body",
                "parameters": [ref_param, location_param, issue_param]
            })

            if task_id:
                components.append({
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [{"type": "text", "text": task_id}]
                })

            body = {
                "messaging_product": "whatsapp",
                "to": to_digits,
                "type": "template",
                "template": {
                    "name": tpl_name,
                    "language": {"code": tpl_lang},
                    "components": components,
                }
            }
            import json as _json
            logger.info(f"[WA:COMPONENTS] task_id={task_id} components={_json.dumps(components, ensure_ascii=False)}")
            logger.info(f"[WA:SEND] template={tpl_name} lang={tpl_lang} to={mask_phone(to_phone)} task_id={task_id} has_image={'yes' if effective_image else 'no'} is_fallback={not image_url or not image_url.startswith('https://')}")
        else:
            text = format_text_message(payload)
            body = {
                "messaging_product": "whatsapp",
                "to": to_digits,
                "type": "text",
                "text": {"body": text}
            }
            logger.info(f"[WA:SEND] text_message to={mask_phone(to_phone)} task_id={task_id}")

        import json as _json2
        logger.info(f"[WA:FULL_BODY] to={mask_phone(to_phone)} body={_json2.dumps(body, ensure_ascii=False)}")
        logger.info(f"[WA:SEND] api_url={self.api_url} to={mask_phone(to_phone)}")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self.api_url, json=body, headers=headers)

        logger.info(f"[WA:SEND] status={resp.status_code} to={mask_phone(to_phone)} task_id={task_id} body={resp.text[:500]}")
        if resp.status_code in (200, 201):
            data = resp.json()
            mid = data.get("messages", [{}])[0].get("id", "")
            logger.info(f"[WA:SEND] SUCCESS provider_message_id={mid} to={mask_phone(to_phone)} task_id={task_id}")
            return {"success": True, "provider_message_id": mid}
        else:
            error_msg = resp.text[:500]
            tpl_used = tpl_info['name'] if tpl_info else 'text_message'
            has_image = bool(image_url and image_url.startswith('https://'))
            logger.error(
                f"[WA] API error sending to {mask_phone(to_phone)}: "
                f"status={resp.status_code} template={tpl_used} "
                f"has_task_image={has_image} used_fallback={not has_image} "
                f"task_id={task_id} error={error_msg}"
            )
            raise RuntimeError(f"WhatsApp API error ({resp.status_code}): {error_msg}")


class NotificationEngine:
    def __init__(self, db, wa_client: WhatsAppClient,
                 invite_template_name: str = "", invite_template_lang: str = "he"):
        self.db = db
        self.wa_client = wa_client
        self.invite_template_name = invite_template_name
        self.invite_template_lang = invite_template_lang
        self.sms_client = None

    @staticmethod
    def _normalize_israeli_phone(phone: str) -> str:
        if not phone:
            return phone
        cleaned = phone.replace('-', '').replace(' ', '').strip()
        if cleaned.startswith('05') and len(cleaned) == 10:
            return '+972' + cleaned[1:]
        return cleaned

    async def _resolve_target_phone(self, task: dict) -> Optional[dict]:
        assignee_id = task.get('assignee_id')
        if assignee_id:
            user = await self.db.users.find_one({'id': assignee_id}, {'_id': 0})
            if user:
                phone = user.get('phone_e164') or user.get('phone', '')
                phone = self._normalize_israeli_phone(phone)
                if phone and validate_e164(phone):
                    return {
                        'phone_e164': phone,
                        'preferred_language': user.get('preferred_language') or 'he',
                    }
                logger.warning(f"[NOTIFY] Assignee {assignee_id} has invalid/missing phone: {mask_phone(phone) if phone else 'NONE'}")

        company_id = task.get('company_id')
        if company_id:
            company = await self.db.companies.find_one({'id': company_id}, {'_id': 0})
            if company:
                phone = company.get('phone_e164') or company.get('phone', '')
                phone = self._normalize_israeli_phone(phone)
                if phone and validate_e164(phone):
                    return {
                        'phone_e164': phone,
                        'preferred_language': 'he',
                    }
                logger.warning(f"[NOTIFY] Company {company_id} has invalid/missing phone: {mask_phone(phone) if phone else 'NONE'}")

        return None

    async def _enrich_payload(self, task: dict, custom_message: str = "", task_link: str = "") -> dict:
        project = await self.db.projects.find_one({'id': task.get('project_id')}, {'_id': 0}) if task.get('project_id') else None
        building = await self.db.buildings.find_one({'id': task.get('building_id')}, {'_id': 0}) if task.get('building_id') else None
        floor = await self.db.floors.find_one({'id': task.get('floor_id')}, {'_id': 0}) if task.get('floor_id') else None
        unit = await self.db.units.find_one({'id': task.get('unit_id')}, {'_id': 0}) if task.get('unit_id') else None
        assignee = await self.db.users.find_one({'id': task.get('assignee_id')}, {'_id': 0}) if task.get('assignee_id') else None
        company = await self.db.companies.find_one({'id': task.get('company_id')}, {'_id': 0}) if task.get('company_id') else None

        first_image_url = None
        attachment = await self.db.task_updates.find_one(
            {'task_id': task.get('id'), 'update_type': 'attachment'},
            {'_id': 0},
        )
        if attachment and attachment.get('attachment_url'):
            first_image_url = attachment['attachment_url']

        payload = build_whatsapp_payload(
            task, project, building, floor, unit, assignee, company,
            task_link=task_link, custom_message=custom_message,
        )
        if first_image_url:
            payload['image_url'] = _make_absolute_url(first_image_url)

        if task.get('created_by'):
            creator = await self.db.users.find_one({'id': task['created_by']}, {'_id': 0, 'phone_e164': 1, 'name': 1})
            if creator:
                payload['pm_phone'] = creator.get('phone_e164', '')
                payload['pm_name'] = creator.get('name', '')

        return payload

    async def enqueue(self, task_id: str, event_type: str, created_by: str,
                      custom_message: str = "", task_link: str = "") -> Optional[dict]:
        task = await self.db.tasks.find_one({'id': task_id}, {'_id': 0})
        if not task:
            logger.warning(f"[NOTIFY] Task {task_id} not found, skipping enqueue")
            return None

        resolved = await self._resolve_target_phone(task)
        if not resolved:
            logger.warning(f"[NOTIFY] No target phone for task {task_id}, skipping")
            return {'status': 'failed', 'id': str(uuid.uuid4()), 'error': 'אין מספר וואטסאפ תקין לקבלן'}

        target_phone = resolved['phone_e164']
        preferred_language = resolved['preferred_language']

        assignee_id = task.get('assignee_id', '')
        if assignee_id:
            assignee_user = await self.db.users.find_one({'id': assignee_id}, {'_id': 0, 'whatsapp_notifications_enabled': 1})
            if assignee_user and assignee_user.get('whatsapp_notifications_enabled') is False:
                logger.info(f"[NOTIFY] notification skipped — user disabled WhatsApp notifications (task={task_id}, user={assignee_id})")
                return {'status': 'skipped_optout', 'id': str(uuid.uuid4()), 'task_id': task_id}
        idem_key = generate_idempotency_key(task_id, event_type, assignee_id)

        existing = await self.db.notification_jobs.find_one({
            'idempotency_key': idem_key,
            'status': {'$nin': ['failed']},
        }, {'_id': 0})
        if existing:
            logger.info(f"[NOTIFY] Duplicate detected (idem_key={idem_key[:12]}…), skipping")
            return existing

        if not task_link:
            from contractor_ops.router import get_public_base_url
            base_url = get_public_base_url()
            task_link = f"{base_url}/tasks/{task_id}" if base_url else f"/tasks/{task_id}"

        payload = await self._enrich_payload(task, custom_message=custom_message, task_link=task_link)
        payload['defect_lang'] = preferred_language
        ts = _now()
        job = {
            'id': str(uuid.uuid4()),
            'task_id': task_id,
            'event_type': event_type,
            'target_phone': target_phone,
            'payload': payload,
            'status': 'queued',
            'channel': 'whatsapp',
            'attempts': 0,
            'max_attempts': 3,
            'provider_message_id': None,
            'last_error': None,
            'idempotency_key': idem_key,
            'created_by': created_by,
            'created_at': ts,
            'updated_at': ts,
            'next_retry_at': None,
        }
        await self.db.notification_jobs.insert_one(job)

        await self.db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'notification',
            'entity_id': job['id'],
            'action': 'enqueued',
            'actor_id': created_by,
            'payload': {'task_id': task_id, 'event_type': event_type, 'target_phone': target_phone, 'defect_lang': preferred_language},
            'created_at': ts,
        })

        logger.info(f"[NOTIFY] Enqueued job {job['id']} for task {task_id} event={event_type} defect_lang={preferred_language}")
        log_msg_queued(msg_type="task_notification", rid=job['id'], phone_masked=mask_phone(target_phone))
        return {k: v for k, v in job.items() if k != '_id'}

    async def attach_image_to_notification(self, task_id: str, attachment_id: str,
                                            image_url: str, actor_id: str,
                                            task_link: str = "") -> Optional[dict]:
        task = await self.db.tasks.find_one({'id': task_id}, {'_id': 0})
        if not task:
            logger.warning(f"[NOTIFY-IMG] Task {task_id} not found, skipping image attach")
            return None

        resolved = await self._resolve_target_phone(task)
        if not resolved:
            logger.warning(f"[NOTIFY-IMG] No target phone for task {task_id}, skipping image attach")
            await self.db.audit_events.insert_one({
                'id': str(uuid.uuid4()), 'entity_type': 'notification',
                'entity_id': task_id, 'action': 'image_attach_skipped',
                'actor_id': actor_id,
                'payload': {'task_id': task_id, 'reason': 'no_target_phone', 'attachment_id': attachment_id},
                'created_at': _now(),
            })
            return None

        target_phone = resolved['phone_e164']

        pending_job = await self.db.notification_jobs.find_one({
            'task_id': task_id,
            'status': {'$in': ['queued', 'pending']},
        }, {'_id': 0}, sort=[('created_at', -1)])

        ts = _now()

        if pending_job:
            payload = pending_job.get('payload', {})
            payload['image_url'] = _make_absolute_url(image_url)
            await self.db.notification_jobs.update_one(
                {'id': pending_job['id']},
                {'$set': {'payload': payload, 'updated_at': ts}},
            )
            await self.db.audit_events.insert_one({
                'id': str(uuid.uuid4()), 'entity_type': 'notification',
                'entity_id': pending_job['id'], 'action': 'image_attached_to_pending',
                'actor_id': actor_id,
                'payload': {'task_id': task_id, 'image_url': image_url, 'attachment_id': attachment_id},
                'created_at': ts,
            })
            logger.info(f"[NOTIFY-IMG] Updated pending job {pending_job['id']} with image_url")
            updated = await self.db.notification_jobs.find_one({'id': pending_job['id']}, {'_id': 0})
            return {k: v for k, v in updated.items() if k != '_id'} if updated else None

        sent_job = await self.db.notification_jobs.find_one({
            'task_id': task_id,
            'status': {'$in': ['sent', 'delivered', 'read', 'skipped_dry_run']},
        }, {'_id': 0}, sort=[('created_at', -1)])

        if sent_job:
            stable_raw = f"{task_id}:media_followup:{attachment_id}:{target_phone}"
            idem_key = hashlib.sha256(stable_raw.encode()).hexdigest()[:32]
            existing = await self.db.notification_jobs.find_one({
                'idempotency_key': idem_key, 'status': {'$nin': ['failed']},
            }, {'_id': 0})
            if existing:
                logger.info(f"[NOTIFY-IMG] Follow-up duplicate (idem_key={idem_key[:12]}…), skipping")
                return existing

            payload = await self._enrich_payload(task, task_link=task_link)
            payload['image_url'] = _make_absolute_url(image_url)

            followup = {
                'id': str(uuid.uuid4()), 'task_id': task_id,
                'event_type': 'media_followup', 'target_phone': target_phone,
                'payload': payload, 'status': 'queued',
                'attempts': 0, 'max_attempts': 3,
                'provider_message_id': None, 'last_error': None,
                'idempotency_key': idem_key, 'created_by': actor_id,
                'created_at': ts, 'updated_at': ts, 'next_retry_at': None,
            }
            await self.db.notification_jobs.insert_one(followup)
            await self.db.audit_events.insert_one({
                'id': str(uuid.uuid4()), 'entity_type': 'notification',
                'entity_id': followup['id'], 'action': 'media_followup_enqueued',
                'actor_id': actor_id,
                'payload': {'task_id': task_id, 'image_url': image_url,
                            'original_job_id': sent_job['id'], 'attachment_id': attachment_id},
                'created_at': ts,
            })
            logger.info(f"[NOTIFY-IMG] Created follow-up media job {followup['id']} for task {task_id}")
            return {k: v for k, v in followup.items() if k != '_id'}

        logger.info(f"[NOTIFY-IMG] No existing notification for task {task_id}, skipping image attach")
        await self.db.audit_events.insert_one({
            'id': str(uuid.uuid4()), 'entity_type': 'notification',
            'entity_id': task_id, 'action': 'image_attach_no_prior_notification',
            'actor_id': actor_id,
            'payload': {'task_id': task_id, 'attachment_id': attachment_id, 'reason': 'no_pending_or_sent_notification'},
            'created_at': _now(),
        })
        return None

    async def _try_sms_fallback(self, job: dict, wa_error: str) -> dict:
        job_id = job['id']
        ts = _now()
        if not self.sms_client or not self.sms_client.enabled:
            logger.info(f"[NOTIFY] SMS fallback not available for job {job_id}")
            return {'success': False, 'reason': 'sms_not_configured'}

        payload = job.get('payload', {})
        text = format_text_message(payload)
        try:
            sms_result = await self.sms_client.send_sms(job['target_phone'], text, context=f'defect_notification:{job_id}')
            if sms_result.get('status') == 'sent':
                sms_sid = sms_result.get('provider_message_id', '')
                await self.db.notification_jobs.update_one(
                    {'id': job_id},
                    {'$set': {
                        'status': 'sent',
                        'channel': 'sms',
                        'provider_message_id': sms_sid,
                        'last_error': f'wa_failed:{wa_error}',
                        'updated_at': ts,
                    }}
                )
                await self._audit_event(job_id, 'sent_sms_fallback', job.get('created_by', ''),
                                        {'sms_sid': sms_sid, 'wa_error': wa_error})
                logger.info(f"[NOTIFY] Job {job_id} sent via SMS fallback, sid={sms_sid}")
                return {'success': True, 'channel': 'sms', 'provider_message_id': sms_sid}
            return {'success': False, 'reason': sms_result.get('error', 'sms_failed')}
        except Exception as e:
            logger.error(f"[NOTIFY] SMS fallback exception for job {job_id}: {e}")
            return {'success': False, 'reason': str(e)[:200]}

    async def process_job(self, job: dict) -> dict:
        job_id = job['id']
        fresh_job = await self.db.notification_jobs.find_one({'id': job_id}, {'_id': 0})
        if fresh_job:
            job = fresh_job
        payload = job.get('payload', {})
        if not payload.get('image_url') and job.get('task_id'):
            attachment = await self.db.task_updates.find_one(
                {'task_id': job['task_id'], 'update_type': 'attachment',
                 'content_type': {'$regex': '^image/'}},
                {'_id': 0, 'attachment_url': 1, 'content_type': 1},
            )
            if not attachment:
                attachment = await self.db.task_updates.find_one(
                    {'task_id': job['task_id'], 'update_type': 'attachment'},
                    {'_id': 0, 'attachment_url': 1, 'content_type': 1},
                )
            if attachment and attachment.get('attachment_url'):
                payload['image_url'] = _make_absolute_url(attachment['attachment_url'])
                job['payload'] = payload
                await self.db.notification_jobs.update_one(
                    {'id': job_id}, {'$set': {'payload': payload}}
                )
        ts = _now()
        attempt = job.get('attempts', 0) + 1
        phone_masked = mask_phone(job.get('target_phone', '')) if job.get('target_phone') else ''
        event_type = job.get('event_type', 'task_notification')
        msg_type = 'invite' if event_type == 'invite_created' else 'task_notification'

        try:
            if not self.wa_client.enabled:
                logger.warning(f"[NOTIFY] WA disabled for job {job_id} -> trying SMS")
                log_msg_delivery(msg_type=msg_type, rid=job_id, channel="whatsapp", result="failed",
                                 error_code="whatsapp_disabled", phone_masked=phone_masked)
                sms_fallback = await self._try_sms_fallback(job, 'whatsapp_disabled')
                if sms_fallback.get('success'):
                    sms_pid = sms_fallback.get('provider_message_id', '')
                    log_msg_delivery(msg_type=msg_type, rid=job_id, channel="sms", result="sent",
                                     provider_status=sms_pid[:20], phone_masked=phone_masked,
                                     fallback_from="whatsapp")
                    return {'status': 'sent', 'job_id': job_id, 'channel': 'sms',
                            'provider_message_id': sms_pid}

                await self.db.notification_jobs.update_one(
                    {'id': job_id},
                    {'$set': {
                        'status': 'skipped_dry_run',
                        'attempts': attempt,
                        'updated_at': ts,
                        'last_error': None,
                    }}
                )
                await self._audit_event(job_id, 'skipped_dry_run', job.get('created_by', ''),
                                        {'reason': 'WHATSAPP_ENABLED=false, SMS not available'})
                log_msg_delivery(msg_type=msg_type, rid=job_id, channel="sms", result="failed",
                                 error_code="sms_not_configured", phone_masked=phone_masked,
                                 fallback_from="whatsapp")
                return {'status': 'skipped_dry_run', 'job_id': job_id}

            if not validate_e164(job.get('target_phone', '')):
                await self.db.notification_jobs.update_one(
                    {'id': job_id},
                    {'$set': {
                        'status': 'failed',
                        'attempts': attempt,
                        'last_error': f"Invalid phone: {job.get('target_phone', '')}",
                        'updated_at': ts,
                    }}
                )
                await self._audit_event(job_id, 'failed', job.get('created_by', ''),
                                        {'reason': 'invalid_phone'})
                log_msg_delivery(msg_type=msg_type, rid=job_id, channel="none", result="failed",
                                 error_code="invalid_phone", phone_masked=phone_masked)
                return {'status': 'failed', 'job_id': job_id}

            timer = DeliveryTimer()
            job_defect_lang = job.get('payload', {}).get('defect_lang')
            result = await self.wa_client.send_message(job['target_phone'], job.get('payload', {}), defect_lang=job_defect_lang)
            wa_ms = timer.elapsed_ms()

            provider_id = result.get('provider_message_id', '')
            if not provider_id:
                raise RuntimeError("WhatsApp API returned empty provider_message_id — cannot link to webhook")
            await self.db.notification_jobs.update_one(
                {'id': job_id},
                {'$set': {
                    'status': 'sent',
                    'channel': 'whatsapp',
                    'attempts': attempt,
                    'provider_message_id': provider_id,
                    'last_error': None,
                    'updated_at': ts,
                }}
            )
            await self._audit_event(job_id, 'sent', job.get('created_by', ''),
                                    {'provider_message_id': provider_id, 'channel': 'whatsapp'})
            log_msg_delivery(msg_type=msg_type, rid=job_id, channel="whatsapp", result="sent",
                             external_ms=wa_ms, provider_status=provider_id[:20],
                             phone_masked=phone_masked)
            return {'status': 'sent', 'job_id': job_id, 'provider_message_id': provider_id, 'channel': 'whatsapp'}

        except Exception as e:
            error_msg = str(e)[:500]
            logger.warning(f"[NOTIFY] WA failed for job {job_id}: {error_msg} -> trying SMS")
            log_msg_delivery(msg_type=msg_type, rid=job_id, channel="whatsapp", result="failed",
                             error_code=error_msg[:80], phone_masked=phone_masked)

            sms_timer = DeliveryTimer()
            sms_fallback = await self._try_sms_fallback(job, error_msg)
            sms_ms = sms_timer.elapsed_ms()
            if sms_fallback.get('success'):
                sms_pid = sms_fallback.get('provider_message_id', '')
                log_msg_delivery(msg_type=msg_type, rid=job_id, channel="sms", result="sent",
                                 external_ms=sms_ms, provider_status=sms_pid[:20],
                                 phone_masked=phone_masked, fallback_from="whatsapp")
                return {'status': 'sent', 'job_id': job_id, 'channel': 'sms',
                        'provider_message_id': sms_pid}

            max_attempts = job.get('max_attempts', 3)
            new_status = 'failed' if attempt >= max_attempts else 'queued'
            backoff_seconds = (2 ** attempt) * 10
            next_retry = (datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)).isoformat() if new_status == 'queued' else None

            await self.db.notification_jobs.update_one(
                {'id': job_id},
                {'$set': {
                    'status': new_status,
                    'attempts': attempt,
                    'last_error': error_msg,
                    'updated_at': ts,
                    'next_retry_at': next_retry,
                }}
            )
            await self._audit_event(job_id, 'send_failed', job.get('created_by', ''),
                                    {'error': error_msg, 'attempt': attempt, 'will_retry': new_status == 'queued',
                                     'sms_fallback_tried': True, 'sms_fallback_result': sms_fallback.get('reason', '')})
            log_msg_delivery(msg_type=msg_type, rid=job_id, channel="sms", result="failed",
                             external_ms=sms_ms, error_code=sms_fallback.get('reason', 'sms_failed')[:80],
                             phone_masked=phone_masked, fallback_from="whatsapp")
            return {'status': new_status, 'job_id': job_id, 'error': error_msg}

    async def enqueue_invite(self, invite_id: str, target_phone: str,
                              project_name: str, join_link: str,
                              inviter_name: str, role_label: str,
                              created_by: str) -> Optional[dict]:
        if not validate_e164(target_phone):
            logger.warning(f"[INVITE-NOTIFY] Invalid phone for invite {invite_id}")
            return None

        ts = _now()
        idem_raw = f"invite:{invite_id}:{target_phone}"
        idem_key = hashlib.sha256(idem_raw.encode()).hexdigest()[:32]

        existing = await self.db.notification_jobs.find_one({
            'idempotency_key': idem_key,
            'status': {'$nin': ['failed']},
        }, {'_id': 0})
        if existing:
            logger.info(f"[INVITE-NOTIFY] Duplicate invite notification (idem={idem_key[:12]}…), skipping")
            return existing

        job_id = str(uuid.uuid4())
        job = {
            'id': job_id,
            'task_id': None,
            'invite_id': invite_id,
            'event_type': 'invite_created',
            'target_phone': target_phone,
            'payload': {
                'project_name': project_name,
                'join_link': join_link,
                'inviter_name': inviter_name,
                'role_label': role_label,
                'invite_id': invite_id,
            },
            'status': 'queued',
            'channel': 'whatsapp',
            'attempts': 0,
            'max_attempts': 2,
            'provider_message_id': None,
            'last_error': None,
            'idempotency_key': idem_key,
            'created_by': created_by,
            'created_at': ts,
            'updated_at': ts,
            'next_retry_at': None,
        }
        await self.db.notification_jobs.insert_one(job)
        await self._audit_event(job_id, 'invite_enqueued', created_by, {
            'invite_id': invite_id, 'target_phone': target_phone,
        })
        logger.info(f"[INVITE-NOTIFY] Enqueued invite job {job_id} for invite {invite_id}")
        log_msg_queued(msg_type="invite", rid=job_id, phone_masked=mask_phone(target_phone))
        return {k: v for k, v in job.items() if k != '_id'}

    async def process_invite_job(self, job: dict) -> dict:
        job_id = job['id']
        ts = _now()
        attempt = job.get('attempts', 0) + 1
        payload = job.get('payload', {})
        target_phone = job.get('target_phone', '')
        phone_masked = mask_phone(target_phone) if target_phone else ''

        def _build_invite_text():
            lines = [
                f"📨 *הזמנה לפרויקט {payload.get('project_name', '')}*",
                "",
                f"👤 הוזמנת על ידי: {payload.get('inviter_name', '')}",
                f"🔑 תפקיד: {payload.get('role_label', '')}",
                "",
                f"🔗 לחץ כאן להצטרפות:",
                payload.get('join_link', ''),
            ]
            return "\n".join(lines)

        try:
            wa_result = None
            wa_error = None

            wa_invite_enabled = os.environ.get('WA_INVITE_ENABLED', 'false').lower() == 'true'
            invite_tpl = self.invite_template_name
            invite_tpl_lang = self.invite_template_lang

            if wa_invite_enabled and self.wa_client and self.wa_client.enabled:
                wa_timer = DeliveryTimer()
                try:
                    to_digits = target_phone.lstrip('+')
                    if invite_tpl:
                        body = {
                            "messaging_product": "whatsapp",
                            "to": to_digits,
                            "type": "template",
                            "template": {
                                "name": invite_tpl,
                                "language": {"code": invite_tpl_lang},
                                "components": [
                                    {
                                        "type": "body",
                                        "parameters": [
                                            {"type": "text", "text": payload.get('project_name', '')},
                                            {"type": "text", "text": payload.get('inviter_name', '')},
                                            {"type": "text", "text": payload.get('role_label', '')},
                                            {"type": "text", "text": payload.get('join_link', '')},
                                        ]
                                    }
                                ]
                            }
                        }
                        logger.info(f"[INVITE-NOTIFY] Using template={invite_tpl} lang={invite_tpl_lang}")
                    else:
                        text = _build_invite_text()
                        body = {
                            "messaging_product": "whatsapp",
                            "to": to_digits,
                            "type": "text",
                            "text": {"body": text}
                        }

                    headers = {
                        "Authorization": f"Bearer {self.wa_client.access_token}",
                        "Content-Type": "application/json",
                    }
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.post(self.wa_client.api_url, json=body, headers=headers)
                    wa_ms = wa_timer.elapsed_ms()

                    if resp.status_code in (200, 201):
                        data = resp.json()
                        mid = data.get("messages", [{}])[0].get("id", "")
                        await self.db.notification_jobs.update_one(
                            {'id': job_id},
                            {'$set': {
                                'status': 'accepted', 'channel': 'whatsapp',
                                'attempts': attempt, 'provider_message_id': mid,
                                'last_error': None, 'updated_at': ts,
                            }}
                        )
                        await self.db.whatsapp_events.insert_one({
                            'id': str(uuid.uuid4()), 'job_id': job_id,
                            'invite_id': payload.get('invite_id', ''),
                            'provider_message_id': mid,
                            'to_phone': target_phone, 'status': 'accepted',
                            'created_at': ts,
                        })
                        await self._audit_event(job_id, 'invite_accepted_wa', job.get('created_by', ''), {
                            'provider_message_id': mid, 'channel': 'whatsapp',
                            'invite_id': payload.get('invite_id', ''),
                        })
                        log_msg_delivery(msg_type="invite", rid=job_id, channel="whatsapp", result="accepted",
                                         external_ms=wa_ms, provider_status=mid[:20],
                                         phone_masked=phone_masked)
                        return {'status': 'accepted', 'job_id': job_id, 'channel': 'whatsapp',
                                'provider_message_id': mid, 'reason': 'whatsapp_accepted'}
                    else:
                        wa_error = resp.text[:500]
                        log_msg_delivery(msg_type="invite", rid=job_id, channel="whatsapp", result="failed",
                                         external_ms=wa_ms, error_code=str(resp.status_code),
                                         phone_masked=phone_masked)
                except Exception as e:
                    wa_error = str(e)[:500]
                    log_msg_delivery(msg_type="invite", rid=job_id, channel="whatsapp", result="failed",
                                     error_code=wa_error[:80], phone_masked=phone_masked)
            else:
                wa_error = 'wa_invite_disabled' if not wa_invite_enabled else 'whatsapp_disabled'
                log_msg_delivery(msg_type="invite", rid=job_id, channel="whatsapp", result="skipped",
                                 error_code=wa_error, phone_masked=phone_masked)
                logger.info(f"[INVITE-NOTIFY] WA skipped (WA_INVITE_ENABLED={wa_invite_enabled}) -> sending SMS directly")

            if self.sms_client and self.sms_client.enabled:
                text = _build_invite_text()
                sms_timer = DeliveryTimer()
                try:
                    sms_result = await self.sms_client.send_sms(target_phone, text, context=f'invite:{job_id}')
                    sms_ms = sms_timer.elapsed_ms()
                    if sms_result.get('status') == 'sent':
                        sms_sid = sms_result.get('provider_message_id', '')
                        await self.db.notification_jobs.update_one(
                            {'id': job_id},
                            {'$set': {
                                'status': 'sent', 'channel': 'sms',
                                'attempts': attempt, 'provider_message_id': sms_sid,
                                'last_error': f'wa_failed:{wa_error}', 'updated_at': ts,
                            }}
                        )
                        await self._audit_event(job_id, 'invite_sent_sms_fallback', job.get('created_by', ''), {
                            'twilio_sid': sms_sid, 'wa_error': wa_error,
                            'invite_id': payload.get('invite_id', ''),
                        })
                        log_msg_delivery(msg_type="invite", rid=job_id, channel="sms", result="sent",
                                         external_ms=sms_ms, provider_status=sms_sid[:20],
                                         phone_masked=phone_masked, fallback_from="whatsapp")
                        wa_skipped = wa_error in ('wa_invite_disabled', 'whatsapp_disabled')
                        return {'status': 'sent', 'job_id': job_id, 'channel': 'sms',
                                'provider_message_id': sms_sid, 'reason': f'wa_failed:{wa_error}',
                                'wa_skipped': wa_skipped}
                    else:
                        log_msg_delivery(msg_type="invite", rid=job_id, channel="sms", result="failed",
                                         external_ms=sms_ms, error_code=sms_result.get('error', '')[:80],
                                         phone_masked=phone_masked, fallback_from="whatsapp")
                except Exception as sms_e:
                    log_msg_delivery(msg_type="invite", rid=job_id, channel="sms", result="failed",
                                     error_code=str(sms_e)[:80], phone_masked=phone_masked,
                                     fallback_from="whatsapp")
            else:
                log_msg_delivery(msg_type="invite", rid=job_id, channel="sms", result="failed",
                                 error_code="sms_not_configured", phone_masked=phone_masked,
                                 fallback_from="whatsapp")

            await self.db.notification_jobs.update_one(
                {'id': job_id},
                {'$set': {
                    'status': 'failed', 'attempts': attempt,
                    'last_error': wa_error or 'all_channels_failed', 'updated_at': ts,
                }}
            )
            await self._audit_event(job_id, 'invite_send_failed', job.get('created_by', ''), {
                'wa_error': wa_error, 'invite_id': payload.get('invite_id', ''),
            })
            return {'status': 'failed', 'job_id': job_id, 'channel': 'none',
                    'reason': wa_error or 'all_channels_failed'}

        except Exception as e:
            error_msg = str(e)[:500]
            logger.error(f"[INVITE-NOTIFY] Unexpected error job={job_id}: {error_msg}")
            log_msg_delivery(msg_type="invite", rid=job_id, channel="none", result="failed",
                             error_code=error_msg[:80], phone_masked=phone_masked)
            await self.db.notification_jobs.update_one(
                {'id': job_id},
                {'$set': {'status': 'failed', 'attempts': attempt,
                          'last_error': error_msg, 'updated_at': ts}}
            )
            return {'status': 'failed', 'job_id': job_id, 'channel': 'none', 'reason': error_msg}

    async def process_webhook(self, provider_message_id: str, new_status: str) -> Optional[dict]:
        valid_statuses = ('sent', 'delivered', 'read', 'failed', 'accepted')
        if new_status not in valid_statuses:
            logger.warning(f"[WEBHOOK] Invalid status: {new_status}")
            return None

        job = await self.db.notification_jobs.find_one(
            {'provider_message_id': provider_message_id}, {'_id': 0}
        )
        if not job:
            logger.warning(f"[WEBHOOK] No job found for provider_message_id={provider_message_id}")
            return None

        ts = _now()
        await self.db.notification_jobs.update_one(
            {'id': job['id']},
            {'$set': {'status': new_status, 'updated_at': ts}}
        )
        await self._audit_event(job['id'], f'webhook_{new_status}', 'system',
                                {'provider_message_id': provider_message_id})
        logger.info(f"[WEBHOOK] Job {job['id']} updated to {new_status}")
        return {'job_id': job['id'], 'status': new_status}

    async def retry_job(self, job_id: str, actor_id: str) -> Optional[dict]:
        job = await self.db.notification_jobs.find_one({'id': job_id}, {'_id': 0})
        if not job:
            return None
        if job['status'] not in ('failed',):
            return {'error': 'Only failed jobs can be retried'}

        ts = _now()
        await self.db.notification_jobs.update_one(
            {'id': job_id},
            {'$set': {
                'status': 'queued',
                'attempts': 0,
                'last_error': None,
                'next_retry_at': None,
                'updated_at': ts,
            }}
        )
        await self._audit_event(job_id, 'retry_requested', actor_id, {})

        job['status'] = 'queued'
        job['attempts'] = 0
        result = await self.process_job(job)
        return result

    async def _audit_event(self, entity_id: str, action: str, actor_id: str, payload: dict):
        await self.db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'notification',
            'entity_id': entity_id,
            'action': action,
            'actor_id': actor_id,
            'payload': payload,
            'created_at': _now(),
        })

    async def run_worker_cycle(self):
        now = _now()
        query = {
            'status': 'queued',
            '$or': [
                {'next_retry_at': None},
                {'next_retry_at': {'$lte': now}},
            ]
        }
        jobs = await self.db.notification_jobs.find(query, {'_id': 0}).sort('created_at', 1).to_list(50)
        results = []
        for job in jobs:
            if job.get('event_type') == 'invite_created':
                result = await self.process_invite_job(job)
            else:
                result = await self.process_job(job)
            results.append(result)
        return results
