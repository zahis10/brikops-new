# Task #35a — Safety Phase 1 Part 3a — Patch: Score Formulas + PDF + Audit Payload

**Scope:** 2 files, ~90 lines changed. No new deps, no schema changes, no new endpoints.

**Why:** Part 3 (commit after #35) shipped the 4 advanced endpoints but drifted from the spec in 4 places. All 4 are MUST FIX before Part 4 frontend starts.

**4 fixes, in order of criticality:**

1. `_compute_safety_score` — 3 penalty formulas use flat weights instead of the spec's severity/type-weighted buckets.
2. `_compute_safety_score` — breakdown response shape doesn't match spec, Part 4 frontend will have nothing to render against.
3. `generate_safety_register` — missing "Management Team" section (regulatory gap for פנקס כללי).
4. `export_safety_filtered` — `$`-prefixed keys in audit payload cause runtime `InvalidDocument` on MongoDB insert when a date filter is present.

---

## Fix 1 — Score formulas (port spec weights)

**File:** `backend/contractor_ops/safety_router.py`

Replace the entire body of `_compute_safety_score` (currently ~100 lines starting at the comment `# Documents bucket`) with the spec-accurate version below. **Keep** the outer signature, the `now`/`today_iso`/`cutoff_90d` setup, and the `return {...}` envelope. Change: (a) add severity-weighted task aggregation, (b) add type-counted incident aggregation, (c) add required-training-per-worker training logic, (d) add `REQUIRED_TRAINING_TYPES` constant at module level.

### 1.1 Add module-level constant (once, near other score constants)

```python
# Safety score — required training types per worker (spec §Steps.1)
REQUIRED_TRAINING_TYPES = frozenset({"safety_induction", "height_work", "electrical"})
```

### 1.2 Documents bucket — already correct, keep as-is

```python
# Documents bucket — unchanged from current implementation
docs_agg = await db.safety_documents.aggregate([
    {"$match": {
        "project_id": project_id,
        "deletedAt": None,
        "status": {"$in": ["open", "in_progress"]},
    }},
    {"$group": {
        "_id": None,
        "sev3": {"$sum": {"$cond": [{"$eq": ["$severity", "3"]}, 1, 0]}},
        "sev2": {"$sum": {"$cond": [{"$eq": ["$severity", "2"]}, 1, 0]}},
        "sev1": {"$sum": {"$cond": [{"$eq": ["$severity", "1"]}, 1, 0]}},
    }},
]).to_list(length=1)
sev3 = docs_agg[0].get("sev3", 0) if docs_agg else 0
sev2 = docs_agg[0].get("sev2", 0) if docs_agg else 0
sev1 = docs_agg[0].get("sev1", 0) if docs_agg else 0
docs_raw = sev3 * 10 + sev2 * 5 + sev1 * 2
docs_penalty = min(docs_raw, _SCORE_DOCS_MAX)
```

### 1.3 Tasks bucket — REPLACE flat-5 with severity weighting

```python
# Tasks bucket — overdue tasks grouped by severity (spec §Steps.1)
# Weights: sev3=6, sev2=3, sev1=1.5. Sum capped at _SCORE_TASKS_MAX (25).
tasks_agg = await db.safety_tasks.aggregate([
    {"$match": {
        "project_id": project_id,
        "deletedAt": None,
        "due_at": {"$ne": None, "$lt": now_iso},
        "status": {"$nin": ["completed", "cancelled"]},
    }},
    {"$group": {
        "_id": None,
        "sev3": {"$sum": {"$cond": [{"$eq": ["$severity", "3"]}, 1, 0]}},
        "sev2": {"$sum": {"$cond": [{"$eq": ["$severity", "2"]}, 1, 0]}},
        "sev1": {"$sum": {"$cond": [{"$eq": ["$severity", "1"]}, 1, 0]}},
    }},
]).to_list(length=1)
t_sev3 = tasks_agg[0].get("sev3", 0) if tasks_agg else 0
t_sev2 = tasks_agg[0].get("sev2", 0) if tasks_agg else 0
t_sev1 = tasks_agg[0].get("sev1", 0) if tasks_agg else 0
tasks_raw = t_sev3 * 6 + t_sev2 * 3 + t_sev1 * 1.5
tasks_penalty = min(tasks_raw, _SCORE_TASKS_MAX)
overdue_tasks_total = t_sev3 + t_sev2 + t_sev1
```

### 1.4 Incidents bucket — REPLACE flat-8 with type weighting

```python
# Incidents bucket — last 90d grouped by type (spec §Steps.1)
# Weights: injury=5, property_damage=3, near_miss=1. Sum capped at _SCORE_INCIDENTS_MAX (15).
inc_agg = await db.safety_incidents.aggregate([
    {"$match": {
        "project_id": project_id,
        "deletedAt": None,
        "occurred_at": {"$gte": cutoff_90d},
    }},
    {"$group": {
        "_id": None,
        "injury":          {"$sum": {"$cond": [{"$eq": ["$incident_type", "injury"]}, 1, 0]}},
        "property_damage": {"$sum": {"$cond": [{"$eq": ["$incident_type", "property_damage"]}, 1, 0]}},
        "near_miss":       {"$sum": {"$cond": [{"$eq": ["$incident_type", "near_miss"]}, 1, 0]}},
    }},
]).to_list(length=1)
inc_injury   = inc_agg[0].get("injury", 0) if inc_agg else 0
inc_property = inc_agg[0].get("property_damage", 0) if inc_agg else 0
inc_near     = inc_agg[0].get("near_miss", 0) if inc_agg else 0
incidents_raw = inc_injury * 5 + inc_property * 3 + inc_near * 1
incidents_penalty = min(incidents_raw, _SCORE_INCIDENTS_MAX)
recent_incidents_total = inc_injury + inc_property + inc_near
```

### 1.5 Training bucket — REPLACE any-training logic with required-types-per-worker

```python
# Training bucket — per worker, check each REQUIRED_TRAINING_TYPE has in-force record
# (spec §Steps.1: 4pts per expired-required-training, 5pts for workers with NO training record)
worker_ids_docs = await db.safety_workers.find(
    {"project_id": project_id, "deletedAt": None}, {"_id": 0, "id": 1}
).to_list(length=10000)
worker_ids = [w["id"] for w in worker_ids_docs]

workers_with_expired_training = 0
workers_without_training = 0
expired_required_count = 0  # total (worker × required_type) pairs that are expired/missing

if worker_ids:
    # Fetch all in-force trainings of required types for these workers in one query
    # (in-force = expires_at is None OR expires_at >= today)
    in_force = await db.safety_trainings.find(
        {
            "project_id": project_id,
            "deletedAt": None,
            "worker_id": {"$in": worker_ids},
            "training_type": {"$in": list(REQUIRED_TRAINING_TYPES)},
            "$or": [{"expires_at": None}, {"expires_at": {"$gte": today_iso}}],
        },
        {"_id": 0, "worker_id": 1, "training_type": 1},
    ).to_list(length=100000)

    # Also fetch any training (to distinguish "no records at all" from "records but expired")
    any_training_worker_ids = set(
        r["worker_id"] for r in await db.safety_trainings.find(
            {"project_id": project_id, "deletedAt": None, "worker_id": {"$in": worker_ids}},
            {"_id": 0, "worker_id": 1},
        ).to_list(length=100000)
    )

    # Build {worker_id: set(in_force_required_types)}
    worker_inforce: dict = {wid: set() for wid in worker_ids}
    for r in in_force:
        worker_inforce[r["worker_id"]].add(r["training_type"])

    for wid in worker_ids:
        if wid not in any_training_worker_ids:
            workers_without_training += 1
            continue
        missing_types = REQUIRED_TRAINING_TYPES - worker_inforce[wid]
        if missing_types:
            workers_with_expired_training += 1
            expired_required_count += len(missing_types)

training_raw = expired_required_count * 4 + workers_without_training * 5
training_penalty = min(training_raw, _SCORE_TRAINING_MAX)
```

### 1.6 Final score + return — align shape to spec

Replace the entire `return {...}` block with:

```python
total_penalty = docs_penalty + tasks_penalty + training_penalty + incidents_penalty
score = max(0, int(round(100 - total_penalty)))

return {
    "score": score,
    "breakdown": {
        # Spec-shaped fields (for frontend)
        "doc_penalty": round(docs_penalty, 2),
        "task_penalty": round(tasks_penalty, 2),
        "training_penalty": round(training_penalty, 2),
        "incident_penalty": round(incidents_penalty, 2),
        "doc_counts": {"sev3": sev3, "sev2": sev2, "sev1": sev1},
        "overdue_task_counts": {"sev3": t_sev3, "sev2": t_sev2, "sev1": t_sev1, "total": overdue_tasks_total},
        "workers_with_expired_training": workers_with_expired_training,
        "workers_without_training": workers_without_training,
        "total_workers": len(worker_ids),
        "incidents_last_90d": {
            "injury": inc_injury,
            "property_damage": inc_property,
            "near_miss": inc_near,
            "total": recent_incidents_total,
        },
        # Max caps (for gauge rendering)
        "caps": {
            "doc_max": _SCORE_DOCS_MAX,
            "task_max": _SCORE_TASKS_MAX,
            "training_max": _SCORE_TRAINING_MAX,
            "incident_max": _SCORE_INCIDENTS_MAX,
        },
    },
    "computed_at": now_iso,
}
```

**Note on severity labels:** the spec used `critical/high/medium/low` but the enum has `"1"/"2"/"3"`. Keep the `sev3/sev2/sev1` keys in the response — frontend can label them in Hebrew (גבוהה/בינונית/נמוכה) per `SEVERITY_HE` map.

---

## Fix 2 — Add Management Team section to PDF

**File:** `backend/services/safety_pdf.py`

After the project metadata table (current section "1. פרטי הפרויקט"), **insert** a new section that queries project memberships and renders PM + safety officers.

### 2.1 Add the query (inside `generate_safety_register`, after the existing `user_map` fetch)

```python
# Management team: PM role + safety_officer sub_role
memberships = await db.project_memberships.find(
    {
        "project_id": project_id,
        "deletedAt": None,
        "$or": [
            {"role": {"$in": ["project_manager", "management_team"]}},
            {"sub_role": "safety_officer"},
        ],
    },
    {"_id": 0, "user_id": 1, "role": 1, "sub_role": 1},
).to_list(length=100)

mgmt_user_ids = list({m["user_id"] for m in memberships if m.get("user_id")})
mgmt_users: dict = {}
if mgmt_user_ids:
    for u in await db.users.find(
        {"id": {"$in": mgmt_user_ids}},
        {"_id": 0, "id": 1, "name": 1, "phone": 1, "email": 1},
    ).to_list(length=100):
        mgmt_users[u["id"]] = u
```

### 2.2 Add the section between "1. פרטי הפרויקט" and "2. רשימת עובדים"

**Renumber** the downstream sections: current 2 → 3, 3 → 4, … 8 → 9 (declaration stays at 9).

Insert after the project metadata `elems.append(Spacer(1, 6 * mm))`:

```python
# Section 2: Management Team (NEW in Part 3a)
elems.append(Paragraph(hebrew("2. צוות ניהולי"), h2))
MGMT_ROLE_HE = {
    "project_manager": "מנהל פרויקט",
    "management_team": "צוות ניהולי",
}
if memberships:
    mgmt_rows = []
    for m in memberships:
        u = mgmt_users.get(m.get("user_id", ""), {})
        role_label = MGMT_ROLE_HE.get(m.get("role", ""), m.get("role", ""))
        if m.get("sub_role") == "safety_officer":
            role_label = "ממונה בטיחות"
        mgmt_rows.append([
            u.get("name", "") or "—",
            role_label,
            u.get("phone", "") or "—",
            u.get("email", "") or "—",
        ])
    elems.append(_table(
        ["שם", "תפקיד", "טלפון", "אימייל"],
        mgmt_rows, [4 * cm, 4 * cm, 3.5 * cm, 4.5 * cm],
    ))
else:
    elems.append(Paragraph(hebrew("אין צוות ניהולי רשום לפרויקט."), body))
elems.append(Spacer(1, 6 * mm))
```

### 2.3 Update section numbers 3-8

Change the headers:

| Before | After |
|---|---|
| `"2. רשימת עובדים"` | `"3. רשימת עובדים"` |
| `"3. הדרכות בטיחות"` | `"4. הדרכות בטיחות"` |
| `"4. ליקויי בטיחות פתוחים"` | `"5. ליקויי בטיחות פתוחים"` |
| `"5. משימות מתקנות"` | `"6. משימות מתקנות"` |
| `"6. אירועי בטיחות"` | `"7. אירועי בטיחות"` |
| `"7. סיכום סטטיסטי"` | `"8. סיכום סטטיסטי"` |
| `"8. תיעוד פעולות (30 ימים אחרונים)"` | Remove this header — merge audit trail under section 8 **or** move it above section 9. Keep as sub-paragraph at end of section 8. |
| `"9. הצהרת מנהל העבודה וחתימות"` | unchanged |

---

## Fix 3 — Flatten `$`-keys in audit payload

**File:** `backend/contractor_ops/safety_router.py`

### 3.1 In `export_safety_filtered`, replace the `applied` construction + `_audit` call

**BEFORE:**

```python
applied = {k: (v if not isinstance(v, dict) else v) for k, v in extra.items()}
await _audit("safety_export", project_id, "filtered_exported", user["id"], {
    "project_id": project_id,
    "filters": applied,
    "matched_documents": len(documents),
})
```

**AFTER:**

```python
# Flatten the $gte/$lte range into plain date_from/date_to keys so the audit
# payload never contains $-prefixed field names (MongoDB rejects those on insert).
applied = {k: v for k, v in extra.items() if k != "found_at"}
if date_from:
    applied["date_from"] = date_from
if date_to:
    applied["date_to"] = date_to

await _audit("safety_export", project_id, "filtered_exported", user["id"], {
    "project_id": project_id,
    "filters": applied,
    "matched_documents": len(documents),
})
```

---

## DO NOT

- ❌ Do NOT touch the 3 other endpoints (`/score`, `/export/excel`, `/export/pdf-register`) except for the score formula body.
- ❌ Do NOT touch the 5 CRUD resource routers from Part 1/2 (workers/trainings/documents/tasks/incidents).
- ❌ Do NOT remove the cache or change its TTL. `_SCORE_TTL_SECONDS = 300` stays.
- ❌ Do NOT touch the existing Part 3 PDF sections except for the new Management section and the renumbering of headers. Text, styles, tables stay identical.
- ❌ Do NOT change the `_audit` signature or add new audit types.
- ❌ Do NOT add `REQUIRED_TRAINING_TYPES` as an enum or Pydantic model — it's a plain `frozenset` constant.
- ❌ Do NOT modify `requirements.txt`.
- ❌ Do NOT touch `pdf_service.py` or `handover_pdf_service.py`.
- ❌ Do NOT introduce a separate training-in-force helper function — keep the logic inline in `_compute_safety_score`.
- ❌ Do NOT remove the dead-code `applied = {k: (v if not isinstance(v, dict) else v) ...}` comprehension "because it's ugly" — the fix already replaces it. Don't double-remove.
- ❌ Do NOT cap lists at a smaller number than current (`length=100000` stays).
- ❌ Do NOT bust the cache. After deploy, existing cached scores from the old formulas will be wrong for up to 5 minutes — acceptable.

---

## VERIFY before commit

### 1. Grep sanity

```bash
# (a) REQUIRED_TRAINING_TYPES exists once as a frozenset:
grep -n "REQUIRED_TRAINING_TYPES" backend/contractor_ops/safety_router.py
# Expected: 3-4 hits (definition + usages in compute_safety_score)

# (b) No more flat-5 on tasks:
grep -n "overdue_tasks \* 5" backend/contractor_ops/safety_router.py
# Expected: EMPTY

# (c) No more flat-8 on incidents:
grep -n "recent_incidents \* 8" backend/contractor_ops/safety_router.py
# Expected: EMPTY

# (d) No more $-keys in audit payload:
grep -n '"\$gte"\|"\$lte"' backend/contractor_ops/safety_router.py | grep -i audit
# Expected: EMPTY
grep -n '"filters": applied' backend/contractor_ops/safety_router.py
# Expected: exactly 1 hit, and the applied dict should be constructed via the
# flatten pattern above.

# (e) Management Team section exists in the PDF:
grep -n "צוות ניהולי\|safety_officer" backend/services/safety_pdf.py
# Expected: at least 2 hits (section header + membership query).
```

### 2. Unit sanity — score breakdown shape

With `ENABLE_SAFETY_MODULE=true` locally, hit the endpoint and verify new shape:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.brikops.com/api/safety/PROJECT_ID/score | jq '.breakdown | keys'
# Expected (sorted):
# [
#   "caps",
#   "doc_counts",
#   "doc_penalty",
#   "incident_penalty",
#   "incidents_last_90d",
#   "overdue_task_counts",
#   "task_penalty",
#   "total_workers",
#   "training_penalty",
#   "workers_with_expired_training",
#   "workers_without_training"
# ]
```

### 3. Manual formula test (if feature flag on anywhere)

```bash
# Create a worker with no trainings → expect workers_without_training=1, training_penalty=5
# Add a safety_induction training that expires tomorrow → workers_without_training=0,
#   workers_with_expired_training=1 (still missing height_work + electrical = 2 expired → 8 pts)
# Add height_work + electrical in-force → workers_with_expired_training=0, training_penalty=0
#
# Create an overdue task with severity=3 → tasks_penalty=6
# Create an incident with incident_type=injury occurred_at yesterday → incident_penalty=5
```

### 4. Filtered export audit — no MongoDB error

```bash
# Hit the filtered endpoint WITH a date range (this is the case that used to fail):
curl -o /tmp/f.xlsx -H "Authorization: Bearer $TOKEN" \
  "https://api.brikops.com/api/safety/PROJECT_ID/export/filtered?date_from=2025-01-01&date_to=2025-12-31"
# Expected: 200 with xlsx. No 500. No "InvalidDocument" in backend log.

# Check the audit entry:
# db.audit_events.find({"entity_type":"safety_export","action":"filtered_exported"}).sort({created_at:-1}).limit(1)
# Expected: payload.filters has {date_from, date_to, ...} — NO $gte / $lte keys.
```

### 5. PDF — Management section appears

```bash
curl -o /tmp/r.pdf -H "Authorization: Bearer $TOKEN" \
  https://api.brikops.com/api/safety/PROJECT_ID/export/pdf-register
open /tmp/r.pdf  # Mac
# Expected: Section "2. צוות ניהולי" appears between project metadata and workers list.
# Expected: table with name/role/phone/email of PM(s) + safety officer(s).
# Expected: section numbers now go 1→9 consecutively.
```

### 6. Cache still works

```bash
# First hit:
curl -H "Authorization: Bearer $TOKEN" https://api.brikops.com/api/safety/PROJECT_ID/score | jq '.cache_age_seconds'
# Expected: 0

# Immediate second hit:
curl -H "Authorization: Bearer $TOKEN" https://api.brikops.com/api/safety/PROJECT_ID/score | jq '.cache_age_seconds'
# Expected: > 0 and < 300
```

### 7. Flag-off still 404s

```bash
# With ENABLE_SAFETY_MODULE=false:
curl -H "Authorization: Bearer $TOKEN" https://api.brikops.com/api/safety/PROJECT_ID/score
# Expected: 404
```

---

## Commit message (exactly)

```
fix(safety): Part 3a — port spec score formulas, add PDF management
section, flatten $-keys in audit payload

1) _compute_safety_score: tasks/incidents/training buckets now use
   severity- and type-weighted sums (spec §Steps.1) instead of flat
   weights. Breakdown response shape aligned with Part 4 frontend
   contract (doc_counts, overdue_task_counts, incidents_last_90d,
   workers_with_expired_training, workers_without_training, caps).

2) generate_safety_register: insert section "2. צוות ניהולי" (management
   team) between project metadata and workers list. Pulls PM +
   management_team roles and safety_officer sub_role from
   project_memberships. Downstream sections renumbered 3-9.

3) export_safety_filtered: flatten $gte/$lte into date_from/date_to
   before logging to audit_events — MongoDB rejects $-prefixed field
   names in insert documents. Previously a 500 on any filtered export
   with a date range.

No new deps, no schema changes, no new endpoints. Feature flag
ENABLE_SAFETY_MODULE stays off in prod — deploy is safe.
```

---

## Deploy

```bash
./deploy.sh --prod
```

זה ה-commit וה-push ביחד. אין שלב מהמק.

אחרי ה-deploy — שלח ל-Zahi את `git log -1 --stat` + unified diff לריוויו סופי.

---

## Definition of Done

- [ ] `REQUIRED_TRAINING_TYPES` constant defined once at module level
- [ ] Tasks bucket uses `$cond`-weighted severity aggregation (6/3/1.5)
- [ ] Incidents bucket uses `$cond`-weighted type aggregation (5/3/1)
- [ ] Training bucket uses per-worker-per-required-type logic (4pts expired, 5pts no-record)
- [ ] Score breakdown response includes: `doc_counts`, `overdue_task_counts`, `incidents_last_90d`, `workers_with_expired_training`, `workers_without_training`, `caps`
- [ ] PDF has "2. צוות ניהולי" section with PM + safety officers
- [ ] PDF section numbers go 1 → 9 consecutively
- [ ] `export_safety_filtered` audit payload has `date_from`/`date_to` instead of `$gte`/`$lte`
- [ ] All 5 greps from VERIFY §1 return expected values
- [ ] Filtered export with date range returns 200, not 500
- [ ] `./deploy.sh --prod` ran successfully (commit + push together)
- [ ] Diff sent to Zahi for post-deploy code review
- [ ] No other files modified
- [ ] No new deps in `requirements.txt`
