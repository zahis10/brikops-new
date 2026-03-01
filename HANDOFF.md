# M2 Handoff — Invite Hierarchy System

## Date: 2026-02-17 | Git SHA: 469fa2e | Tag: m2-invite-ready

---

## 1. Final Endpoints List (56 total)

### Auth & Users (4)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register user (email+password or phone) |
| POST | `/api/auth/login` | Login (returns JWT) |
| GET | `/api/auth/me` | Current user profile |
| GET | `/api/users` | List users (admin only) |

### Projects (8)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects` | Create project |
| GET | `/api/projects` | List projects |
| GET | `/api/projects/{id}` | Get project details |
| GET | `/api/projects/{id}/dashboard` | Project dashboard |
| POST | `/api/projects/{id}/assign-pm` | Assign PM to project |
| GET | `/api/projects/{id}/available-pms` | List available PMs |
| GET | `/api/projects/{id}/stats` | Project statistics |
| GET | `/api/projects/{id}/hierarchy` | Full project hierarchy |

### Buildings & Floors & Units (9)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects/{id}/buildings` | Create building |
| GET | `/api/projects/{id}/buildings` | List buildings |
| POST | `/api/buildings/{id}/floors` | Create floor |
| GET | `/api/buildings/{id}/floors` | List floors |
| POST | `/api/floors/{id}/units` | Create unit |
| GET | `/api/floors/{id}/units` | List units |
| POST | `/api/floors/bulk` | Bulk create floors |
| POST | `/api/units/bulk` | Bulk create units |
| GET | `/api/units/{id}` | Get unit details |

### Tasks (11)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tasks` | Create task |
| GET | `/api/tasks` | List tasks |
| GET | `/api/tasks/{id}` | Get task details |
| PATCH | `/api/tasks/{id}` | Update task |
| PATCH | `/api/tasks/{id}/assign` | Assign task |
| POST | `/api/tasks/{id}/status` | Change task status |
| POST | `/api/tasks/{id}/reopen` | Reopen closed task |
| POST | `/api/tasks/{id}/contractor-proof` | Submit contractor proof |
| POST | `/api/tasks/{id}/manager-decision` | Manager approve/reject |
| POST | `/api/tasks/{id}/updates` | Add task update/comment |
| GET | `/api/tasks/{id}/updates` | List task updates |

### Files & Feed (2)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/tasks/{id}/attachments` | Upload attachment |
| GET | `/api/updates/feed` | Real-time updates feed |

### Companies (6)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/companies` | Create company (global) |
| GET | `/api/companies` | List companies (global) |
| POST | `/api/projects/{id}/companies` | Add company to project |
| GET | `/api/projects/{id}/companies` | List project companies |
| PUT | `/api/projects/{id}/companies/{cid}` | Update project company |
| DELETE | `/api/projects/{id}/companies/{cid}` | Remove project company |

### Invites (4) — M2 NEW
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects/{id}/invites` | Create invite |
| GET | `/api/projects/{id}/invites` | List project invites |
| POST | `/api/projects/{id}/invites/{iid}/resend` | Resend invite |
| POST | `/api/projects/{id}/invites/{iid}/cancel` | Cancel invite |

### Memberships (2)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects/{id}/memberships` | List project members |
| GET | `/api/my-memberships` | List my memberships |

### Notifications (2)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/notifications` | List notifications |
| GET | `/api/notifications/stats` | Notification statistics |

### Excel (2)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects/{id}/excel-template` | Download Excel template |
| POST | `/api/projects/{id}/excel-import` | Import from Excel |

### Hierarchy Ops (3)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects/{id}/migrate-sort-index` | Migrate sort indices |
| POST | `/api/buildings/{id}/resequence` | Resequence building |
| POST | `/api/projects/{id}/insert-floor` | Insert floor at position |

### Observability (3)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/ready` | Readiness check |
| GET | `/api/debug/version` | Version info + feature flags |

---

## 2. Active Feature Flags

| Flag | Current Value | Description |
|------|--------------|-------------|
| `APP_MODE` | `dev` | dev/prod — controls debug endpoints |
| `WHATSAPP_ENABLED` | `false` | WhatsApp Cloud API — dry-run until Meta credentials |
| `OTP_PROVIDER` | `mock` | mock/sms/whatsapp — OTP delivery method |

### Environment Variables (backend/.env)
```
APP_ID=contractor-ops-001
APP_MODE=dev
MONGO_URL=mongodb://localhost:27017
DB_NAME=contractor_ops
CORS_ORIGINS=*
JWT_SECRET=<from Replit Secrets>
JWT_SECRET_VERSION=v1
WHATSAPP_ENABLED=false
```

---

## 3. Rollback Steps

### Code Rollback
```bash
git checkout m2-invite-ready
```

### Database Rollback
Replit provides automatic checkpoints. Use the Replit UI to rollback to any checkpoint from the M2 period.

### Manual DB Rollback (if needed)
```bash
cd backend && python scripts/backup_restore.py --export --output m2-backup.json
cd backend && python scripts/backup_restore.py --import --input m2-backup.json
```

### Collections Added in M2
- `invites` — invite records
- `audit_events` — audit trail for invites
- `project_memberships` — project-level role assignments (existed, extended)

### Rollback Checklist
1. Revert code to tag `m2-invite-ready`
2. Restart MongoDB + backend
3. Verify `/api/health` returns 200
4. Verify `/api/ready` returns 200
5. Run seed if clean DB: `cd backend && python seed.py`

---

## 4. Test Coverage Summary (M2 Final)

| Suite | Count |
|-------|-------|
| E2E | 44 |
| Onboarding | 54 |
| Notifications | 65 |
| Workflow M1 | 14 |
| Audit Immutability | 18 |
| Cross-Project RBAC | 9 |
| Dry-Run Flow | 20 |
| Invite System | 39 |
| E2E Invite Proof | 54 |
| **Total** | **317** |

---

## 5. Git Commands for M2 Closure

```bash
git tag m2-invite-ready 469fa2e
git branch m3-dev HEAD
```
