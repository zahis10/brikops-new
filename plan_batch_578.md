# BATCH #578 — תוכנית עבודה
## Android native Google Sign-In fix: הסרת `scopes` מיותר + העלאת גרסה ל-25

**תאריך:** 2026-08-05 · **Base:** b7b69b3 · **סטטוס:** ⛔ ממתין ל"תתחיל" מזהי — אסור לגעת בקוד

---

## 1. הבעיה (Root cause — אומת ב-STEP 0)

בכניסת Google נייטיבית באנדרואיד (build v24 מה-Play), הקריאה נכשלת מיידית
בלי בוחר חשבונות, עם ההודעה הגנרית "אימות Google נכשל".

הסיבה נמצאת בקוד הפלאגין המותקן
`node_modules/@capgo/capacitor-social-login@7.6.5` — `GoogleProvider.java`:

```java
// Add default scopes
uniqueScopes.add("https://www.googleapis.com/auth/userinfo.email");
uniqueScopes.add("https://www.googleapis.com/auth/userinfo.profile");
uniqueScopes.add("openid");

// Add custom scopes if provided
if (scopesArray != null) {
    if (!(this.activity instanceof ModifiedMainActivityForSocialLoginPlugin)) {
        call.reject("You CANNOT use scopes without modifying the main activity. Please follow the docs!");
        return;
    }
    ...
```

ה-JS שלנו שולח `options: { scopes: ['email','profile'], forcePrompt: true }`,
וה-MainActivity שלנו הוא BridgeActivity רגיל → הקריאה נדחית לפני כל UI של Google.

**המסקנה:** `scopes` באנדרואיד מיותר לחלוטין — הפלאגין מוסיף בעצמו
email + profile + openid כברירת מחדל. הסרתו לא מאבדת כלום ומאפשרת
ל-CredentialManager לרוץ רגיל (בוחר חשבונות → idToken).

- iOS לא מושפע (קוד provider אחר) ועובד היום — לא נוגעים בו.
- צד GCP אומת תקין — אין שינויי ענן.

## 2. ממצאי STEP 0 (הכל תואם לספק)

| בדיקה | תוצאה |
|---|---|
| LoginPage.js ~:313 — בלוק נייטיבי עם `scopes: ['email','profile'], forcePrompt: true` | ✅ מאומת |
| OnboardingPage.js ~:200 — בלוק זהה | ✅ מאומת |
| `Capacitor` מיובא בשני הקבצים (שורות 11 / 16) | ✅ מאומת |
| GoogleProvider.java — בלוק default scopes + reject (~:303-317) | ✅ מאומת, מצוטט למעלה |
| build.gradle — versionCode 24 / versionName "1.0.24" (שורות 11-12) | ✅ מאומת |
| grep "scopes" בשני הקבצים — 2 קריאות נייטיביות + 2 בנתיב GIS ווב (לא נוגעים) | ✅ מאומת |

## 3. העריכות המתוכננות — 3 קבצים בלבד

### E1 — LoginPage.js + OnboardingPage.js (שינוי זהה בשניהם)
החלפת ה-options בבלוק הנייטיבי בלבד:

```js
const loginOptions = Capacitor.getPlatform() === 'android'
  // Android (capgo 7.6.5): passing `scopes` hard-rejects unless
  // MainActivity implements ModifiedMainActivityForSocialLoginPlugin.
  // The plugin adds email/profile/openid by default — scopes are
  // redundant here.
  ? { forcePrompt: true }
  : { scopes: ['email', 'profile'], forcePrompt: true };
const res = await SocialLogin.login({
  provider: 'google',
  options: loginOptions,
});
```

שורת ה-pre-logout והערת auth-google-chooser נשארות ללא שינוי.

### E2 — frontend/android/app/build.gradle
```
versionCode 24        →  versionCode 25
versionName "1.0.24"  →  versionName "1.0.25"
```

## 4. מה אסור (DO NOT)

- לא נוגעים ב-MainActivity.java, בגרסת הפלאגין, ב-package.json או בקבצים נייטיביים אחרים.
- לא נוגעים ב-SocialLogin.initialize (index.js) או בזרימת iOS — iOS ממשיך לשלוח scopes כמו היום.
- לא נוגעים ב-pre-logout / forcePrompt.
- לא נוגעים בנתיב GIS הוובי, ב-backend או בקבצי iOS.
- לא מריצים builds/העלאות לחנויות — זהי עושה זאת ב-Mac.

## 5. אימות (VERIFY)

- **V1** — `CI=true` craco build, יציאה 0.
- **V2** — ציטוט הבלוקים הסופיים משני הקבצים: אנדרואיד בלי מפתח scopes; iOS זהה לחלוטין (string-diff).
- **V3** — grep על ה-diff: בדיוק 3 קבצים (LoginPage, OnboardingPage, build.gradle — 2 שורות).
- **V4** — sanity ווב: `npx serve` על ה-build, נתיב GIS זהה בייט-לבייט ב-diff.

## 6. תוצרים (DELIVERABLES)

- `review.txt` — ציטוטי STEP 0, diff מלא, V1–V4, מסתיים ב-"AWAITING ZAHI APPROVAL — DO NOT DEPLOY".
- `.local/.commit_message` — לפי הנוסח שבספק.

---

⛔ **ממתין לאישור "תתחיל" מזהי — אין נגיעה בקוד עד אז.**
