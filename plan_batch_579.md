# BATCH #579 — תוכנית עבודה
## Auth pages (web only): קישורי הורדה לחנויות בכרטיסי ההרשמה וההתחברות

**תאריך:** 2026-08-09 · **Base:** 8fae782 · **FRONTEND בלבד, 2 קבצים** · **סטטוס:** ⛔ ממתין ל"תתחיל"

---

## 1. מה ולמה

ה-CTA בלנדינג שולח מבקרים ל-app.brikops.com/onboarding (הרשמה ווב) — טוב
להרשמה ללא חיכוך, אבל מי שמעדיף להתקין את האפליקציה לא מקבל שום נתיב לחנויות.
נוסיף רצועת "מעדיפים את האפליקציה?" עם קישורי App Store / Google Play
לשני כרטיסי ה-auth (OnboardingPage + LoginPage):

- מוצג **רק בווב** — לעולם לא בתוך האפליקציות הנייטיביות (guard חובה).
- סינון לפי מכשיר בדפדפני מובייל: אנדרואיד → רק Google Play, iPhone/iPad → רק App Store, דסקטופ → שניהם.
- אפס שינויי לוגיקה בזרימות ה-auth.

## 2. ממצאי STEP 0 (על 8fae782)

| בדיקה | תוצאה |
|---|---|
| grep `apps.apple.com \| play.google.com` על frontend/src | ✅ אפס תוצאות (כצפוי) |
| OnboardingPage — בלוק חברתי (divider "או הרשמה עם" + Google/Apple + כפתור "יש לי כבר חשבון") | ✅ מצוטט — מופיע **פעמיים** (:~848 כרטיס ראשי, :~1181 בתוך `!socialFlow`) |
| LoginPage — divider "או התחבר עם" (:770) + Google/Apple; תחתית הכרטיס: "אין לך חשבון? הרשמה" (:~1006) + קישור נגישות | ✅ מצוטט |
| `Capacitor` מיובא | ✅ OnboardingPage:16, LoginPage:11 |

**הערה לזהי:** בגלל שהבלוק החברתי ב-OnboardingPage מופיע בשני נתיבי רנדור,
התוכנית מוסיפה את הרצועה **בשני המופעים** כדי שאף נתיב הרשמה לא יפספס אותה.
אם מעדיפים רק את הכרטיס הראשי — להגיד לפני "תתחיל".

## 3. העריכות — 2 קבצים בלבד (תוספת זהה)

### E1 — helper פנימי בכל קובץ (בלי קבצים חדשים, בלי deps)

```js
const getWebStoreLinks = () => {
  if (Capacitor.isNativePlatform()) return [];   // never inside the apps
  const ua = navigator.userAgent || '';
  const isAndroid = /Android/i.test(ua);
  const isIOS = /iPhone|iPad|iPod/i.test(ua) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const ios = { key: 'ios', href: 'https://apps.apple.com/il/app/brikops/id6762542628', label: 'App Store' };
  const play = { key: 'android', href: 'https://play.google.com/store/apps/details?id=com.brikops.app', label: 'Google Play' };
  if (isAndroid) return [play];
  if (isIOS) return [ios];
  return [ios, play];                             // desktop: both
};
```

### E2 — רנדור הרצועה בתחתית כרטיס ה-auth (רק כשהרשימה לא ריקה)

```jsx
<div className="mt-4 pt-3 border-t border-slate-100 text-center">
  <p className="text-xs text-slate-400 mb-2">מעדיפים את האפליקציה?</p>
  <div className="flex justify-center gap-2">
    {links.map(l => (
      <a key={l.key} href={l.href} target="_blank" rel="noopener noreferrer"
         className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-600 hover:border-amber-400 hover:text-amber-700">
        {/* אייקון SVG inline (Apple / Play), 14px, currentColor */}
        {l.label}
      </a>
    ))}
  </div>
</div>
```

**מיקומים:**
- **OnboardingPage** — מיד אחרי בלוק כפתור "יש לי כבר חשבון - התחברות", בשני המופעים (:~848, :~1181).
- **LoginPage** — אחרי בלוק "אין לך חשבון? הרשמה", מעל קישור הנגישות (המקום הנקי בתחתית הכרטיס).

אייקונים: SVG inline בלבד (אותם paths כמו בבאדג'ים בלנדינג), בלי תמונות חדשות ובלי deps.

## 4. מה אסור (DO NOT)

- לא נוגעים בשום לוגיקת auth: OTP, checkbox תנאים, handlers חברתיים, ענפים נייטיביים, socialAuth, ניווט.
- הרצועה לעולם לא מוצגת בתוך האפליקציות — ה-guard `isNativePlatform()` ב-E1 חובה ויצוטט ב-review.
- בלי deps, תמונות או קבצים חדשים.
- לא נוגעים בשום עמוד אחר או ב-backend.

## 5. אימות (VERIFY)

- **V1** — `CI=true` craco build, יציאה 0.
- **V2** — צילומי מסך @390px (אמולציית מכשיר):
  - a. Onboarding עם iPhone UA → רק App Store.
  - b. Onboarding עם Android UA → רק Google Play.
  - c. דסקטופ → שניהם, layout שלם.
  - d. LoginPage — אותן שלוש בדיקות (לפחות צילום אחד).
  - e. הכרטיס לא נשבר ב-390px באף מצב.
- **V3** — ציטוט ה-guard שמוכיח שהרצועה לא מרונדרת כש-`Capacitor.isNativePlatform()` אמת.
- **V4** — היקף diff: בדיוק OnboardingPage.js + LoginPage.js.

## 6. תוצרים (DELIVERABLES)

- `review.txt` — ציטוטי STEP 0, diff מלא, V1–V4, מסתיים ב-"AWAITING ZAHI APPROVAL — DO NOT DEPLOY".
- `.local/.commit_message` — לפי הנוסח שבספק.

---

⛔ **ממתין לאישור "תתחיל" מזהי — אין נגיעה בקוד עד אז.**
