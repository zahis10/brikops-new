# Spec #383 — enrich `GET /units/{unit_id}/tasks` עם שמות

**Base branch:** main (אחרי #381)
**Scope:** backend בלבד. אפס שינוי ב-frontend.
**Files:**
- `backend/contractor_ops/projects_router.py` — שינוי יחיד ב-`list_unit_tasks` (line ~1084)

---

## הבעיה

ב-FilterDrawer של `ApartmentDashboardPage` (sections של חברה / אחראי / נוצר על ידי) מופיעים UUIDs מקוצרים במקום שמות אמיתיים:

- `af1eb249 1` ← שם חברה
- `c2175280 1` ← שם אחראי
- `af9dcab5 1` ← שם יוצר

הסיבה: ה-frontend בונה labels ככה:
```js
companies[t.company_id]   = t.company_name      || t.assignee_company_name || t.company_id.slice(0, 8);
assignees[t.assignee_id]  = t.assignee_name     || t.assigned_to_name       || t.assignee_id.slice(0, 8);
creators [t.created_by]   = t.created_by_name   || t.created_by.slice(0, 8);
```

ה-API endpoint `GET /units/{unit_id}/tasks` מחזיר `Task(**t).dict()` — והמודל `Task` (ב-`schemas.py`) כולל רק IDs (`company_id`, `assignee_id`, `created_by`) **ללא שדות שם**. לכן כל הפולבקים נכשלים ונופלים על `slice(0, 8)`.

## איך זה נפתר כבר ב-single-task endpoint

ב-`backend/contractor_ops/tasks_router.py:475-491` ה-endpoint `GET /tasks/{task_id}` **כן** עושה enrichment. הוא שולף מ-`project_memberships`, `project_companies`, ו-`users` (fallback chain) את השמות ומחזיר `assignee_name`, `assignee_company_name`, `project_name` וכו'. הקוד הזה יכול לשמש מודל — אבל צריך לייצר גרסה batch שלו כדי לא ליפול ל-N+1 על רשימות של 100+ ליקויים.

---

## TASK #383 — שינוי ב-`backend/contractor_ops/projects_router.py`

### החלפה של `list_unit_tasks` (line ~1084)

```python
@router.get("/units/{unit_id}/tasks")
async def list_unit_tasks(unit_id: str,
                          status: Optional[str] = Query(None),
                          category: Optional[str] = Query(None),
                          user: dict = Depends(get_current_user)):
    db = get_db()
    query = {'unit_id': unit_id}
    if status:
        query['status'] = status
    if category:
        query['category'] = category
    tasks = await db.tasks.find(query, {'_id': 0}).sort('created_at', -1).to_list(1000)
    tasks = sorted(tasks, key=_priority_sort_key)
    from services.object_storage import resolve_urls_in_doc

    # ---- Batch enrichment ----
    project_id = tasks[0].get('project_id') if tasks else None

    company_ids  = {t.get('company_id')  for t in tasks if t.get('company_id')}
    assignee_ids = {t.get('assignee_id') for t in tasks if t.get('assignee_id')}
    creator_ids  = {t.get('created_by')  for t in tasks if t.get('created_by')}

    # companies: project_companies (preferred) ← fallback companies
    company_name_map: dict[str, str] = {}
    if company_ids:
        async for pc in db.project_companies.find(
            {'id': {'$in': list(company_ids)}, 'deletedAt': {'$exists': False}},
            {'_id': 0, 'id': 1, 'name': 1}
        ):
            if pc.get('id'):
                company_name_map[pc['id']] = pc.get('name', '')
        missing = company_ids - set(company_name_map.keys())
        if missing:
            async for c in db.companies.find(
                {'id': {'$in': list(missing)}},
                {'_id': 0, 'id': 1, 'name': 1}
            ):
                if c.get('id'):
                    company_name_map[c['id']] = c.get('name', '')

    # memberships (for assignee_name + assignee company_id)
    membership_map: dict[str, dict] = {}
    if assignee_ids and project_id:
        async for pm in db.project_memberships.find(
            {'project_id': project_id, 'user_id': {'$in': list(assignee_ids)}},
            {'_id': 0, 'user_id': 1, 'user_name': 1, 'company_id': 1}
        ):
            if pm.get('user_id'):
                membership_map[pm['user_id']] = pm

    # users: fallback name source for assignee + source for created_by
    all_user_ids = assignee_ids | creator_ids
    user_name_map: dict[str, str] = {}
    if all_user_ids:
        async for u in db.users.find(
            {'id': {'$in': list(all_user_ids)}},
            {'_id': 0, 'id': 1, 'name': 1}
        ):
            if u.get('id'):
                user_name_map[u['id']] = u.get('name', '')

    # Fetch any extra project_companies referenced via membership.company_id that weren't in tasks
    extra_company_ids = {m.get('company_id') for m in membership_map.values() if m.get('company_id')} - set(company_name_map.keys())
    if extra_company_ids:
        async for pc in db.project_companies.find(
            {'id': {'$in': list(extra_company_ids)}, 'deletedAt': {'$exists': False}},
            {'_id': 0, 'id': 1, 'name': 1}
        ):
            if pc.get('id'):
                company_name_map[pc['id']] = pc.get('name', '')

    # ---- Build response ----
    result = []
    for t in tasks:
        td = Task(**t).dict()
        resolve_urls_in_doc(td)

        if t.get('company_id'):
            td['company_name'] = company_name_map.get(t['company_id'], '')

        if t.get('assignee_id'):
            pm = membership_map.get(t['assignee_id'])
            a_name = (pm.get('user_name') if pm else None) or user_name_map.get(t['assignee_id'], '')
            td['assignee_name'] = a_name
            a_company_id = (pm.get('company_id') if pm else None) or t.get('company_id')
            if a_company_id:
                td['assignee_company_name'] = company_name_map.get(a_company_id, '')

        if t.get('created_by'):
            td['created_by_name'] = user_name_map.get(t['created_by'], '')

        result.append(td)

    return result
```

### שינויים מול הקוד הקיים

1. **הוסרה הגבלת `response_model=List[Task]`** — Pydantic היה מסנן החוצה את שדות השם החדשים. בלי response_model, ה-enrichment עובר לתגובה. הערה: ה-route עדיין מוגדר ב-`async def` עם אותם params, ומחזיר `list[dict]`.
2. **4 queries במקום N×3** — סט אחד ל-project_companies/companies, אחד ל-project_memberships, אחד ל-users, ואופציונלית עוד אחד ל-extra company_ids שגוררים דרך memberships. בסה"כ מקסימום 4-5 queries לכל הרשימה, לא משנה כמה ליקויים.
3. **Fallback chain זהה לזה של ה-single-task endpoint**: project_companies → companies, ו-memberships.user_name → users.name.

---

## DO NOT

- **אל תיגע ב-`GET /tasks/{task_id}`** ב-`tasks_router.py` — הוא עובד נכון.
- **אל תשנה את `Task` ב-`schemas.py`** — ה-enrichment הוא על דאטה response בלבד, לא במודל. הוספת שדות אופציונליים ל-Task תדרוש migrations וסנכרון נוספים.
- **אל תוסיף את אותו enrichment ב-`get_unit_detail`** (line ~1106) — הוא מחזיר kpi counts בלבד, לא רשימת ליקויים.
- **אל תיגע ב-`ApartmentDashboardPage.js`** — הפולבק `|| slice(0, 8)` נשאר כרשת ביטחון, אבל בפועל לא ירוץ יותר כי השמות יגיעו מהשרת.
- **אל תיגע ב-`BuildingDefectsPage.js`** — הוא משתמש ב-endpoint אחר (building aggregate). זה scope נפרד.
- **אל תשתמש ב-MongoDB `$lookup` aggregate pipeline** — הפתרון הפשוט עם 4 queries מספיק. Aggregate יסבך את הקוד ולא יתן תועלת עד שיש אלפי ליקויים.

---

## VERIFY

### Backend

1. `cd backend && pytest contractor_ops/` — כל הטסטים הקיימים עוברים.
2. בדוק ידנית בשרת רץ:
   ```bash
   curl -H "Authorization: Bearer <token>" \
     https://api.brikops.com/units/<unit_id>/tasks | \
     python -m json.tool | \
     grep -E '"(company_name|assignee_name|created_by_name)"'
   ```
   צפוי: 3 שורות עם שמות (לא ריקים כשיש IDs).

3. קוד פייתון:
   ```python
   # חייב להיות בתוך המסלול:
   assert 'response_model' not in inspect.getsource(list_unit_tasks)
   ```

### Frontend (בלי שינוי קוד, רק בדיקת נראות)

4. פתח `https://app.brikops.com/projects/<id>/units/<unitWithDefects>` → לחץ סינון → section "חברה" → **צפוי:** שם קבלן אמיתי במקום `af1eb249`.
5. section "אחראי" → שם משתמש אמיתי במקום `c2175280`.
6. section "נוצר על ידי" → שם יוצר אמיתי במקום `af9dcab5`.
7. אם אין שם זמין כלל (לדוגמה user שנמחק) → ה-section יראה חלק חסר שם (fallback יציג ריק/מקוצר). זה OK — לא regression.

### No regression

8. צפה בכרטיס ליקוי בדף (מחוץ לסינון) → שדות `priority`, `status`, `due_date`, `attachments_count` עדיין מופיעים נכון.
9. פילטרים לפי status/category עדיין עובדים דרך ה-query params.

---

## סיכום Checklist

- [ ] `response_model=List[Task]` הוסר מ-`list_unit_tasks`
- [ ] Batch-fetch ל-project_companies + companies fallback
- [ ] Batch-fetch ל-project_memberships
- [ ] Batch-fetch ל-users (assignees + creators)
- [ ] Extra fetch ל-companies שנגררים דרך memberships
- [ ] כל task עם `company_id` מקבל `company_name`
- [ ] כל task עם `assignee_id` מקבל `assignee_name` + `assignee_company_name`
- [ ] כל task עם `created_by` מקבל `created_by_name`
- [ ] pytest עובר
- [ ] בדיקה ידנית בסינון של `ApartmentDashboardPage` — שמות אמיתיים מופיעים
