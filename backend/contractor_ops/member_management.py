from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
import uuid
import logging

from contractor_ops.router import get_current_user, _get_project_membership, _is_super_admin, get_db
from contractor_ops.billing import BILLING_V1_ENABLED, VALID_ORG_ROLES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

PM_ROLES = ('project_manager',)
VALID_PROJECT_ROLES = {'project_manager', 'management_team', 'work_manager', 'contractor', 'viewer'}

ROLE_CONFLICT_MSG = 'לא ניתן לשלב תפקיד קבלן עם תפקיד ניהולי בארגון'
MANAGEMENT_ORG_ROLES = {'owner', 'org_admin', 'billing_admin'}


async def _resolve_org_for_project(db, project_id: str):
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project or not project.get('org_id'):
        return None, None
    org = await db.organizations.find_one(
        {'id': project['org_id']},
        {'_id': 0, 'id': 1, 'owner_user_id': 1}
    )
    if not org:
        return None, None
    return org['id'], org.get('owner_user_id')


async def _audit_role_conflict(db, *, actor_id, target_user_id, org_id,
                                attempted_role, current_roles, reason, request=None):
    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'role_conflict_blocked',
        'actor_id': actor_id or 'system',
        'target_user_id': target_user_id,
        'org_id': org_id,
        'attempted_role': attempted_role,
        'current_roles': current_roles,
        'reason': reason,
        'created_at': datetime.now(timezone.utc).isoformat(),
    })


def _raise_role_conflict():
    raise HTTPException(
        status_code=409,
        detail={'message': ROLE_CONFLICT_MSG, 'code': 'ROLE_CONFLICT'},
    )


async def check_role_conflict(db, user_id: str, project_id: str, new_role: str, *,
                               actor_id: str, attempted_action: str, request=None):
    if new_role != 'contractor':
        return
    org_id, owner_user_id = await _resolve_org_for_project(db, project_id)
    if not org_id:
        return

    if user_id == owner_user_id:
        await _audit_role_conflict(
            db, actor_id=actor_id, target_user_id=user_id, org_id=org_id,
            attempted_role='contractor', current_roles=['owner'],
            reason='contractor_conflicts_with_org_management_role', request=request,
        )
        logger.warning(f"[ROLE-CONFLICT] {attempted_action} user={user_id[:8]} org={org_id[:8]} blocked=owner_as_contractor")
        _raise_role_conflict()

    org_mem = await db.organization_memberships.find_one(
        {'org_id': org_id, 'user_id': user_id}, {'_id': 0, 'role': 1}
    )
    if org_mem and org_mem.get('role') in MANAGEMENT_ORG_ROLES:
        await _audit_role_conflict(
            db, actor_id=actor_id, target_user_id=user_id, org_id=org_id,
            attempted_role='contractor', current_roles=[org_mem['role']],
            reason='contractor_conflicts_with_org_management_role', request=request,
        )
        logger.warning(f"[ROLE-CONFLICT] {attempted_action} user={user_id[:8]} org={org_id[:8]} blocked={org_mem['role']}_as_contractor")
        _raise_role_conflict()


async def has_role_conflict(db, user_id: str, project_id: str, new_role: str) -> bool:
    if new_role != 'contractor':
        return False
    org_id, owner_user_id = await _resolve_org_for_project(db, project_id)
    if not org_id:
        return False
    if user_id == owner_user_id:
        return True
    org_mem = await db.organization_memberships.find_one(
        {'org_id': org_id, 'user_id': user_id}, {'_id': 0, 'role': 1}
    )
    return bool(org_mem and org_mem.get('role') in MANAGEMENT_ORG_ROLES)


async def check_role_conflict_for_ownership(db, user_id: str, org_id: str, *,
                                             actor_id: str, request=None):
    org_project_ids = await db.projects.distinct('id', {'org_id': org_id})
    if not org_project_ids:
        return
    contractor_membership = await db.project_memberships.find_one({
        'user_id': user_id,
        'project_id': {'$in': org_project_ids},
        'role': 'contractor',
    })
    if not contractor_membership:
        return
    await _audit_role_conflict(
        db, actor_id=actor_id, target_user_id=user_id, org_id=org_id,
        attempted_role='owner', current_roles=['contractor'],
        reason='org_management_role_conflicts_with_contractor', request=request,
    )
    logger.warning(f"[ROLE-CONFLICT] ownership_transfer user={user_id[:8]} org={org_id[:8]} blocked=contractor_as_owner")
    _raise_role_conflict()


async def check_role_conflict_for_org_role(db, user_id: str, org_id: str, new_org_role: str, *,
                                            actor_id: str, request=None):
    if new_org_role not in ('org_admin', 'billing_admin'):
        return
    org_project_ids = await db.projects.distinct('id', {'org_id': org_id})
    if not org_project_ids:
        return
    contractor_membership = await db.project_memberships.find_one({
        'user_id': user_id,
        'project_id': {'$in': org_project_ids},
        'role': 'contractor',
    })
    if not contractor_membership:
        return
    await _audit_role_conflict(
        db, actor_id=actor_id, target_user_id=user_id, org_id=org_id,
        attempted_role=new_org_role, current_roles=['contractor'],
        reason='org_management_role_conflicts_with_contractor', request=request,
    )
    logger.warning(f"[ROLE-CONFLICT] org_role_change user={user_id[:8]} org={org_id[:8]} blocked=contractor_as_{new_org_role}")
    _raise_role_conflict()


async def _require_pm_or_owner(user: dict, project_id: str):
    if _is_super_admin(user):
        return 'project_manager'
    db = get_db()
    membership = await _get_project_membership(user, project_id)
    role = membership.get('role', 'none')
    if role in PM_ROLES:
        return role
    org_owner_id, _ = await _get_org_owner_id(db, project_id)
    if org_owner_id and org_owner_id == user['id']:
        return 'org_owner'
    raise HTTPException(status_code=403, detail='רק מנהל פרויקט או בעלים של הארגון יכולים לבצע פעולה זו')


async def _get_org_owner_id(db, project_id: str):
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project or not project.get('org_id'):
        return None, None
    org = await db.organizations.find_one({'id': project['org_id']}, {'_id': 0, 'owner_user_id': 1, 'id': 1})
    if not org:
        return None, None
    return org.get('owner_user_id'), org['id']


@router.put("/projects/{project_id}/members/{target_user_id}/role")
async def change_member_role(project_id: str, target_user_id: str, request: Request,
                             user: dict = Depends(get_current_user)):
    db = get_db()
    await _require_pm_or_owner(user, project_id)

    body = await request.json()
    new_role = body.get('new_role', '').strip()
    if not new_role or new_role not in VALID_PROJECT_ROLES:
        raise HTTPException(status_code=400, detail='תפקיד לא תקין')

    if target_user_id == user['id']:
        pm_count = await db.project_memberships.count_documents({
            'project_id': project_id, 'role': 'project_manager'
        })
        if pm_count <= 1:
            raise HTTPException(status_code=409, detail='לא ניתן לשנות תפקיד — חייב להיות לפחות מנהל פרויקט אחד')

    org_owner_id, _ = await _get_org_owner_id(db, project_id)
    if org_owner_id and target_user_id == org_owner_id:
        raise HTTPException(status_code=403, detail='לא ניתן לשנות תפקיד לבעלים של הארגון — יש להשתמש בהעברת בעלות')

    membership = await db.project_memberships.find_one({
        'user_id': target_user_id, 'project_id': project_id
    })
    if not membership:
        raise HTTPException(status_code=404, detail='חבר צוות לא נמצא בפרויקט')

    old_role = membership.get('role', '')
    if old_role == new_role:
        raise HTTPException(status_code=400, detail='התפקיד החדש זהה לנוכחי')

    if old_role == 'project_manager':
        pm_count = await db.project_memberships.count_documents({
            'project_id': project_id, 'role': 'project_manager'
        })
        if pm_count <= 1:
            raise HTTPException(status_code=409, detail='חייב להיות לפחות מנהל פרויקט אחד בפרויקט')

    await check_role_conflict(db, target_user_id, project_id, new_role,
                              actor_id=user['id'], attempted_action='change_member_role', request=request)

    update_fields = {'role': new_role}
    if new_role != 'contractor':
        update_fields['contractor_trade_key'] = None
    if new_role != 'management_team':
        update_fields['sub_role'] = None

    await db.project_memberships.update_one(
        {'user_id': target_user_id, 'project_id': project_id},
        {'$set': update_fields}
    )

    target = await db.users.find_one({'id': target_user_id}, {'_id': 0, 'name': 1})
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'name': 1})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'role_changed',
        'actor_id': user['id'],
        'actor_name': user.get('name', ''),
        'target_user_id': target_user_id,
        'target_user_name': target.get('name', '') if target else '',
        'project_id': project_id,
        'project_name': project.get('name', '') if project else '',
        'payload': {'old_role': old_role, 'new_role': new_role},
        'created_at': datetime.now(timezone.utc).isoformat(),
    })

    logger.info(f"[MEMBER] role_changed project={project_id[:8]} target={target_user_id[:8]} {old_role}->{new_role} by={user['id'][:8]}")
    return {'success': True, 'old_role': old_role, 'new_role': new_role}


@router.delete("/projects/{project_id}/members/{target_user_id}")
async def remove_member_from_project(project_id: str, target_user_id: str,
                                     user: dict = Depends(get_current_user)):
    db = get_db()
    await _require_pm_or_owner(user, project_id)

    org_owner_id, _ = await _get_org_owner_id(db, project_id)
    if org_owner_id and target_user_id == org_owner_id:
        raise HTTPException(status_code=403, detail='לא ניתן להסיר את בעלי הארגון מהפרויקט')

    if target_user_id == user['id']:
        pm_count = await db.project_memberships.count_documents({
            'project_id': project_id, 'role': 'project_manager'
        })
        if pm_count <= 1:
            raise HTTPException(status_code=409, detail='לא ניתן להסיר — חייב להיות לפחות מנהל פרויקט אחד')

    membership = await db.project_memberships.find_one({
        'user_id': target_user_id, 'project_id': project_id
    })
    if not membership:
        raise HTTPException(status_code=404, detail='חבר צוות לא נמצא בפרויקט')

    old_role = membership.get('role', '')

    await db.project_memberships.delete_one({
        'user_id': target_user_id, 'project_id': project_id
    })

    target = await db.users.find_one({'id': target_user_id}, {'_id': 0, 'name': 1})
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'name': 1})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'member_removed_from_project',
        'actor_id': user['id'],
        'actor_name': user.get('name', ''),
        'target_user_id': target_user_id,
        'target_user_name': target.get('name', '') if target else '',
        'project_id': project_id,
        'project_name': project.get('name', '') if project else '',
        'payload': {'removed_role': old_role},
        'created_at': datetime.now(timezone.utc).isoformat(),
    })

    logger.info(f"[MEMBER] removed_from_project project={project_id[:8]} target={target_user_id[:8]} role={old_role} by={user['id'][:8]}")
    return {'success': True, 'removed_user_id': target_user_id}


@router.delete("/org/members/{target_user_id}")
async def remove_member_from_org(target_user_id: str, request: Request,
                                 user: dict = Depends(get_current_user)):
    db = get_db()

    actor_org_mem = await db.organization_memberships.find_one({
        'user_id': user['id']
    }, {'_id': 0})
    if not actor_org_mem:
        raise HTTPException(status_code=403, detail='אינך חבר בארגון')

    org_id = actor_org_mem['org_id']
    org = await db.organizations.find_one({'id': org_id}, {'_id': 0})
    if not org:
        raise HTTPException(status_code=404, detail='ארגון לא נמצא')

    is_owner = org.get('owner_user_id') == user['id']
    is_sa = _is_super_admin(user)
    if not is_owner and not is_sa:
        raise HTTPException(status_code=403, detail='רק בעלים של הארגון יכול להסיר חברים')

    if target_user_id == org.get('owner_user_id'):
        raise HTTPException(status_code=403, detail='לא ניתן להסיר את בעלי הארגון — יש להעביר בעלות קודם')

    target_org_mem = await db.organization_memberships.find_one({
        'user_id': target_user_id, 'org_id': org_id
    })
    if not target_org_mem:
        raise HTTPException(status_code=404, detail='המשתמש אינו חבר בארגון')

    org_projects = await db.projects.find({'org_id': org_id}, {'_id': 0, 'id': 1, 'name': 1}).to_list(1000)
    org_project_ids = [p['id'] for p in org_projects]

    removed_from_projects = []
    if org_project_ids:
        project_memberships = await db.project_memberships.find({
            'user_id': target_user_id,
            'project_id': {'$in': org_project_ids}
        }).to_list(1000)

        for pm in project_memberships:
            pid = pm['project_id']
            if pm.get('role') == 'project_manager':
                pm_count = await db.project_memberships.count_documents({
                    'project_id': pid, 'role': 'project_manager'
                })
                if pm_count <= 1:
                    proj_name = next((p['name'] for p in org_projects if p['id'] == pid), pid[:8])
                    raise HTTPException(
                        status_code=409,
                        detail=f'לא ניתן להסיר — המשתמש הוא מנהל הפרויקט היחיד ב-"{proj_name}"'
                    )

        result = await db.project_memberships.delete_many({
            'user_id': target_user_id,
            'project_id': {'$in': org_project_ids}
        })
        removed_from_projects = [pm['project_id'] for pm in project_memberships]
        logger.info(f"[MEMBER] cascade_remove_projects org={org_id[:8]} target={target_user_id[:8]} projects_removed={result.deleted_count}")

    await db.organization_memberships.delete_one({
        'user_id': target_user_id, 'org_id': org_id
    })

    target = await db.users.find_one({'id': target_user_id}, {'_id': 0, 'name': 1})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'member_removed_from_org',
        'actor_id': user['id'],
        'actor_name': user.get('name', ''),
        'target_user_id': target_user_id,
        'target_user_name': target.get('name', '') if target else '',
        'org_id': org_id,
        'org_name': org.get('name', ''),
        'payload': {
            'removed_from_projects': removed_from_projects,
            'projects_count': len(removed_from_projects),
        },
        'created_at': datetime.now(timezone.utc).isoformat(),
    })

    logger.info(f"[MEMBER] removed_from_org org={org_id[:8]} target={target_user_id[:8]} cascade_projects={len(removed_from_projects)} by={user['id'][:8]}")
    return {
        'success': True,
        'removed_user_id': target_user_id,
        'removed_from_projects': len(removed_from_projects),
    }


@router.get("/orgs/{org_id}/members")
async def list_org_members(org_id: str, user: dict = Depends(get_current_user)):
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')

    db = get_db()
    is_sa = _is_super_admin(user)

    org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'owner_user_id': 1, 'name': 1})
    if not org:
        raise HTTPException(status_code=404, detail='ארגון לא נמצא')

    owner_user_id = org.get('owner_user_id', '')
    is_owner = owner_user_id == user['id']

    if not is_sa and not is_owner:
        caller_mem = await db.organization_memberships.find_one(
            {'org_id': org_id, 'user_id': user['id']}, {'_id': 0, 'role': 1}
        )
        caller_role = caller_mem.get('role', 'member') if caller_mem else None
        if caller_role not in ('org_admin', 'billing_admin'):
            raise HTTPException(status_code=403, detail='אין הרשאה לצפות ברשימת חברי הארגון')

    memberships = await db.organization_memberships.find(
        {'org_id': org_id}, {'_id': 0}
    ).to_list(500)

    members = []
    for mem in memberships:
        u = await db.users.find_one({'id': mem['user_id']}, {'_id': 0, 'id': 1, 'name': 1, 'phone_e164': 1})
        if u:
            members.append({
                'user_id': u['id'],
                'name': u.get('name', ''),
                'phone': u.get('phone_e164', ''),
                'role': mem.get('role', 'member'),
                'is_owner': u['id'] == owner_user_id,
            })

    members.sort(key=lambda m: (not m['is_owner'], m.get('role', 'member') != 'org_admin', m.get('role', 'member') != 'billing_admin', m.get('name', '')))

    return {'org_id': org_id, 'org_name': org.get('name', ''), 'owner_user_id': owner_user_id, 'members': members}


@router.put("/orgs/{org_id}/members/{target_user_id}/org-role")
async def change_org_member_role(org_id: str, target_user_id: str, request: Request,
                                  user: dict = Depends(get_current_user)):
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')

    db = get_db()
    is_sa = _is_super_admin(user)

    if not is_sa:
        org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'owner_user_id': 1})
        if not org or org.get('owner_user_id') != user['id']:
            raise HTTPException(status_code=403, detail='רק בעלים של הארגון או מנהל מערכת יכולים לשנות תפקיד ארגוני')

    body = await request.json()
    new_role = body.get('role', '').strip()
    if new_role not in VALID_ORG_ROLES:
        raise HTTPException(status_code=400, detail=f'תפקיד לא חוקי: {new_role}')

    mem = await db.organization_memberships.find_one(
        {'org_id': org_id, 'user_id': target_user_id}, {'_id': 0}
    )
    if not mem:
        raise HTTPException(status_code=404, detail='משתמש לא נמצא בארגון')

    old_role = mem.get('role', 'member')
    if old_role == new_role:
        return {'success': True, 'message': 'התפקיד לא השתנה', 'old_role': old_role, 'new_role': new_role}

    await check_role_conflict_for_org_role(db, target_user_id, org_id, new_role,
                                            actor_id=user['id'], request=request)

    await db.organization_memberships.update_one(
        {'org_id': org_id, 'user_id': target_user_id},
        {'$set': {'role': new_role}}
    )

    ts = datetime.now(timezone.utc).isoformat()
    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'organization',
        'entity_id': org_id,
        'action': 'org_role_changed',
        'actor_id': user['id'],
        'payload': {
            'target_user_id': target_user_id,
            'old_role': old_role,
            'new_role': new_role,
            'org_id': org_id,
        },
        'created_at': ts,
    })

    target = await db.users.find_one({'id': target_user_id}, {'_id': 0, 'name': 1})
    logger.info(f"[MEMBER] org_role_changed org={org_id[:8]} target={target_user_id[:8]} {old_role}->{new_role} by={user['id'][:8]}")

    return {
        'success': True,
        'target_user_id': target_user_id,
        'target_name': target.get('name', '') if target else '',
        'old_role': old_role,
        'new_role': new_role,
    }
