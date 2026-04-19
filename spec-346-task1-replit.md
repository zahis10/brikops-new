# Spec #346 Task 1 — Typography scale ב-tailwind.config.js

## What & Why
מתחילים את ספק 346 (Polish Pass). Task 1 הוא הוספת סקאלת fontSize אחידה ל-Tailwind config. זה additive only — לא מוחק כלום, לא משנה כלום בקבצים אחרים. זה התשתית ל-Tasks הבאים שישתמשו ב-`text-title`, `text-display` וכו'.

## File: `frontend/tailwind.config.js`

הוסף `fontSize` בתוך `theme.extend` (אחרי `colors`, לפני `keyframes`):

```js
fontSize: {
  // BrikOps unified type scale
  'caption': ['12px', { lineHeight: '16px', letterSpacing: '0.01em' }],
  'body-sm': ['14px', { lineHeight: '20px' }],
  'body':    ['16px', { lineHeight: '24px' }],
  'subhead': ['18px', { lineHeight: '26px', fontWeight: '600' }],
  'title':   ['24px', { lineHeight: '32px', fontWeight: '700' }],
  'display': ['32px', { lineHeight: '40px', fontWeight: '700', letterSpacing: '-0.01em' }],
},
```

ה-config הסופי של `theme.extend` צריך להיראות ככה (החלק הרלוונטי בלבד):

```js
extend: {
  borderRadius: { ... },
  colors: { ... },
  fontSize: {
    'caption': ['12px', { lineHeight: '16px', letterSpacing: '0.01em' }],
    'body-sm': ['14px', { lineHeight: '20px' }],
    'body':    ['16px', { lineHeight: '24px' }],
    'subhead': ['18px', { lineHeight: '26px', fontWeight: '600' }],
    'title':   ['24px', { lineHeight: '32px', fontWeight: '700' }],
    'display': ['32px', { lineHeight: '40px', fontWeight: '700', letterSpacing: '-0.01em' }],
  },
  keyframes: { ... },
  animation: { ... }
}
```

## DO NOT
- ❌ אל תמחק / תשנה את `text-xs`, `text-sm`, `text-base`, `text-2xl` של Tailwind ה-default — הם נשארים. הסקאלה החדשה היא **תוספת בלבד**.
- ❌ אל תיגע באף קובץ אחר. זה Task של config-only.
- ❌ אל תיגע ב-`borderRadius`, `colors`, `keyframes`, `animation` או `plugins`.
- ❌ אל תוסיף תלויות חדשות.
- ❌ אל תשנה את `darkMode` או `content`.

## VERIFY
1. `git diff frontend/tailwind.config.js` — צריך להציג רק תוספת של block `fontSize` בתוך `extend`. אפס שורות נמחקות, אפס שינויים בקבצים אחרים.
2. הרץ build: `cd frontend && npm run build` — חייב לעבור בלי warning/error חדש.
3. בדוק ש-`text-display` ו-`text-title` נמצאים בפלט: `grep -E "\.text-(display|title|subhead|caption|body|body-sm)" frontend/build/static/css/*.css | head -5` — צריך להראות תוצאות (ה-CSS נוצר רק אם class בשימוש בפועל; אם הקבצים עדיין לא משתמשים, זה צפוי שלא יראה — לא error).

## Risks
🟢 נמוך מאוד. Config-only, additive. אם משהו נשבר ב-build → revert מיידי, סימן שהפורמט לא תואם לגרסת Tailwind.
