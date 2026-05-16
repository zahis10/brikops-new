# BrikOps — Session Handoff

**תאריך:** 22 באפריל 2026
**למי:** צ'אט Claude חדש שממשיך מכאן
**מאת:** הצ'אט הקודם (Zahi Shami — zahis10@gmail.com)

---

## מי אני (הבעלים) ואיך אני עובד

**זהות משפטית:** צחי שמי (Zahi Shami), **עוסק מורשה 203004767** בישראל. לא BrikOps Ltd., לא חברה בע"מ. כל מי שכותב "BrikOps Ltd." — טועה, ותקני מיד.

**סגנון עבודה:** אני לא מפתח. אני נותן הנחיות, ה-AI כותב ספקים, **Replit מבצע**, אני רץ על מק מה שצריך בנייה native. אני מעריך דיוק וחוסך סבלנות לטעויות חוזרות. אל תמציא מידע על הקוד — אם לא ידוע, תקרא את הקובץ.

---

## הארכיטקטורה — תמצית

| רובד | טכנולוגיה |
|---|---|
| Frontend | React 19 (Capacitor 7 wrapper ל-iOS/Android) |
| Backend | Python FastAPI — AWS Elastic Beanstalk (Docker) |
| DB | MongoDB Atlas (M10) |
| Storage | S3 |
| OTA updates | Capgo (רק שינויי JS/React) |
| CI | Replit → git push → Cloudflare Pages (web) + Capgo (mobile OTA) |
| Native builds | מק → Xcode (iOS) / Android Studio (Android) |
| תשלומים | PayPlus (חיצוני, כרטיס אשראי בלבד — Google Pay הוסר בכוונה) |
| SMS OTP | Twilio (iOS) + Google Play Services SMS Retriever API (Android, hash `V0i9QkmW7rd`) |

**נתיבי קוד עיקריים:**
- Frontend: `frontend/src/` — קומפוננטות `components/`, דפים `pages/`, API client `services/api.js`
- Backend: `backend/contractor_ops/` — routers, `otp_service.py`, `schemas.py`
- Android native: `frontend/android/app/src/main/java/com/brikops/app/`
- iOS native: `frontend/ios/`

---

## שיטת העבודה — ברזל

**הכלל הקריטי (מ-`CLAUDE.md` בשורש הריפו):**

### מצב 1 — שינוי קוד רגיל (JS/React/backend/טקסטים/לוגיקה)
```
ברפליט:  ./deploy.sh --prod
```
זהו. Capgo דוחף OTA, הטלפונים מתעדכנים אוטומטית. **לא לפתוח מק**, לא Xcode, לא Android Studio.

### מצב 2 — שינוי native (חייב גם ./ship.sh במק)
הקבצים/תיקיות שמחייבים בנייה native חדשה:
- `frontend/capacitor.config.json`
- כל מה שתחת `frontend/ios/`
- כל מה שתחת `frontend/android/`
- `frontend/package.json` **אם** הוספת/הסרת פלאגין Capacitor או Capgo
- `versionCode` / `versionName` ב-`frontend/android/app/build.gradle` או ב-Xcode

**הזרימה:**
1. Replit: `./deploy.sh --prod` (מזהה native changes ומדפיס אזהרה צהובה `NATIVE CHANGES DETECTED` אבל לא חוסם)
2. מק: `cd ~/brikops-new && ./ship.sh`
   - הסקריפט עושה pull + push, מזהה מה השתנה, פותח Xcode / Android Studio / שניהם
   - אם אין שינוי native — יוצא בלי לפתוח כלום

**איסור:** לא לערבב קומיטים ידניים במק עם `./deploy.sh` ברפליט. `ship.sh` מטפל בכל הסנכרון.

---

## איפה אנחנו עומדים כרגע (snapshot של 22.4.26)

### ✅ נסגר היום
1. **Android OTP autofill** (Spec #395) — עבד סוף-סוף. הבעיה הייתה **Google Play App Signing**: גוגל חותמת מחדש את ה-AAB עם מפתח משלה, לכן ה-SMS Retriever hash חייב להיות נגזר מ-`deployment_cert.der` של Google, לא מה-upload keystore המקומי. ה-hash הנכון: **`V0i9QkmW7rd`** (ישן ושגוי היה `ZewZNI02rYu`). מעודכן ב-AWS Elastic Beanstalk env vars.
2. **Android launcher icon** — האות B כיווצה מ-~50% ל-~40% מהקנבס. Spec: `specs/spec-android-icon-shrink-v2.txt`. רפליט הריץ את `scripts/regenerate_android_icons.py` → 15 PNGs חודשו (5 densities × 3 variants) + versionCode 17→18, versionName 1.0.18. הקומיט: הוזנק ב-./ship.sh במק → Android Studio פתוח.
3. **Apple App Review תשובה ל-Guideline 2.1(b)** — נשלחה דרך Resolution Center. התשובה המלאה שמורה ב-`docs/apple/review-response-2.1b-draft.md` (2,519 תווים, מתחת למגבלת 4,000). מכסה: B2B, PayPlus חיצוני, Guideline 3.1.3(a) Business Services exemption, 7 ימי trial, נתוני פרויקט נשמרים.

### 🟡 פתוח — דורש טיפול קרוב
| # | נושא | מה לעשות |
|---|---|---|
| 25 | Apple Review 2.1(b) | להמתין 24-48 שעות לתשובת Apple. אם מקבלים — Review ממשיך → אישור ב-1-3 ימים. אם דוחים → לחזור לכאן ולחשב מהלך. |
| 26 | Android v1.0.18 AAB | במק (Android Studio): Build → Generate Signed Bundle → AAB 18 → להעלות ל-Play Console → Production → Create new release. **חשוב:** versionCode 18 הכרחי כי 17 כבר נדחה על ידי Play Console. |
| 23 | App Privacy section | למלא את ה-App Privacy section ב-App Store Connect (Data Collection Disclosure). נתונים שנאספים: phone number, email (optional), photos (מהאתר בנייה), location (אופציונלי לפרויקטים). |

### ℹ️ רקע חשוב שצריך לזכור
- **אפל — משרד רשום:** כשמלאנו App Review, המשרד הוא של צחי שמי (עוסק מורשה 203004767), לא BrikOps Ltd. אם אפל שואלת על זה — זו ישות משפטית תקפה בישראל.
- **Apple Pay / Google Pay:** **שניהם הוסרו ב-PayPlus** כדי שאפל לא תתלונן על parity (למה לאנדרואיד יש ולאייפון אין). כרטיס אשראי בלבד בדף PayPlus החיצוני.
- **Sign in with Apple:** כבר מיושם (נדרש כי יש Sign in with Google — Guideline 4.8).
- **שיטות התחברות:** טלפון + SMS OTP הוא היחיד **חובה**. אופציונלית אפשר לקשר email+password או Google auth או Apple auth.
- **7 ימי trial חופשי** לכל ארגון חדש. אחרי — ה-admin בוחר לשלם ב-PayPlus או לא. **נתוני הפרויקט נשמרים בכל מקרה** (רשומות פגמים יש משמעות משפטית/אחריות).

---

## Task list — מצב נוכחי

**Open:**
- #23 App Privacy section ב-App Store Connect (pending)
- #25 Apple Review 2.1(b) — המתנה לתשובת Apple (pending, נוצר היום)
- #26 Android v1.0.18 — בניית AAB + העלאה ל-Play Console (pending, נוצר היום)

**Closed היום:**
- #20 Spec #395 Android OTP autofill → completed (hash תוקן, עובד)
- #24 Build 15 Android icon עם padding → completed (נחלף ב-v1.0.18)

---

## דברים חשובים שחשוב שתדע שלא לעשות

**❌ אל:**
- תכתוב "BrikOps Ltd." בשום מקום. השם הוא **Zahi Shami, Israeli עוסק מורשה 203004767**.
- תגיד לרוץ `./ship.sh` לפני ש-Replit הריץ `./deploy.sh --prod`. זה הפוך מהתהליך.
- תכתוב קבצים ישירות ל-working tree של המק כש-Replit אמור ליצור אותם. הספק נכתב למק → דוחפים ל-git → Replit מושך ומריץ.
- תזכיר Google Pay כאופציה פעילה — הוסר מ-PayPlus.
- תזכיר `Apple Pay` כאופציה — לא פעיל עדיין.
- תמציא תוכן של קובץ שלא קראת. אם לא ידוע — תקרא את הקובץ קודם.
- תערוך את `CLAUDE.md` בשורש. זה source of truth ל-workflow.

**✅ כן:**
- תקרא `CLAUDE.md` בשורש הפרויקט תחילה.
- תשתמש ב-skills הזמינים: `brikops-spec-writer` (ספקים), `brikops-code-reviewer` (review דיפים), `brikops-qa-tester`, `brikops-security-auditor`, `brikops-pen-tester`, `brikops-ux-auditor`, `brikops-facebook-post`.
- תעבוד בצעדים קטנים ותעצור לאישור לפני deploy.

---

## קבצים שכדאי להכיר

| קובץ | מה שם |
|---|---|
| `/CLAUDE.md` | הוראות workflow (deploy.sh / ship.sh — מי עושה מה מתי) |
| `/docs/apple/review-response-2.1b-draft.md` | התשובה שנשלחה ל-Apple היום |
| `/docs/handoff/session-handoff-2026-04-22.md` | הקובץ הזה |
| `/specs/spec-android-icon-shrink-v2.txt` | הספק שרץ היום לאייקון |
| `/scripts/regenerate_android_icons.py` | הסקריפט שרפליט הריץ לחידוש האייקונים |
| `/frontend/android/app/build.gradle` | versionCode 18 / versionName "1.0.18" |
| `/frontend/android/app/src/main/java/com/brikops/app/SmsRetrieverPlugin.kt` | תוסף Kotlin ל-SMS Retriever (Android autofill) |
| `/frontend/src/native/SmsRetriever.js` | גשר JS לתוסף ה-Kotlin |
| `/backend/contractor_ops/otp_service.py` | לוגיקת שליחת OTP (שורה 211-224: מוסיף prefix `<#>` + hash אם platform == android) |
| `/frontend/src/services/api.js` | `requestOtp(phone_e164)` שולח `platform` ל-backend (שורה 578-594) |

---

---

## 🧠 Roadmap אסטרטגי — פיצ'רי AI ומערכות חכמות

זה לא "שטויות dashboard" — זה ה-**X-Factor** של BrikOps מול Cemento, PlanRadar, Fieldwire. אף מתחרה לא עושה AI אמיתי מעל ה-data שלך. המסמכים המלאים יושבים בריפו — אל תכתוב חדשים לפני שקראת אותם:

### 1. BrikOps AI Assistant — add-on בתשלום (₪250/חודש, סה"כ ₪749)
📄 **מסמך מלא:** `/future-features/ai-assistant-concept.md`

**מה זה:** AI Assistant אופציונלי שמנהל פרויקט מפעיל ברמת פרויקט ספציפי. 6 יכולות:
1. **Daily Briefing** (7:30) ב-WhatsApp/Push — מה דחוף, מה תקוע, המלצה לפעולה
2. **Chat Q&A** בתוך האפליקציה — "כמה ליקויים פתוחים בדירה 8?" "איזו דירה הכי מוכנה למסירה?"
3. **Decision Support** — "הדייר רוצה למסור בשבוע הבא, האם מוכנים?" → AI מנתח ועונה עם נתונים
4. **Risk Predictor** (הכי חזק) — מזהה חריגות בקצב סגירת ליקויים, חוזה עיכוב במסירה לפני שהוא קורה
5. **Weekly Report** (יום ו' בבוקר) — סיכום לשליחה ליזם/הנהלה
6. **Onboarding ל-PM חדש** — סיור בפרויקט קיים: "180 דירות, 450 ליקויים, 8 קבלני משנה..."

**החלטות שכבר נסגרו (אל תפתח מחדש):**
- ✅ Self-service activation ב-frontend (לא דרך PayPlus — דרך `manual_override`)
- ✅ הפעלה מיידית + חיוב מחודש הבא (בלי pro-rating)
- ✅ ₪250 add-on, OFF by default, rate-limited גם למשלמים (100 שאלות/יום/פרויקט)
- ✅ **לא לגעת ב-PayPlus core** — עובד דרך `manual_override.total_monthly`

**5 Phases (7-9 שבועות סה"כ):**
Phase 1 Foundation → Phase 2 Chat Widget → Phase 3 Daily Briefing → Phase 4 Risk Predictor → Phase 5 Weekly Report + Polish

### 2. Vision AI — ניתוח אוטומטי של תמונות ליקויים
📄 **POC results:** `/vision-ai-poc-result.md`
📄 **רשימת use-cases:** `/TODO-vision-ai-feature.md`

**POC הוכיח (22.4.26):** Claude Sonnet 4.6 Vision מזהה נכון קטגוריה+מקצוע ב-100%, מייצר תיאור טכני מפורט, ואפילו מזהה סיכוני בטיחות (חיווט חשוף → "קריטי" עם reasoning). עלות: $0.02/תמונה, חיסכון ~20-30 שניות ליקוי.

**6 Use-cases מסודרים לפי ROI:**
1. **Auto-fill של טופס ליקוי** (Phase 1 מומלץ) — PM מצלם → AI ממלא קטגוריה/כותרת/תיאור/מקצוע/severity → PM מאשר/מתקן
2. **דירוג חומרה (Severity)** — AI מציע קוסמטי/מבני/**בטיחותי** עם הסבר. ⚠️ AI *מציע*, PM *מאשר*. לא override אוטומטי.
3. **QC אוטומטי** — מצלם קיר/ריצוף → בודק: ישר? אחיד? פגמים?
4. **Before/After** — תמונת ליקוי ← תמונת תיקון → AI משווה ומאשר/דוחה סגירה
5. **קריאת מונים (handover)** — מצלם מונה מים/חשמל → AI קורא ספרות → ממלא אוטומטית
6. **Completeness check** — מצלם חדר → AI מזהה: חסר שקע, ברז לא מותקן, מזגן לא מחובר → יוצר ליקויים

**ROI מצטבר ל-500 ליקויים בפרויקט:** חיסכון ~3-4 שעות PM, עלות $10 ≈ **שווה פי 100+**.
**Phase 1 מומלץ:** Use-case #1 בלבד (הכי פשוט, הכי הרבה ROI).

### 3. 🔴 פיצ'ר בטיחות + יומן עבודה — **הפיצ'ר הכי חשוב**
📄 **מסמך מלא:** `/future-features/safety-and-worklog-concept.md`

**זאהי הגדיר בצ'אט הזה:** "אולי הדבר הכי חשוב. כמו ב-Cemento — פיצ'ר בטיחות ויומן עבודה. חובה בישראל."

**למה זה חובה, לא nice-to-have:**
- **חובה רגולטורית** — תקנות הבטיחות בעבודה (עבודות בנייה) התשמ"ח-1988 + חוק תכנון ובנייה
- **תנאי לטופס 4** (תעודת גמר בנייה) — בלי יומן עבודה תקין אין אכלוס
- **Cemento (המתחרה העיקרי)** כבר מציע את זה — Enterprise customers לא יעברו בלי
- **הזדמנות עסקית** — מעבר מ"כלי ליקויים" ל-"פלטפורמת ניהול אתר מלאה"; הכפלת ה-ARPU (₪499 → ₪899 Pro tier)

**2 רכיבים תאומים:**

**רכיב A — יומן עבודה יומי (Work Diary):**
רישום יומי חתום דיגיטלית של מנהל עבודה + ממונה בטיחות. כולל מזג אוויר, רשימת עובדים+קבלני משנה, עבודות שבוצעו, חומרים שהגיעו, ציוד כבד, אירועי בטיחות, ביקורות מפקחים. immutable (hash ב-audit_events), PDF חתום לשמירה 7 שנים.

**רכיב B — ניהול בטיחות (Safety Management):**
- B1. סיור בטיחות יומי עם checklists (פיגומים, קסדות, מעקות, כיבוי אש...)
- B2. דיווח תאונות + **near-miss** (קריטי ללמידה ארגונית)
- B3. הדרכות בטיחות (Toolbox Talks) + רישום נוכחים
- B4. אישורי כשירות עובדים (עגורן, גובה, ע"ר) + alerts 30 יום לפני פקיעה
- B5. ביקורות מפקח עבודה (תיעוד + העלאת צווים)
- B6. דוחות (יומי/שבועי/חודשי/שנתי לטופס 4)

**תשתית שכבר קיימת:**
- Sub-roles: `safety_officer`, `safety_assistant`, `work_manager` (כבר במערכת ההזמנות)
- Vision AI POC מזהה `severity="בטיחותי"` עם reasoning
- Collection `audit_events` קיים → immutability ready

**Phases מוצעים (12-15 שבועות סה"כ לפיצ'ר מלא ברמת Cemento):**
1. Phase 1 — יומן עבודה בסיסי + חתימה דיגיטלית + PDF (3-4 שבועות)
2. Phase 2 — סיור בטיחות + ליקויים בטיחותיים (2-3 שבועות)
3. Phase 3 — הדרכות + אישורי כשירות (2 שבועות)
4. Phase 4 — תאונות + near-miss + ביקורות מפקח (2 שבועות)
5. Phase 5 — Auto-fill (מזג אוויר, ברקוד), offline mode, דוחות שנתיים (2 שבועות)
6. Phase 6 — אינטגרציה עם AI Assistant + Vision AI (שבוע)

**שאלות פתוחות שצריך לסגור עם זאהי לפני Phase 1** (8 שאלות מפורטות במסמך הקונספט):
חתימה של מי, offline priority, WhatsApp integration, Cemento import, מבנה checklists, multi-project dashboards וכו'.

**סיכון קריטי לזיהוי:** מורכבות רגולטורית — **מומלץ מאוד לשלב יועץ חיצוני** (ממונה בטיחות ותיק) בסקירת Phase 1 לפני launch כדי לא לפספס דרישת חוק.

### 4. מה שעוד נאמר בדרך אבל לא תועד במסמך עצמאי
רעיונות שהוזכרו בצ'אטים קודמים אבל **כרגע אין עליהם spec רשמי** — לבירור עם זאהי:
- "מערכות חכמות" — כנראה מטרייה לכל ה-AI (Assistant + Vision + Risk) אבל ייתכן שיש רכיבים נוספים
- Integration עם מערכות חיצוניות (אבטחה / מצלמות באתר / בקרת כניסה)
- Automation של תקשורת עם קבלני משנה (WhatsApp bot שמתריע אוטומטית)

---

## 📋 סדר עדיפויות מוצע (לאישור Zahi)

סדר מוצע — אבל **זאהי צריך לאשר/לשנות** לפני שמתחילים משהו חדש:

### **Tier 0 — חובה לפני הכל (app-store clearance)**
1. Apple Review 2.1(b) — המתנה לתשובה (Task #25)
2. Android v1.0.18 AAB upload ל-Play Console (Task #26)
3. App Privacy section ב-App Store Connect (Task #23)

### **Tier 1 — פיתוח אחרי שהחנויות מסודרות**
1. 🔴 **בטיחות + יומן עבודה Phase 1** (יומן בסיסי) — **עדיפות עליונה**. חובה רגולטורית. 3-4 שבועות. מסמך: `/future-features/safety-and-worklog-concept.md`
2. **Vision AI Phase 1** (Auto-fill ליקויים מתמונה) — שבוע פיתוח, ROI מיידי, לא מסוכן
3. **AI Assistant Phase 1** (Foundation + Self-service activation + Upgrade card) — 2-3 שבועות

### **Tier 2 — הרחבה של ה-core offering**
1. 🔴 **בטיחות Phase 2** (סיור בטיחות + ליקויים בטיחותיים) — 2-3 שבועות
2. 🔴 **בטיחות Phase 3** (הדרכות + אישורי כשירות) — 2 שבועות
3. AI Assistant Phase 2 (Chat widget) — שבוע
4. AI Assistant Phase 3 (Daily briefing — **כולל Daily Safety Briefing**) — שבוע
5. Vision AI Phase 2 (Severity suggestion + Before/After)

### **Tier 3 — השלמה לרמת Cemento**
1. 🔴 **בטיחות Phase 4** (תאונות + near-miss + ביקורות מפקח) — 2 שבועות
2. 🔴 **בטיחות Phase 5** (Auto-fill + offline + דוחות שנתיים + טופס 4)
3. 🔴 **בטיחות Phase 6** (אינטגרציה עם Vision AI → יצירת safety tickets אוטומטית)
4. AI Assistant Phase 4 (Risk Predictor)
5. AI Assistant Phase 5 (Weekly Report + Polish + Analytics dashboard)
6. Vision AI Phases 3-6 (QC אוטומטי, קריאת מונים, completeness check)

> **הערה אסטרטגית:** בטיחות + יומן עבודה הוא הפיצ'ר שהופך את BrikOps מ-"כלי ניהול ליקויים" ל-"פלטפורמת ניהול אתר בנייה מלאה". זה מצדיק tier מחיר חדש (Pro ₪899/חודש) ופותח את הדלת ל-Enterprise sales.

---

## פרומפט פתיחה מומלץ לצ'אט החדש

> אני ממשיך פיתוח של BrikOps. לפני שאנחנו עושים משהו, בבקשה קרא את הקבצים הבאים בסדר הזה:
> 1. `CLAUDE.md` בשורש — שיטת העבודה (deploy.sh / ship.sh)
> 2. `docs/handoff/session-handoff-2026-04-22.md` — תמונת המצב (הקובץ הזה)
> 3. `future-features/safety-and-worklog-concept.md` — **🔴 הפיצ'ר הכי חשוב: בטיחות + יומן עבודה**
> 4. `future-features/ai-assistant-concept.md` — ה-AI Assistant (₪250 add-on)
> 5. `vision-ai-poc-result.md` + `TODO-vision-ai-feature.md` — Vision AI
>
> אחרי שקראת, תגיד לי:
> א. מה המשימה הכי דחופה שנשארה (מתוך Tier 0 — Apple/Android clearance)
> ב. איך לעבור אל פיצ'ר הבטיחות + יומן עבודה (Phase 1 — יומן בסיסי) — יש 8 שאלות פתוחות במסמך הקונספט שאנחנו צריכים לסגור לפני spec כתובה ל-Replit.

---

**סוף מסמך handoff.**
