# BrikOps — שיטת עבודה לעדכונים

## שורה תחתונה — 2 מצבים בלבד:

### 1. שינוי קוד רגיל (דפים, טקסטים, באגים, לוגיקה)
```
ברפליט: ./deploy.sh --prod
```
זהו. Capgo מעלה OTA אוטומטית, הטלפונים מתעדכנים לבד. לא צריך מק, לא Xcode, לא כלום.

### 2. שינוי native (דרוש ./ship.sh, לא רק ./deploy.sh)

**כל אחד מהקבצים/התיקיות הבאים דורש שגם תריץ `./ship.sh` אחרי ה-`./deploy.sh --prod`:**
- `frontend/capacitor.config.json` — הגדרות פלטפורמה, פלאגינים, channels
- כל מה שתחת `frontend/ios/` — Podfile, Info.plist, Swift, xcconfig, Assets.xcassets
- כל מה שתחת `frontend/android/` — build.gradle, AndroidManifest.xml, Java/Kotlin, res/
- `frontend/package.json` **אם** הוספת או הסרת פלאגין של Capacitor/Capgo
- עדכון `versionCode` / `versionName`

**למה?** כי הקבצים האלה נצרכים ע"י האפליקציה המקומפלת שכבר מותקנת אצלך באייפון/אנדרואיד. עדכון שלהם לא מועבר דרך Capgo OTA — הם דורשים בניה חדשה של האפליקציה + התקנה חדשה.

**סימן זהירות:** אם ערכת אחד מהקבצים האלה ושכחת להריץ `./ship.sh`, האייפון שלך יישאר על הגרסה הישנה לנצח — בשקט, בלי שגיאה. `./deploy.sh --prod` מאז Wave 2d מזהה שינויים כאלה ומדפיס אזהרה צהובה (`NATIVE CHANGES DETECTED`), אבל לא חוסם את ה-push.

```
במק טרמינל:
cd ~/brikops-new
./ship.sh
```

הסקריפט עושה הכל לבד:
- מסנכרן גיט (pull+push) — דואג שהמק מעודכן מול רפליט
- מזהה מה השתנה (iOS / Android / שניהם)
- פותח **רק** את ה-IDE שצריך (Xcode או Android Studio או שניהם)
- אם אין שינוי native — לא פותח כלום, פשוט יוצא

שם אני עושה Archive → Upload. וזהו.

## כללים ברזל:
- אסור לערבב קומיטים ידניים במק עם ./deploy ברפליט — `ship.sh` מטפל בהכל.
- אם השתנו רק קבצים ב-`frontend/src/` או `public/` → **לא צריך native build**. Capgo מטפל.
- אייקונים / capacitor plugins / גרסה → **כן native**.

---

## 🤖 Standing instructions for Cowork (read before every batch)

This section is for the agent (Cowork). Zahi's deploy workflow above
stays the canonical operational doc. Cowork extends it with the
following standing rules.

### Before any spec implementation
1. Read `docs/architecture/README.md` — especially the **conventions**
   and **anti-patterns** sections.
2. If the spec touches a file with an ADR (`docs/architecture/adr-*.md`),
   read that ADR first.
3. Run STEP 0 mandatory pre-flight grep audit (already standing rule):
   - Verify the spec's line refs / file paths still match HEAD.
   - Search for similar patterns elsewhere in the codebase that might
     also be affected (broaden the spec's grep — see BATCH 5I).
   - Check `docs/refactor-backlog.md` for items in the same file
     and propose folding them in (Boy Scout Rule). Get Zahi's approval
     before expanding scope.

### Anti-patterns Zahi has flagged repeatedly
- `WebkitOverflowScrolling: 'touch'` → **NEVER USE** (iOS WebView freeze).
- `ObjectId` → **NEVER USE** (string UUIDs only via `str(uuid.uuid4())`).
- `now_il()` / local-timezone helpers → **NEVER USE** (UTC only at the
  storage layer; use `_now()` from `router.py`).
- `console.log` with PII → **NEVER** in production code paths. Use
  `mask_phone()` from `msg_logger.py` for phone numbers.
- `modal={true}` on Radix Dialog → can leave `pointer-events: none` on
  `body` if the dialog unmounts mid-animation. Default `modal={false}`.
- Photo annotation rendering via `createPortal` → events bubble through
  the React tree. Use the `PhotoAnnotation` component's contained
  event handling, don't lift overlay state up.
- Native `<select>` in RTL + `position:fixed` drawer → escapes ~600px on
  Desktop browsers (Mobile WebView is fine). Use Radix Select for new
  code. Open backlog item: UserDrawer migration (#7).
- `window.confirm()` → looks ugly in mobile WebView. Use a Radix Dialog
  modal. Reference: `TaskDetailPage` reopen confirm modal.
- Local duplicates of constants → silently shadow imports. Always grep
  `^<CONST_NAME> = ` before assuming an update cascades. BATCH 5C found
  one in `handover_router.py`.
- Hardcoded status comparisons (`if status in ["open", "in_progress"]`)
  → silently rot when statuses are added. BATCH 5G added 3 statuses.
  Always go through `STATUS_BUCKET_EXPANSION` (`tasks_router.py:40`).
- `navigate(\`/projects/${id}\`)` → **NO SUCH ROUTE.** Falls through to
  project list. Every project-scoped route has a suffix (`/control`,
  `/dashboard`, etc.). Use `getProjectBackPath()` or hardcode the full
  path with suffix. BATCH 5I fixed two instances.

### Where to find existing helpers (BEFORE building new ones)
- `STATUS_BUCKET_EXPANSION` → `backend/contractor_ops/tasks_router.py:40`
- `TERMINAL_TASK_STATUSES` → `backend/contractor_ops/constants.py:1`
- `_now()` / `_audit()` / `_check_project_access()` /
  `_get_project_role()` → `backend/contractor_ops/router.py`
- `check_org_billing_role()` → `backend/contractor_ops/billing.py:532`
- `mask_phone()` → `backend/contractor_ops/msg_logger.py`
- `validate_upload()` → `backend/contractor_ops/upload_safety.py`
- `getProjectBackPath()` / `navigateToProject()` →
  `frontend/src/utils/navigation.js`
- `t() / tStatus / tCategory / tPriority / tRole / tSubRole / tTrade` →
  `frontend/src/i18n/index.js`
- `formatUnitLabel()` → `frontend/src/utils/formatters.js`

Full reference table in `docs/architecture/README.md` under "When in
doubt — where to find existing helpers".

### Hebrew commit message format Zahi prefers
```
fix(<scope>): <one-line summary in present tense, lowercase>
```
Examples:
- `fix(handover): back arrow returns to /control instead of falling through to /projects`
- `fix(nav): back arrows on /handover and /org-billing route to /control?workMode=structure instead of broken /projects/:id`
- `docs(architecture): add ADRs, refactor backlog, and Cowork standing instructions`

Include a multi-paragraph body when the change has nuance (scope
expansion, drift caught, follow-ups). See `.local/.commit_message` from
the most recent merged batch for the template.

### The standing rule (non-negotiable)
- Branch: **staging** (NOT main).
- Agent **NEVER** runs `./deploy.sh`, `./ship.sh`, `git commit`,
  `git push`. Stop at `review.txt` + `.local/.commit_message` +
  `present_asset`.
- Agent does NOT restart workflows, deploy, or publish.
- Zahi reviews `review.txt`, decides any revisions, then runs
  `./deploy.sh --stag` and `--prod` himself.
- Capacitor / Capgo: Cowork edits the React code only. Capgo OTA picks
  up frontend changes; native edits require Zahi's `./ship.sh`.

When in doubt: **stop and ask.** Don't deploy.
