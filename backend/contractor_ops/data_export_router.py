import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from contractor_ops.router import get_db, get_current_user, _get_project_role

from services.object_storage import generate_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.post("/projects/{project_id}/export")
async def start_project_export(
    project_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    db = get_db()

    role = await _get_project_role(user, project_id)
    if role != 'project_manager' and user.get('platform_role') != 'super_admin':
        raise HTTPException(status_code=403, detail='אין הרשאה לייצוא נתונים')

    project = await db.projects.find_one(
        {'id': project_id, 'archived': {'$ne': True}}, {'_id': 0, 'id': 1}
    )
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = await db.export_jobs.find_one({
        'project_id': project_id,
        'status': 'done',
        'completed_at': {'$gte': one_hour_ago},
    })
    if recent:
        raise HTTPException(status_code=429, detail='ניתן לייצא פעם בשעה')

    import uuid
    from pymongo.errors import DuplicateKeyError
    job_id = str(uuid.uuid4())
    job = {
        'id': job_id,
        'project_id': project_id,
        'user_id': user['id'],
        'status': 'pending',
        'progress': 0,
        'progress_label': '',
        'format': 'full_zip',
        'file_url': None,
        'file_size': None,
        'error': None,
        'stats': {},
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc),
        'completed_at': None,
        '_active_lock': True,
    }

    thirty_min_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
    stuck = await db.export_jobs.find_one({
        'project_id': project_id,
        '_active_lock': True,
        'status': {'$in': ['pending', 'processing']},
        '$or': [
            {'updated_at': {'$lt': thirty_min_ago}},
            {'updated_at': {'$exists': False}, 'created_at': {'$lt': thirty_min_ago}},
        ],
    })
    if stuck:
        logger.warning(f"[DATA_EXPORT] Cleaning stuck job {stuck['id']} "
                       f"(last update {stuck.get('updated_at', stuck.get('created_at'))})")
        await db.export_jobs.update_one(
            {'id': stuck['id']},
            {'$set': {'status': 'error', 'error': 'ייצוא נתקע ובוטל אוטומטית',
                      'updated_at': datetime.now(timezone.utc)},
             '$unset': {'_active_lock': ''}}
        )

    try:
        await db.export_jobs.insert_one(job)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail='ייצוא כבר בתהליך')

    from services.data_export_service import run_export_job
    background_tasks.add_task(run_export_job, job['id'])

    return {'job_id': job['id'], 'status': 'pending'}


@router.get("/projects/{project_id}/export/latest")
async def get_latest_export(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    role = await _get_project_role(user, project_id)
    if role != 'project_manager' and user.get('platform_role') != 'super_admin':
        raise HTTPException(status_code=403, detail='אין הרשאה')

    job = await db.export_jobs.find_one(
        {'project_id': project_id, 'status': 'done'},
        {'_id': 0},
        sort=[('completed_at', -1)],
    )
    if not job:
        return {'exists': False}

    return {
        'exists': True,
        'job_id': job['id'],
        'completed_at': job.get('completed_at'),
        'file_size': job.get('file_size'),
        'stats': job.get('stats', {}),
        'download_url': generate_url(job['file_url']),
    }


@router.get("/projects/{project_id}/export/{job_id}")
async def get_export_status(
    project_id: str,
    job_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    role = await _get_project_role(user, project_id)
    if role != 'project_manager' and user.get('platform_role') != 'super_admin':
        raise HTTPException(status_code=403, detail='אין הרשאה')

    job = await db.export_jobs.find_one(
        {'id': job_id, 'project_id': project_id}, {'_id': 0}
    )
    if not job:
        raise HTTPException(status_code=404, detail='Export job not found')

    result = {
        'job_id': job['id'],
        'status': job['status'],
        'progress': job.get('progress', 0),
        'progress_label': job.get('progress_label', ''),
        'stats': job.get('stats', {}),
    }
    if job['status'] == 'done':
        result['download_url'] = generate_url(job['file_url'])
        result['file_size'] = job.get('file_size')
        result['completed_at'] = job.get('completed_at')
    elif job['status'] == 'error':
        result['error'] = job.get('error', 'שגיאה לא צפויה')

    return result
