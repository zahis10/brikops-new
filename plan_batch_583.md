# BATCH #583 — תוכנית עבודה

**Notification history: תצוגה ממוקדת משתמש, עם דיבוג מקופל תחת "פרטים"**

- תאריך: 2026-08-31
- Branch: `staging`
- Base: `8c8abc8` (תואם HEAD; workspace נקי)
- Scope: Frontend בלבד, קובץ אחד:
  `frontend/src/pages/TaskDetailPage.js`

## STEP 0 — ממצאים

### 1. שורת ההתראה הנוכחית

כל שורה נוצרת בתוך:

```jsx
{notifications.map(n => {
  const cfg = NOTIF_STATUS_CONFIG[n.status] || NOTIF_STATUS_CONFIG.queued;
  const Icon = cfg.icon;
  const channelLabel = n.channel === 'sms'
    ? 'SMS'
    : n.channel === 'whatsapp'
      ? 'WhatsApp'
      : n.channel;
  const maskedPhone = ...;
```

בראש השורה מוצגים:

```jsx
<Icon className={`w-4 h-4 ${cfg.color}`} />
<span className={`text-sm font-medium ${cfg.color}`}>{cfg.label}</span>
{channelLabel && (
  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-200 text-slate-600 font-medium">
    {channelLabel}
  </span>
)}
...
<span className="text-xs text-slate-400">
  {n.created_at ? new Date(n.created_at).toLocaleString('he-IL') : ''}
</span>
```

בשורה השנייה מוצגים תג האירוע והטלפון הממוסך, ולצידם retry (רק failed)
וכפתור "העתק דיבוג". כפתור הדיבוג מעתיק את אותו אובייקט מלא:

```js
{
  task_id: n.task_id,
  job_id: n.id,
  masked_phone: maskedPhone,
  message_id: n.provider_message_id || '',
  delivery_state: n.status,
  channel: n.channel,
  event_type: n.event_type,
  error: n.last_error || null,
  created_at: n.created_at,
  updated_at: n.updated_at,
}
```

אחריהם, בתצוגת ברירת המחדל, מופיעים כיום:

```jsx
{n.provider_message_id && (
  <p className="text-[10px] text-slate-400 mt-1 font-mono truncate" dir="ltr">
    msg: {n.provider_message_id}
  </p>
)}
{n.updated_at && n.updated_at !== n.created_at && (
  <p className="text-[10px] text-slate-400 mt-0.5">
    עודכן: {new Date(n.updated_at).toLocaleString('he-IL')}
  </p>
)}
```

בלוק queued/sent מעל 60 שניות:

```jsx
{oldQueuedOrSent && (
  n.channel === 'sms' ? (
    <p className="text-[10px] text-slate-400 mt-1.5">
      נשלח כ-SMS — אין מעקב מסירה להודעות SMS
    </p>
  ) : (
    <div className="mt-1.5 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
      <p className="font-medium">⚠ לא התקבל אישור מסירה</p>
      <p className="text-[10px] text-amber-600 mt-0.5">
        עדכון אחרון: ...
        {n.provider_message_id && <span ...>msg: ...</span>}
      </p>
    </div>
  )
)}
```

והשגיאה הגולמית מ-#582:

```jsx
{n.last_error && (
  <p className="text-xs text-red-500 mt-1 break-all overflow-hidden" dir="ltr">
    {n.last_error}
  </p>
)}
```

### 2. דפוס expand/collapse קיים בקובץ

**ממצא:** אין בקובץ דפוס קיים של expanded row IDs או תוכן מקופל פר-שורה.
ה-expand היחיד הוא `InlineSelect`, שמשתמש ב:

```js
const [open, setOpen] = useState(false);
```

וב-`ChevronDown` שכבר מיובא. קיימים גם שימושים ב-`ChevronRight`, אך הם
קישורי ניווט ולא collapse.

לכן, בהתאם להוראת E3 המפורשת, יתווסף state יחיד ברמת `TaskDetailPage`:

```js
const [expandedNotificationIds, setExpandedNotificationIds] = useState(new Set());
```

ה-toggle יעדכן את ה-Set בצורה immutable. נשתמש ב-`ChevronDown` שכבר מיובא
ונסובב אותו במצב פתוח; אין dependency או import חדש.

זהו פער קטן מהנחת STEP 0 ("existing pattern"), אך אינו חוסם: הספק עצמו
מורה במפורש על `useState` יחיד של expanded row ids, והכלים הדרושים כבר קיימים.

## עריכות

### E1 — תצוגת ברירת מחדל

תציג רק:

- אייקון + סטטוס
- צ'יפ ערוץ
- תג event type
- טלפון ממוסך
- זמן יצירה
- retry הקיים במקרה failed
- אזהרת WhatsApp הצהובה הקיימת, ללא שינוי בהתנהגות

יוסרו מברירת המחדל ויעברו ל"פרטים": msg id, זמן עדכון, raw error, הערת
SMS האפורה וכפתור העתקת הדיבוג.

### E2 — שורת fallback ידידותית

רק כאשר:

```js
n.channel === 'sms' && n.last_error?.startsWith('wa_failed')
```

תוצג כברירת מחדל:

> ווטסאפ לא היה זמין — נשלח כ-SMS

SMS רגיל לא יקבל שורה נוספת.

### E3 — "פרטים" פר-שורה

כפתור טקסט קטן עם chevron. במצב פתוח יוצגו:

- `עודכן:` אם זמן העדכון שונה מזמן היצירה
- full provider message id עם `dir="ltr"` ו-`break-all`
- raw `last_error` באדום, עם מחלקות ההכלה של #582 ו-`dir="ltr"`
- הערת "אין מעקב מסירה ל-SMS"
- כפתור "העתק דיבוג" עם payload ולוגיקה זהים לחלוטין

המידע לא יוסר — רק יעבור לאזור המקופל.

### E4 — ללא שינויים אחרים

לא נוגעים בסטטוסים, אייקונים, סדר ההתראות, data fetching, payload של
copy-debug, backend, schemas, endpoints או notification logic.

## אימות

1. `CI=true` craco build, יציאה 0.
2. Playwright ב-390px עם mock data:
   - collapsed SMS fallback: status + chip + phone + time + friendly line,
     ללא debug גלוי.
   - collapsed WhatsApp read: status + chip + phone + time בלבד.
   - expanded SMS "פרטים": msg id, עודכן, raw error עטוף, הערת SMS וכפתור
     copy-debug; `scrollWidth === innerWidth`.
   - WhatsApp sent מעל 60 שניות: האזהרה הצהובה נשארת בתצוגת ברירת המחדל.
3. diff scope: `TaskDetailPage.js` בלבד.
4. `review.txt` עם STEP 0, diff מלא ו-V1–V3; וכן
   `.local/.commit_message` לפי הספק.

---

**עוצר כאן — לא נוגע בקוד עד "תתחיל".**