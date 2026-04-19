# BrikOps — App Store Submission Kit

ערכת הגשה מלאה להגשת BrikOps ל-App Store.

## מבנה התיקייה

```
app-store-submission/
├── README.md                    ← המסמך הזה
├── app-store-content.md         ← כל הטקסטים (תיאור, keywords, privacy Q&A, וכו')
├── icon/
│   └── BrikOps-icon-1024.png    ← אייקון 1024×1024 PNG RGB (מוכן להעלאה)
└── screenshots-6.9/             ← 8 screenshots בגודל 1290×2796 (iPhone 6.9")
    ├── 01-projects-dashboard.png
    ├── 02-create-defect.png
    ├── 03-defect-detail.png
    ├── 04-units-list.png
    ├── 05-defect-status.png
    ├── 06-qc-overview.png
    ├── 07-status-tracking.png
    └── 08-defect-evidence.png
```

## סדר פעולות בהגשה

### 1. App Store Connect → My Apps → BrikOps → Version 1.0 (iOS App)

### 2. App Information (tab)
- Subtitle: `מסירת דירות חכמה וקבלנים`
- Privacy Policy URL: [הזן את ה-URL שלך]
- Category: Primary **Business**, Secondary **Productivity**
- Age Rating: 4+

### 3. Pricing and Availability
- Price: Free
- Availability: Israel (+ מדינות נוספות לפי החלטתך)

### 4. App Privacy → Editא
- Data Collection: Yes
- מלא לפי `app-store-content.md` section "App Privacy Practices Questionnaire"

### 5. Version 1.0 iOS App → Edit (the current version in prep)
- Build: **Select Build 2** מהרשימה (כשיעבור עיבוד מ-TestFlight, 15-60 דק')
- Screenshots (iPhone 6.9" Display):
  - העלה את 8 הקבצים מתיקיית `screenshots-6.9/` בסדר 01→08
- App Icon: יילקח אוטומטית מה-binary (כבר בנוי)
- Promotional Text: הדבק מה-content file
- Description: הדבק מה-content file
- Keywords: הדבק מה-content file
- Support URL + Marketing URL: לפי content file
- Copyright: `© 2026 BrikOps Ltd.`

### 6. App Review Information
- Sign-in required: **Yes**
- ספק username/password של חשבון test
- Contact Info: שם, אימייל, טלפון שלך
- Notes: לפי content file

### 7. Export Compliance
- כשיגיע המייל: Answer **No** (רק HTTPS סטנדרטי → exempt)

### 8. Submit for Review
- לוחצים **Submit for Review**
- זמן בדיקה: 24-48 שעות בדרך כלל
- יתכנו שאלות מ-Reviewer — יגיעו למייל

---

## Checklist לפני Submit

- [ ] Build 2 הועלה ל-App Store Connect (✓ בוצע 11:01)
- [ ] Build 2 עבר עיבוד ומופיע ב-TestFlight (ממתין)
- [ ] בדיקת TestFlight — התקן והרץ ב-iPhone, אמת שה-Apple Sign-In עובד
- [ ] Privacy Policy URL פעיל
- [ ] Test account פעיל ונבדק (reviewer@brikops.com)
- [ ] Subtitle, Keywords, Description הודבקו
- [ ] 8 Screenshots הועלו בסדר הנכון
- [ ] Category מוגדרת (Business + Productivity)
- [ ] App Privacy Questionnaire מולא
- [ ] Age Rating = 4+
- [ ] Copyright מוגדר

---

## שימו לב

1. **Subtitle** נראית אחרי שם האפליקציה — תחשב עליה כhook משני.
2. **Keywords** חשובים מאוד ל-ASO (App Store Optimization). לא לחזור על מילים מהתיאור.
3. **Screenshots** — Apple ממליצה על 6-10. אנחנו עם 8.
4. **Privacy Policy** — חובה כי אוספים email (Apple Sign-In). לא ניתן להגיש בלעדיו.
5. **Test Account** — אם Apple לא מצליחים להיכנס, הם ידחו אוטומטית. Double check שהחשבון עובד.
