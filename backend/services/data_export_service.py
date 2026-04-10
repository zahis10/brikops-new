import asyncio
import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_MAX_PHOTOS = 10000
PHOTO_BATCH_SIZE = 10


def _write_json_to_zip(tmp_path, data, stats, project_name):
    with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('project.json',
                    json.dumps(data['project'], ensure_ascii=False, indent=2, default=str))
        zf.writestr('defects.json',
                    json.dumps(data['defects'], ensure_ascii=False, indent=2, default=str))
        zf.writestr('handover_protocols.json',
                    json.dumps(data['protocols'], ensure_ascii=False, indent=2, default=str))
        zf.writestr('qc_runs.json',
                    json.dumps(data['qc_runs'], ensure_ascii=False, indent=2, default=str))
        zf.writestr('team.json',
                    json.dumps(data['team'], ensure_ascii=False, indent=2, default=str))
        zf.writestr('companies.json',
                    json.dumps(data['companies'], ensure_ascii=False, indent=2, default=str))
        zf.writestr('README.txt', _readme(stats, project_name))


def _download_photo_batch(batch):
    results = []
    for filename, stored_ref in batch:
        photo_bytes = _download_photo(stored_ref)
        results.append((filename, photo_bytes))
    return results


def _append_photos_to_zip(tmp_path, batch_results):
    with zipfile.ZipFile(tmp_path, 'a', zipfile.ZIP_DEFLATED) as zf:
        for filename, photo_bytes in batch_results:
            if photo_bytes:
                zf.writestr(f'photos/{filename}', photo_bytes)


def _upload_zip_sync(tmp_path, s3_key, zip_size):
    from services.object_storage import save_bytes, is_s3_mode, _get_s3, _S3_BUCKET
    if zip_size > 500 * 1024 * 1024 and is_s3_mode():
        logger.warning(f"[DATA_EXPORT] Large ZIP {zip_size / 1024 / 1024:.0f}MB — streaming upload")
        s3 = _get_s3()
        s3.upload_file(tmp_path, _S3_BUCKET, s3_key,
                       ExtraArgs={'ContentType': 'application/zip'})
        return f"s3://{s3_key}"
    else:
        with open(tmp_path, 'rb') as f:
            return save_bytes(f.read(), s3_key, 'application/zip')


async def run_export_job(job_id: str):
    from contractor_ops.router import get_db, _audit

    db = get_db()
    job = await db.export_jobs.find_one({'id': job_id})
    if not job:
        return

    project_id = job['project_id']
    tmp_path = None

    try:
        await _update_job(db, job_id, status='processing', progress=0,
                          progress_label='מתחיל ייצוא...')

        await _update_job(db, job_id, progress=5, progress_label='מייצא מבנה פרויקט...')
        project_data = await _export_project_structure(db, project_id)
        project_name = project_data.get('name', 'export')

        await _update_job(db, job_id, progress=15, progress_label='מייצא ליקויים...')
        defects = await _export_defects(db, project_id)

        await _update_job(db, job_id, progress=30, progress_label='מייצא פרוטוקולי מסירה...')
        protocols = await _export_handover_protocols(db, project_id)

        await _update_job(db, job_id, progress=42, progress_label='מייצא בקרת ביצוע...')
        qc_runs = await _export_qc_runs(db, project_id)

        await _update_job(db, job_id, progress=50, progress_label='מייצא צוות וחברות...')
        team = await _export_team(db, project_id)
        companies = await _export_companies(db, project_id)

        await _update_job(db, job_id, progress=55, progress_label='מזהה תמונות...')
        photo_refs = _collect_photo_refs(defects, protocols, qc_runs)

        max_photos = None if job.get('is_admin') else DEFAULT_MAX_PHOTOS
        photos_total = len(photo_refs)
        photo_count = photos_total if max_photos is None else min(photos_total, max_photos)

        stats = {
            'defects': len(defects),
            'handover_protocols': len(protocols),
            'qc_runs': len(qc_runs),
            'team_members': len(team),
            'companies': len(companies),
            'photos': photos_total,
            'photos_total': photos_total,
            'photos_to_export': photo_count,
        }

        photo_map = {}
        for filename, original_ref in photo_refs[:photo_count]:
            photo_map[original_ref] = f"photos/{filename}"

        _rewrite_photo_refs(defects, protocols, qc_runs, photo_map)

        await _update_job(db, job_id, progress=60,
                          progress_label=f'בונה ZIP ({photo_count} תמונות)...',
                          stats=stats)

        tmp_file = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
        tmp_path = tmp_file.name
        tmp_file.close()

        data = {
            'project': project_data, 'defects': defects,
            'protocols': protocols, 'qc_runs': qc_runs,
            'team': team, 'companies': companies,
        }

        await asyncio.to_thread(
            _write_json_to_zip, tmp_path, data, stats, project_name
        )

        downloaded = 0
        failed = 0

        for i in range(0, photo_count, PHOTO_BATCH_SIZE):
            batch = photo_refs[i:i + PHOTO_BATCH_SIZE]
            batch_results = await asyncio.to_thread(
                _download_photo_batch, batch
            )

            await asyncio.to_thread(
                _append_photos_to_zip, tmp_path, batch_results
            )

            for filename, photo_bytes in batch_results:
                if photo_bytes:
                    downloaded += 1
                else:
                    failed += 1

            pct = 60 + int(((i + len(batch)) / max(photo_count, 1)) * 30)
            await _update_job(db, job_id, progress=min(pct, 90),
                              progress_label=f'מוריד תמונות ({downloaded}/{photo_count})...')

        await _update_job(db, job_id, progress=95, progress_label='מעלה קובץ...')

        zip_size = os.path.getsize(tmp_path)
        safe_name = project_name.replace(' ', '_').replace('/', '_')
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        s3_key = f"exports/{project_id}/{today}_{safe_name}.zip"

        file_url = await asyncio.to_thread(
            _upload_zip_sync, tmp_path, s3_key, zip_size,
        )

        os.unlink(tmp_path)
        tmp_path = None

        stats['photos_downloaded'] = downloaded
        stats['photos_failed'] = failed
        stats['photos_skipped'] = photos_total - photo_count
        stats['file_size_mb'] = round(zip_size / (1024 * 1024), 1)

        await _update_job(db, job_id, status='done', progress=100,
                          progress_label='הייצוא הושלם',
                          file_url=file_url, file_size=zip_size,
                          completed_at=datetime.now(timezone.utc), stats=stats)

        await _audit('project', project_id, 'full_data_export', job['user_id'], {
            'job_id': job_id, 'stats': stats,
        })

        logger.info(f"[DATA_EXPORT] project={project_id} job={job_id} "
                     f"defects={stats['defects']} protocols={stats['handover_protocols']} "
                     f"qc={stats['qc_runs']} photos={downloaded}/{failed} "
                     f"size={stats['file_size_mb']}MB")

    except Exception as e:
        logger.error(f"[DATA_EXPORT:ERROR] job={job_id} error={e}", exc_info=True)
        await _update_job(db, job_id, status='error',
                          error=f'שגיאה בייצוא: {str(e)[:200]}')
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


async def _update_job(db, job_id, **fields):
    fields['updated_at'] = datetime.now(timezone.utc)
    update = {'$set': fields}
    if fields.get('status') in ('done', 'error'):
        update['$unset'] = {'_active_lock': ''}
    await db.export_jobs.update_one({'id': job_id}, update)


async def _export_project_structure(db, project_id):
    project = await db.projects.find_one(
        {'id': project_id},
        {'_id': 0, 'join_code': 0},
    )
    project['buildings'] = await db.buildings.find(
        {'project_id': project_id, 'archived': {'$ne': True}}, {'_id': 0}
    ).to_list(1000)
    project['floors'] = await db.floors.find(
        {'project_id': project_id, 'archived': {'$ne': True}}, {'_id': 0}
    ).to_list(10000)
    project['units'] = await db.units.find(
        {'project_id': project_id, 'archived': {'$ne': True}}, {'_id': 0}
    ).to_list(100000)
    return project


async def _export_defects(db, project_id):
    tasks = await db.tasks.find(
        {'project_id': project_id, 'archived': {'$ne': True}}, {'_id': 0}
    ).to_list(100000)

    task_ids = [t['id'] for t in tasks]
    updates_by_task = {}

    for i in range(0, len(task_ids), 500):
        batch = task_ids[i:i + 500]
        batch_updates = await db.task_updates.find(
            {'task_id': {'$in': batch}, 'deletedAt': {'$exists': False}}, {'_id': 0}
        ).to_list(500000)
        for u in batch_updates:
            updates_by_task.setdefault(u['task_id'], []).append(u)

    for t in tasks:
        t['updates'] = updates_by_task.get(t['id'], [])
    return tasks


async def _export_handover_protocols(db, project_id):
    protocols = await db.handover_protocols.find(
        {'project_id': project_id}, {'_id': 0}
    ).to_list(10000)

    for p in protocols:
        for tenant in (p.get('tenants') or []):
            if 'id_number' in tenant:
                tenant['id_number'] = '***'
    return protocols


async def _export_qc_runs(db, project_id):
    runs = await db.qc_runs.find(
        {'project_id': project_id}, {'_id': 0}
    ).to_list(10000)

    run_ids = [r['id'] for r in runs]
    items_by_run = {}

    for i in range(0, len(run_ids), 500):
        batch = run_ids[i:i + 500]
        batch_items = await db.qc_items.find(
            {'run_id': {'$in': batch}}, {'_id': 0}
        ).to_list(500000)
        for item in batch_items:
            items_by_run.setdefault(item['run_id'], []).append(item)

    for r in runs:
        r['items'] = items_by_run.get(r['id'], [])
    return runs


_TEAM_FIELDS = {'user_id', 'role', 'sub_role', 'project_id', 'joined_at', 'status'}

async def _export_team(db, project_id):
    memberships = await db.project_memberships.find(
        {'project_id': project_id}, {'_id': 0}
    ).to_list(1000)

    user_ids = [m['user_id'] for m in memberships if m.get('user_id')]
    users = {}
    if user_ids:
        user_docs = await db.users.find(
            {'id': {'$in': user_ids}},
            {'_id': 0, 'id': 1, 'name': 1},
        ).to_list(1000)
        users = {u['id']: u.get('name', '') for u in user_docs}

    result = []
    for m in memberships:
        safe = {k: m[k] for k in _TEAM_FIELDS if k in m}
        safe['user_name'] = users.get(m.get('user_id'), '')
        result.append(safe)
    return result


async def _export_companies(db, project_id):
    return await db.project_companies.find(
        {'project_id': project_id, 'deletedAt': {'$exists': False}}, {'_id': 0}
    ).to_list(1000)


def _collect_photo_refs(defects, protocols, qc_runs):
    refs = []
    seen = set()
    counter = [0]

    def _add(url, prefix):
        if not url or not isinstance(url, str) or url in seen:
            return
        seen.add(url)
        counter[0] += 1
        ext = os.path.splitext(url.split('?')[0])[1] or '.jpg'
        refs.append((f"{prefix}_{counter[0]:05d}{ext}", url))

    for task in defects:
        tag = str(task.get('display_number') or task.get('short_ref') or task['id'][:8])
        for url in (task.get('proof_urls') or []):
            _add(url, f"defect_{tag}")
        for upd in (task.get('updates') or []):
            if upd.get('update_type') == 'attachment':
                _add(upd.get('attachment_url'), f"defect_{tag}")

    for p in protocols:
        tag = str(p.get('display_number') or p['id'][:8])
        for sec in (p.get('sections') or []):
            for item in (sec.get('items') or []):
                for photo_url in (item.get('photos') or []):
                    _add(photo_url, f"handover_{tag}")
        meters = p.get('meters') or {}
        for mt in ('water', 'electricity'):
            m = meters.get(mt) or {}
            _add(m.get('photo_url'), f"handover_{tag}_meter")
        for tenant in (p.get('tenants') or []):
            _add(tenant.get('id_photo_url'), f"handover_{tag}_tenant")

    for run in qc_runs:
        tag = run['id'][:8]
        for item in (run.get('items') or []):
            for photo in (item.get('photos') or []):
                url = photo.get('url') if isinstance(photo, dict) else photo
                _add(url, f"qc_{tag}")

    return refs


def _download_photo(stored_ref):
    from services.object_storage import is_s3_mode, _get_s3, _S3_BUCKET, _LOCAL_UPLOADS_ROOT
    try:
        if stored_ref.startswith('s3://'):
            try:
                key = stored_ref[5:]
                resp = _get_s3().get_object(Bucket=_S3_BUCKET, Key=key)
                return resp['Body'].read()
            except Exception:
                pass
        elif stored_ref.startswith('/api/uploads/'):
            rel = stored_ref[len('/api/uploads/'):]
            if not rel or '..' in rel or rel.startswith('/'):
                logger.warning(f"[DATA_EXPORT] rejected suspicious path: {stored_ref[:80]}")
                return None
            base = _LOCAL_UPLOADS_ROOT.resolve()
            path = (base / rel).resolve()
            try:
                path.relative_to(base)
            except ValueError:
                logger.warning(f"[DATA_EXPORT] path traversal blocked: {stored_ref[:80]}")
                return None
            if path.exists():
                return path.read_bytes()
    except Exception as e:
        logger.warning(f"[DATA_EXPORT] photo download failed: {stored_ref[:80]} — {e}")
    return None


def _rewrite_photo_refs(defects, protocols, qc_runs, photo_map):
    def _rw(url):
        return photo_map.get(url, url) if url else url

    for task in defects:
        task['proof_urls'] = [_rw(u) for u in (task.get('proof_urls') or [])]
        for upd in (task.get('updates') or []):
            if upd.get('attachment_url'):
                upd['attachment_url'] = _rw(upd['attachment_url'])

    for p in protocols:
        for sec in (p.get('sections') or []):
            for item in (sec.get('items') or []):
                item['photos'] = [_rw(u) for u in (item.get('photos') or [])]
        meters = p.get('meters') or {}
        for mt in ('water', 'electricity'):
            m = meters.get(mt)
            if m and m.get('photo_url'):
                m['photo_url'] = _rw(m['photo_url'])
        for tenant in (p.get('tenants') or []):
            if tenant.get('id_photo_url'):
                tenant['id_photo_url'] = _rw(tenant['id_photo_url'])

    for run in qc_runs:
        for item in (run.get('items') or []):
            new_photos = []
            for photo in (item.get('photos') or []):
                if isinstance(photo, dict) and photo.get('url'):
                    photo['url'] = _rw(photo['url'])
                    new_photos.append(photo)
                elif isinstance(photo, str):
                    new_photos.append(_rw(photo))
                else:
                    new_photos.append(photo)
            item['photos'] = new_photos


def _readme(stats, project_name):
    return f"""BrikOps — ייצוא נתוני פרויקט
==============================
פרויקט: {project_name}
תאריך ייצוא: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

תכולה:
- project.json    — מבנה הפרויקט (בניינים, קומות, דירות)
- defects.json    — כל הליקויים כולל הערות, סטטוסים ותמונות
- handover_protocols.json — פרוטוקולי מסירה כולל ממצאים וחתימות
- qc_runs.json    — ריצות בקרת ביצוע כולל פריטי בדיקה
- team.json       — חברי צוות ותפקידים
- companies.json  — חברות וקבלנים
- photos/         — כל התמונות (ליקויים, מסירות, בקרת ביצוע)

סטטיסטיקה:
- ליקויים: {stats.get('defects', 0)}
- פרוטוקולי מסירה: {stats.get('handover_protocols', 0)}
- ריצות QC: {stats.get('qc_runs', 0)}
- חברי צוות: {stats.get('team_members', 0)}
- חברות: {stats.get('companies', 0)}
- תמונות: {stats.get('photos', 0)}

הערות:
- כל התאריכים ב-UTC בפורמט ISO 8601
- כל המזהים הם UUID
- נתיבי תמונות ב-JSON מפנים לתיקיית photos/
- מספרי ת.ז. של דיירים מוסתרים לפרטיות
- הקובץ נוצר על ידי BrikOps (https://brikops.com)
"""
