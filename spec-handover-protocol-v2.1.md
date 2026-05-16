    # SPEC — BrikOps Handover Protocol v2.1

    ## הקשר (קרא לפני שאתה מתחיל)

    יש לי קובץ HTML אחד עצמאי בשם **`BrikOps Handover Protocol.html`** — מוקאפ של פרוטוקול מסירה (Handover Protocol) לדירה חדשה בעברית, RTL, מותאם A4 (794×1123 @ 96dpi). זה מסמך שעובר ייצוא ל-PDF ונשלח ל**יזמים, קבלנים, מהנדסים, בודקי בית ודיירים**.

    המוצר נקרא **BrikOps**. המתחרה הראשי הוא **Semento** — הם משתמשים בפרוטוקולים של 53 עמודים בעיצוב פלאט-אפור משנת 2008. אצלי המסמך הוא 14 עמודים בעיצוב SaaS מודרני, ואני רוצה לשמור על הפער הזה.

    המבנה הקיים (7 עמודי תבנית): **Cover → TOC + Defects Summary → Room Inspections → Defect Detail → Handed-Over Items + Meters → Legal Declarations → Signatures**.

    ---

    ## עקרונות-על

    1. **שמור על הזהות הוויזואלית הקיימת.** הצבעים, הטיפוגרפיה, הירארכיית הכותרות, מבנה ה-Cover Hero, מבנה הסטטס פאנל, מבנה כרטיסי החתימה — **אל תיגע**. כל שינוי שלא מופיע בספק הזה במפורש = אסור.
    2. **המסמך מודפס ל-PDF.** אל תוסיף JS, אינטראקציות hover, או דברים שחיים רק בדפדפן. הכל סטטי.
    3. **עברית + RTL בלבד.** אסור להוסיף טקסט באנגלית בתוך תוכן (page-label בלעז זה תחזוקה — מותר).
    4. **אל תשנה את ה-bundler wrapper** של הקובץ. ערוך רק את ה-template הפנימי (ה-HTML/CSS שיוצא אחרי ה-unpack).

    ---

    ## עיצוב סיסטם קיים (לעיון, לא לשנות)

    ```
    --orange: #F08A3E       (accent ראשי)
    --ink: #0F1626          (טקסט ראשי + hero כהה)
    --green: #16A34A        (תקין)
    --red: #DC2626          (ליקוי קריטי)
    --amber: #D97706        (אזהרה / חלקי)
    --blue: #2563EB         (קוסמטי / מידע)
    --paper: #FAFBFD        (רקע משני)
    --slate-1..7            (אפורים)

    font-family: "Heebo", system-ui, sans-serif
    ```

    ---

    ## 5 התיקונים הקריטיים

    ### תיקון 1 — להחליף את כל האימוג'ים ב-SVG inline

    **הבעיה:** אימוג'ים נראים שונה לחלוטין בכל מערכת הפעלה (Windows שונה מ-macOS שונה מ-Android), ובייצוא ל-PDF הם לפעמים יוצאים לבן-שחור או נעלמים. זה הורג את המקצועיות.

    **מצא והחלף את כל ההופעות הבאות בקובץ:**

    | מיקום | אימוג'י נוכחי | החלף ל-SVG |
    |---|---|---|
    | `.meter.water .icon` | `💧` | Lucide `droplet` 18×18, stroke #1E40AF |
    | `.meter.elec .icon` | `⚡` | Lucide `zap` 18×18, stroke #92400E |
    | `.meter.gas .icon` | `🔥` | Lucide `flame` 18×18, stroke #9A3412 |
    | `.room-summary.bad` | `🚨` | Lucide `alert-triangle` 14×14, stroke #991B1B, inline-flex |
    | `.room-summary` (כללי) | `⚠️` | Lucide `alert-circle` 14×14, stroke matching color |
    | `.legal-sigline .sigchip::before` | `✓` בעיגול | SVG check inline בתוך ה-`::before` (background-image: url with data-uri SVG, או החלף ל-`<span>` רגיל בתוך ה-DOM) |
    | `.room-summary.clean` | `✓` | Lucide `check-circle` 14×14, stroke #166534 |

    **איך מטמיעים SVG inline:** העתק את ה-path ישירות מ-https://lucide.dev (אל תוריד SVG כקובץ נפרד — הכל חייב להיות inline בתוך ה-HTML/CSS). דוגמה ל-`droplet`:

    ```html
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5S5 13 5 15a7 7 0 0 0 7 7z"/>
    </svg>
    ```

    עבור ה-`::before` בכרטיסי חתימה — שנה את ה-CSS כך ש-`content: ""` ו-`background-image: url("data:image/svg+xml;utf8,<svg ...>");` (URL-encoded SVG inline).

    **אחרי התיקון:** חפש בקובץ עם regex `[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2700}-\u{27BF}]` — חייב להחזיר 0 תוצאות.

    ---

    ### תיקון 2 — Thumbnail של תמונת הדירה ב-Cover Hero

    **הבעיה:** ה-Cover שלי לא נושא חתימה ויזואלית של *הדירה הספציפית*. סמנטו דווקא עושים את זה (תמונת בניין בעמוד 1). אני חייב להיות לפחות שווה להם בעיצוב הרגשי.

    **מה לעשות:**

    ב-`<div class="cover-top">` הקיים — כרגע יש שני אלמנטים: `cover-logo` ו-`cover-meta`. הוסף **אלמנט שלישי באמצע** (סדר RTL: לוגו ימין → תמונה אמצע → meta שמאל):

    ```html
    <div class="cover-top">
      <img class="cover-logo" src="..." alt="BrikOps">
      
      <div class="cover-thumb">
        <!-- placeholder תמונת הבניין/הדירה -->
      </div>
      
      <div class="cover-meta">...</div>
    </div>
    ```

    CSS:
    ```css
    .cover-thumb {
      width: 88px;
      height: 88px;
      border-radius: 12px;
      background: 
        linear-gradient(135deg, rgba(255,255,255,.08) 0%, rgba(255,255,255,.02) 100%);
      border: 1px solid rgba(255,255,255,.18);
      flex-shrink: 0;
      position: relative;
      overflow: hidden;
      /* placeholder pattern: SVG icon של בניין באמצע + תווית "תמונת חזית" קטנה למטה */
    }
    .cover-thumb::after {
      /* SVG icon של building inline (Lucide "building-2") - 32px, opacity 0.4, מרכז */
    }
    ```

    הוסף `align-items: center` ל-`cover-top` כדי שהשלישייה תיישר נכון.

    ---

    ### תיקון 3 — לצמצם 10 צבעי trade ל-6

    **הבעיה:** יש לי כרגע 10 קלאסים של trade (elec, plumb, tile, paint, alum, door, gen, kitch, iron, plast) — כל אחד עם זוג צבעים שונה. זה מסיט את העין מהסטטוס (שזה הנתון העיקרי). כלל UX: מקסימום 6–7 קטגוריות צבע במסמך אחד.

    **עשה את האיחודים הבאים:**

    | איחוד | קלאסים נוכחיים | קלאס חדש | צבע (background / color) |
    |---|---|---|---|
    | פתחים ומסגרות | `door` + `iron` | `frame` | `#DCFCE7` / `#14532D` (ירוק עמוק) |
    | גימור | `paint` + `plast` | `finish` | `#FCE7F3` / `#9D174D` (ורוד-בורדו) |

    נשארים בלי שינוי: `elec, plumb, tile, alum, gen, kitch` (6).

    **עדכן בכל ה-HTML:**
    - `<span class="trade door">דלתות</span>` → `<span class="trade frame">פתחים ומסגרות</span>`
    - כל הופעה של `paint` או `plast` → `finish` עם תווית "גימור"

    מחק את ה-CSS rules של `.trade.door`, `.trade.iron`, `.trade.paint`, `.trade.plast` והוסף את `.trade.frame` ו-`.trade.finish`.

    ---

    ### תיקון 4 — להסיר dashed borders מיותרים

    **הבעיה:** `border-bottom: 1px dashed` נראה לא חד בייצוא PDF, ויש בו שימוש יתר.

    **עשה replace:**

    | selector | מ- | ל- |
    |---|---|---|
    | `.kv` | `border-bottom: 1px dashed var(--slate-2)` | `border-bottom: 1px solid var(--slate-2)` |
    | `.tenant` | `border-bottom: 1px dashed var(--slate-2)` | `border-bottom: 1px solid var(--slate-2)` |
    | `.toc-item` | `border-bottom: 1px dashed var(--slate-2)` | `border-bottom: 1px solid var(--slate-2)` |

    **שמור dashed רק ב-`.legal-sigline` ו-`.defect-card-body`** (שם dashed יש לו משמעות ויזואלית — מפריד התחייבות מחתימה).

    ---

    ### תיקון 5 — Fallback לתמונות שנכשלות

    **הבעיה:** הסלקטור `.photo` משתמש כרגע ב-`repeating-linear-gradient` בתור placeholder. זה נראה כמו תכלת משוייפת — קבלן/יזם יחשוב שיש באג בקובץ.

    **שנה את ה-`.photo` placeholder ל-fallback מקצועי:**

    ```css
    .photo {
      aspect-ratio: 4/3;
      border-radius: 8px;
      background: var(--slate-1);
      border: 1px solid var(--slate-2);
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 6px;
      color: var(--slate-5);
    }
    .photo::before {
      /* SVG icon של "image-off" של Lucide, 28×28, stroke currentColor, stroke-width 1.5 */
      content: "";
      width: 28px;
      height: 28px;
      background-image: url("data:image/svg+xml;utf8,<svg ...>");
      background-repeat: no-repeat;
      background-position: center;
    }
    .photo::after {
      /* התווית הקיימת של data-label עוברת לפינה תחתונה */
      font-family: "JetBrains Mono", monospace;
      font-size: 10px;
    }
    ```

    הוסף ל-`.photo` כשיש תמונה אמיתית — קלאס `has-image` שמכבה את ה-`::before`.

    ---

    ## 2 שיפורים אופציונליים (אם נשאר זמן)

    ### שיפור A — QR Code בעמוד החתימות

    בתחתית עמוד 7 (Signatures), בלוק האימות הדיגיטלי הקיים — הוסף **QR code SVG inline** מצד שמאל של הטקסט. ה-QR מצביע ל-`https://brikops.com/verify/BO-2026-0412`. ייצור: השתמש בספריית `qrcode-svg` או pre-render את ה-QR כ-SVG path inline. גודל: 64×64. רקע לבן, foreground #0F1626.

    מטרה: דייר/יזם יכול לסרוק ולוודא שהמסמך אותנטי = יתרון אדיר על Semento.

    ### שיפור B — Section "תיקונים מאז ביקור קודם" ב-TOC

    בעמוד 2 (TOC), מתחת לסיכום הליקויים — הוסף בלוק קטן:

    ```
    ✓ תוקן מאז ביקור #1 (4.2.2026):
      • דלת כניסה — סגר עליון תוקן
      • סלון — נורה הוחלפה
      • אמבטיה הורים — סיליקון חודש
      
    התקדמות כללית: 14 ליקויים → 5 ליקויים (–64%)
    ```

    עיצוב: כרטיס ירוק רך (`background: var(--green-soft)`, `border-right: 3px solid var(--green)`) — דומה ל-`.legal-block` אבל בירוק. כל פריט עם chip ירוק קטן עם check.

    מטרה: מציג לקבלן credit על העבודה שלו = יחסים טובים יותר. סמנטו לא יודעים לעשות את זה כי הם לא tracker — הם טופס.

    ---

    ## בדיקות לפני שאתה מסיים (חובה)

    - [ ] `grep -P "[\x{1F300}-\x{1FAFF}]|[\x{2600}-\x{27BF}]"` מחזיר 0 תוצאות
    - [ ] `cover-top` מכיל 3 ילדים (logo + thumb + meta)
    - [ ] רק 6 קלאסים `.trade.*` בקובץ ה-CSS (elec, plumb, tile, alum, gen, kitch, frame, finish — סה״כ 8 כי שני האיחודים הם חדשים, אבל הסה״כ ירד מ-10 ל-8)
    - [ ] תקן את הספירה אם עדיין יש 10 — צריך 8
    - [ ] `dashed` נשאר רק ב-`.legal-sigline` וב-`.sig-area`
    - [ ] `.photo` placeholder מציג icon + text, לא diagonal stripes
    - [ ] הקובץ עדיין נטען ומראה 7 עמודי A4 כמו במקור
    - [ ] לא הוספת ספריות JS חיצוניות
    - [ ] לא שינית את ה-color tokens ב-`:root`

    ---

    ## פלט סופי

    - שמור את הקובץ המעודכן בשם **`BrikOps Handover Protocol v2.1.html`**
    - בסוף תכתוב **CHANGELOG קצר** של מה שינית בפועל (סעיף 1 / 2 / 3 / 4 / 5 / A / B), עם ספירת ההחלפות בפועל (לדוגמה: "החלפתי 7 אימוג'ים ל-SVG, איחדתי 4 trade classes ל-2").

    ---

    **הערה אחרונה:** אם משהו בספק הזה לא ברור או סותר את הקובץ הקיים — אל תנחש. ציין את הסתירה ב-CHANGELOG ובחר את הפעולה השמרנית יותר (פחות לשנות).
