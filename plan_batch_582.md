# BATCH #582 — תוכנית עבודה

**Notification history UI: מניעת גלילה אופקית + הודעת SMS מדויקת**

- תאריך: 2026-08-31
- Branch: `staging`
- Base: `44d2c7d` (תואם HEAD)
- Scope: frontend + passthrough סכמטי מינימלי שנדרש לפי STEP 0

## STEP 0 — ממצאים

### בלוק היסטוריית ההתראות

`TaskDetailPage.js` טוען את הרשימה כך:

```js
const [notifData, members, projCompanies] = await Promise.all([
  notificationService.getTimeline(id),
  projectService.getMemberships(taskData.project_id),
  projectCompanyService.list(taskData.project_id).catch(() => []),
]);
setNotifications(notifData);
```

הרשימה מגיעה מ-`GET /tasks/{task_id}/notifications`, דרך
`notificationService.getTimeline`.

ברינדור:

```jsx
{notifications.map(n => {
  const cfg = NOTIF_STATUS_CONFIG[n.status] || NOTIF_STATUS_CONFIG.queued;
  const Icon = cfg.icon;
  const channelLabel = n.channel === 'sms' ? 'SMS' : n.channel === 'whatsapp' ? 'WhatsApp' : n.channel;
  ...
  {(n.status === 'queued' || n.status === 'sent') && n.created_at &&
    (Date.now() - new Date(n.created_at).getTime() > 60000) && (
    <div className="mt-1.5 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
      <p className="font-medium">⚠ לא התקבל אישור מסירה</p>
      ...
    </div>
  )}
  {n.last_error && (
    <p className="text-xs text-red-500 mt-1">{n.last_error}</p>
  )}
})}
```

כפתור "העתק דיבוג" כבר מעתיק את `channel` ואת `last_error` המלאים.

### האם `channel` מגיע ל-Frontend?

לא. מסמכי `notification_jobs` מכילים `channel`, וה-endpoint קורא אותם ישירות,
אבל `NotificationJobResponse` ב-`backend/contractor_ops/schemas.py` אינו כולל
את השדה. מאחר שה-endpoint מוגדר עם:

```python
@router.get("/tasks/{task_id}/notifications",
            response_model=List[NotificationJobResponse])
```

Pydantic מסנן את `channel` מהתגובה. לכן נדרש passthrough additive מינימלי:

```python
channel: Optional[str] = None
```

זהו ה-backend serializer היחיד שיידרש; אין שינוי בלוגיקת ההתראות.

## עריכות

1. `frontend/src/pages/TaskDetailPage.js`
   - הוספת `break-all overflow-hidden` ו-`dir="ltr"` ל-`last_error`.
   - כאשר ההתראה ישנה מ-60 שניות ובסטטוס queued/sent:
     - `channel === 'sms'`: שורה ניטרלית אפורה — "נשלח כ-SMS — אין מעקב מסירה להודעות SMS".
     - כל ערוץ אחר: הקופסה הצהובה הקיימת נשארת ללא שינוי.
   - ללא שינוי בטקסט השגיאה, סטטוסים, timestamps, IDs או כפתור הדיבוג.

2. `backend/contractor_ops/schemas.py`
   - הוספת `channel: Optional[str] = None` בלבד ל-`NotificationJobResponse`.

## אימות

1. build עם `CI=true`, יציאה 0.
2. בדיקה וצילומי מסך ב-390px:
   - שגיאה לא-שבירה באורך 300+ תווים נשארת בתוך הכרטיס ואין scroll אופקי.
   - SMS ישן מציג שורה אפורה בלבד, ללא קופסה צהובה.
   - WhatsApp ישן ממשיך להציג את הקופסה הצהובה ללא שינוי.
3. diff scope: רק `TaskDetailPage.js` ו-`schemas.py`; שינוי ה-backend הוא שדה
   passthrough additive בלבד.
4. יצירת `review.txt` ו-`.local/.commit_message` לפי הספק.

---

**עוצר כאן — לא נוגע בקוד עד "תתחיל".**