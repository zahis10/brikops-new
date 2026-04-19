# BrikOps UX Upgrade — Handoff Brief

## מה יש כאן
ביצענו audit מקיף של UX/UI לאפליקציית BrikOps (ציון התחלתי: 5.4/10).
הכנו דוח UX מפורט + 6 ספקים טכניים מוכנים לביצוע ב‑Replit.

## קבצים שחייב לקרוא (בסדר הזה):

### 1. דוח ה‑UX
`ux-opinion-2026-04-16.md` — הדוח המלא בעברית: ציון, ממצאים קריטיים, benchmarks מול מתחרים, תוכנית פעולה 3 פאזות.

### 2. הספקים (בסדר ביצוע):

| # | קובץ | סיכון | שעות | ציון |
|---|---|---|---|---|
| 345 | `spec-345-ux-quick-wins.md` | 🟢 נמוך | ~16h | 5.4→6.8 |
| 346 | `spec-346-polish-pass.md` | 🟢 נמוך | ~50h | 6.8→7.6 |
| 346B | `spec-346B-button-resize.md` | 🟡 בינוני | ~25h | +0.2 |
| 347 | `spec-347-desktop-shell.md` | 🟠 בינוני‑גבוה | ~40h | 7.6→8.0 |
| 348 | `spec-348-dark-mode.md` | 🔴 גבוה | ~50h | 8.0→8.3 |
| 349 | `spec-349-onboarding-activity.md` | 🔴 גבוה | ~25h | 8.3→8.5 |
| 350 | `spec-350-pwa-push.md` | 🔴 גבוה | ~50h | 8.5→8.7 |

### 3. קובץ שאסור לבצע
`spec-347-strategic-upgrades.SUPERSEDED.md` — הגרסה הישנה (לפני הפיצול). נשאר לתיעוד. **אל תבצע אותו.**

## כללי עבודה
- כל ספק כתוב בפורמט: What & Why / Done looks like / Out of scope / Tasks / Relevant files / DO NOT / VERIFY / Risks
- כל ספק מכיל file paths אמיתיים + line numbers מאומתים מתוך `frontend/src/`
- סדר ביצוע: 345 → 346 (+ 346B במקביל) → 347 → 348 → 349 → 350
- **חובה:** merge + QA בין כל ספק. אסור ב‑PR אחד.
- הטכנולוגיה: React 19, Tailwind CSS, shadcn/ui, Radix UI, Lucide icons, Heebo font, RTL Hebrew
- Backend: Python FastAPI, MongoDB Atlas

## התחל מכאן
קרא את `spec-345-ux-quick-wins.md` ובצע אותו. זה 7 tasks פשוטים, סיכון נמוך, impact גבוה.
