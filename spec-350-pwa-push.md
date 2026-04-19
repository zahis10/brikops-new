# #350 — PWA Manifest + Splash + Web Push Notifications (Phase 4 of old #347)

> **שינוי הסקופ (16/04/2026):** הספק המקורי #347 פוצל ל‑4. ספק זה הוא **שלב 4: PWA + Push**. הוא **הספק המסוכן ביותר** מבין הארבעה — דורש תשתית חדשה (VAPID, service worker), שינויים ב‑native build (iOS PWA install flow), ו‑backend infrastructure לשליחת push. צפי ~50 שעות (יותר מהערכה המקורית של 30). **המלץ לבצע עם backend dev מנוסה.**

## What & Why
היום BrikOps דורש מהמשתמש לפתוח את האתר/אפליקציה כדי לראות שיש ליקויים חדשים. **Web Push Notifications** מאפשרות לשלוח התראה אקטיבית למשתמש (גם כשהאפליקציה סגורה) — זה פיצ'ר הליבה של אפליקציות B2B מודרניות. בנוסף, **PWA Manifest + Splash Screens** הופכים את BrikOps לאפליקציה שאפשר "להתקין" מ‑Safari/Chrome עם אייקון על ה‑homescreen, splash screen מקצועי, ו‑standalone mode.

**מציאות iOS:** Apple מאפשרת Web Push **רק** ל‑PWA מותקן (לא ל‑Safari רגיל). זה אומר שהזרימה דורשת: התקנת PWA → אישור הרשאה → קבלת notifications. ב‑Android Chrome זה פועל גם בלי PWA install. צריך להסביר את ההבדל ב‑UI.

## Done looks like
- `manifest.json` מעודכן עם short_name, icons (192, 512, maskable), start_url, display=standalone, theme_color, lang=he, dir=rtl
- אייקונים בגדלים 192×192, 512×512 (קיימים או חדשים)
- iOS apple‑touch‑icon ו‑apple‑touch‑startup‑image עבור 6+ גדלי מכשירים (iPhone SE, 12, 14, 15 Pro Max, iPad)
- Service worker רשום ופועל (Workbox CRA preset)
- VAPID keys generated, public key מוגדר ב‑frontend env, private key ב‑backend env
- אחרי Onboarding Tour (ספק 349), המשתמש רואה prompt לבקשת הרשאת notifications
- Subscription נשמר ב‑DB (`users.push_subscriptions[]`)
- כל פעולה רלוונטית (ליקוי חדש שמשויך, סטטוס שינוי, תזכורת) שולחת push דרך VAPID
- iOS PWA install banner מופיע ב‑Safari iOS עם הסבר ("הוסף למסך הבית")
- אין רגרסיות בספקים 345–349

## Out of scope
- אין Native push (FCM ל‑Capacitor Android / APNs ל‑Capacitor iOS) — Web Push בלבד
- אין notifications email — נשמר ל‑נפרד
- אין SMS notifications
- אין rich push (תמונה גדולה, action buttons מותאמים) — basic title + body + URL בלבד
- אין notifications grouping
- אין preference center מלא (כל ה‑notifications פתוחות אם ה‑permission ניתן)
- אין retry logic מתקדם לשליחת push שנכשל
- אין analytics על delivery rate
- אין offline mode מלא (רק offline cache בסיסי של static assets)

## Phased Execution Within This Spec
ספק זה מחולק ל‑3 תתי‑שלבים. **חובה לבצע sequential.**
- **Phase A** (15h): PWA Manifest + Splash + apple‑touch
- **Phase B** (15h): Service Worker + VAPID setup
- **Phase C** (20h): Backend push sender + frontend permission flow

## Tasks

### PHASE A: PWA Manifest

### Task 1 — `manifest.json` Update
**File:** `frontend/public/manifest.json`

**BEFORE (אם קיים):** וודא מה הקיים:
```bash
cat frontend/public/manifest.json
```

**AFTER:**
```json
{
  "short_name": "BrikOps",
  "name": "BrikOps - ניהול ליקויי בנייה",
  "description": "פלטפורמת ניהול ליקויים, QC ומסירה לקבלנים",
  "icons": [
    {
      "src": "icons/icon-192.png",
      "type": "image/png",
      "sizes": "192x192",
      "purpose": "any"
    },
    {
      "src": "icons/icon-512.png",
      "type": "image/png",
      "sizes": "512x512",
      "purpose": "any"
    },
    {
      "src": "icons/icon-maskable-192.png",
      "type": "image/png",
      "sizes": "192x192",
      "purpose": "maskable"
    },
    {
      "src": "icons/icon-maskable-512.png",
      "type": "image/png",
      "sizes": "512x512",
      "purpose": "maskable"
    }
  ],
  "start_url": "/projects",
  "scope": "/",
  "display": "standalone",
  "orientation": "portrait",
  "theme_color": "#F59E0B",
  "background_color": "#F8FAFC",
  "lang": "he",
  "dir": "rtl",
  "categories": ["business", "productivity"]
}
```

### Task 2 — אייקונים בגדלים נדרשים
**Files:** `frontend/public/icons/`

נדרשים האייקונים הבאים (יש או צריך לייצר):
- `icon-192.png` (192×192, square)
- `icon-512.png` (512×512, square)
- `icon-maskable-192.png` (192×192 עם safe area של 80% במרכז)
- `icon-maskable-512.png` (512×512 maskable)

**אם האייקונים לא קיימים:** המנהל המוצר/דיזיינר חייב לספק אותם. **אסור** לייצר אותם בקוד — זה עבודת design.

**Validation:**
```bash
ls -la frontend/public/icons/
```

### Task 3 — Apple Touch Icons + Splash
**File:** `frontend/public/index.html` (או template equivalent)

הוסף ב‑`<head>`:
```html
<!-- Apple Touch Icons -->
<link rel="apple-touch-icon" href="%PUBLIC_URL%/icons/icon-192.png" />
<link rel="apple-touch-icon" sizes="152x152" href="%PUBLIC_URL%/icons/icon-152.png" />
<link rel="apple-touch-icon" sizes="180x180" href="%PUBLIC_URL%/icons/icon-180.png" />

<!-- Apple PWA Meta -->
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<meta name="apple-mobile-web-app-title" content="BrikOps" />

<!-- Splash Screens (iOS) -->
<!-- iPhone 15 Pro Max: 1290x2796 -->
<link rel="apple-touch-startup-image"
      href="%PUBLIC_URL%/splash/iphone-15-pro-max.png"
      media="(device-width: 430px) and (device-height: 932px) and (-webkit-device-pixel-ratio: 3) and (orientation: portrait)" />

<!-- iPhone 14 Pro: 1179x2556 -->
<link rel="apple-touch-startup-image"
      href="%PUBLIC_URL%/splash/iphone-14-pro.png"
      media="(device-width: 393px) and (device-height: 852px) and (-webkit-device-pixel-ratio: 3) and (orientation: portrait)" />

<!-- iPhone 14: 1170x2532 -->
<link rel="apple-touch-startup-image"
      href="%PUBLIC_URL%/splash/iphone-14.png"
      media="(device-width: 390px) and (device-height: 844px) and (-webkit-device-pixel-ratio: 3) and (orientation: portrait)" />

<!-- iPhone SE 3rd gen: 750x1334 -->
<link rel="apple-touch-startup-image"
      href="%PUBLIC_URL%/splash/iphone-se.png"
      media="(device-width: 375px) and (device-height: 667px) and (-webkit-device-pixel-ratio: 2) and (orientation: portrait)" />

<!-- iPad Pro 12.9": 2048x2732 -->
<link rel="apple-touch-startup-image"
      href="%PUBLIC_URL%/splash/ipad-pro-12.png"
      media="(device-width: 1024px) and (device-height: 1366px) and (-webkit-device-pixel-ratio: 2) and (orientation: portrait)" />
```

**Splash images לייצור (Designer task):**
- iPhone 15 Pro Max: 1290×2796
- iPhone 14 Pro: 1179×2556
- iPhone 14: 1170×2532
- iPhone SE 3: 750×1334
- iPad Pro 12.9": 2048×2732
- iPad Air: 1640×2360

**עיצוב splash:** רקע `#F8FAFC` (slate‑50), לוגו BrikOps במרכז ב‑amber‑500, גודל לוגו ~40% ממימדי המסך הקטן.

### Task 4 — Test PWA Install (Android Chrome)
1. הרץ `npm run build`
2. שרת מ‑`build/` ב‑HTTPS (חובה — service worker דורש HTTPS)
3. פתח באנדרואיד Chrome
4. תפריט → "התקן אפליקציה" → אייקון נוסף ל‑homescreen
5. פתח מהאייקון → רץ ב‑standalone (ללא URL bar)
6. theme color הצבע של ה‑status bar צבעוני (amber)

### Task 5 — Test PWA Install (iOS Safari)
1. iOS Safari → הוסף "Add to Home Screen"
2. אייקון נוסף ל‑homescreen
3. פתח → splash screen מופיע (לפי מימדי המכשיר)
4. רץ ב‑standalone

---

### PHASE B: Service Worker + VAPID

### Task 6 — Service Worker Registration
**File:** `frontend/src/index.js` (או equivalent — הקובץ שמרנדר את App)

CRA יצר service worker template ב‑`frontend/src/serviceWorker.js` או `frontend/src/serviceWorkerRegistration.js`. ודא רישום:
```jsx
import * as serviceWorkerRegistration from './serviceWorkerRegistration';
// בסוף הקובץ:
serviceWorkerRegistration.register();
```

**אם משתמש ב‑Workbox מ‑CRA 5+:**
**File:** `frontend/src/service-worker.js` (custom service worker)
```js
/* eslint-disable no-restricted-globals */
import { precacheAndRoute } from 'workbox-precaching';

precacheAndRoute(self.__WB_MANIFEST);

self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data.json(); } catch (e) {}
  const title = data.title || 'התראה מ-BrikOps';
  const options = {
    body: data.body || '',
    icon: '/icons/icon-192.png',
    badge: '/icons/badge-72.png',
    dir: 'rtl',
    lang: 'he',
    data: data.url ? { url: data.url } : {},
    tag: data.tag || 'brikops-default',
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/projects';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if (c.url.includes(url) && 'focus' in c) return c.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
```

### Task 7 — VAPID Keys Generation
ב‑terminal של backend dev:
```bash
npm install -g web-push
web-push generate-vapid-keys
```

תקבל:
```
=======================================
Public Key:
BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U

Private Key:
UUxI4O8-FbRouAevSmBQ6o18hgE4nSG3qwvJTfKc-ls
=======================================
```

**שמור:**
- Public key → frontend `.env` כ‑`REACT_APP_VAPID_PUBLIC_KEY`
- Private key → backend `.env` כ‑`VAPID_PRIVATE_KEY` (סוד! never commit)
- Subject → backend `.env` כ‑`VAPID_SUBJECT=mailto:zahis10@gmail.com`

### Task 8 — Backend: Push Send Infrastructure
**File:** `backend/contractor_ops/push_service.py` (חדש)

```python
import os
import json
from pywebpush import webpush, WebPushException

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_CLAIMS = {"sub": os.getenv("VAPID_SUBJECT", "mailto:admin@brikops.com")}

async def send_push_to_user(user_doc, payload: dict):
    """Send push notification to all subscriptions of a user."""
    subs = user_doc.get("push_subscriptions", [])
    if not subs:
        return {"sent": 0}

    sent = 0
    failed = []
    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS.copy(),
            )
            sent += 1
        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                # Subscription expired — mark for cleanup
                failed.append(sub.get("endpoint"))
            else:
                # Log other errors
                print(f"Push failed: {e}")

    # Cleanup stale subscriptions
    if failed:
        await users_collection.update_one(
            {"_id": user_doc["_id"]},
            {"$pull": {"push_subscriptions": {"endpoint": {"$in": failed}}}}
        )

    return {"sent": sent, "failed": len(failed)}
```

**File:** `backend/requirements.txt`
```
pywebpush>=2.0.0
```

### Task 9 — Backend: Subscribe Endpoint
**File:** `backend/contractor_ops/users_router.py`

```python
from pydantic import BaseModel

class PushSubscription(BaseModel):
    endpoint: str
    keys: dict  # { "p256dh": "...", "auth": "..." }

@router.post("/me/push-subscribe")
async def push_subscribe(sub: PushSubscription, user = Depends(get_current_user)):
    """Save a push subscription for the current user."""
    sub_dict = sub.dict()
    # Avoid duplicates
    await users_collection.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$pull": {"push_subscriptions": {"endpoint": sub_dict["endpoint"]}}}
    )
    await users_collection.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$push": {"push_subscriptions": sub_dict}}
    )
    return {"ok": True}

@router.delete("/me/push-unsubscribe")
async def push_unsubscribe(endpoint: str, user = Depends(get_current_user)):
    """Remove a push subscription by endpoint."""
    await users_collection.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$pull": {"push_subscriptions": {"endpoint": endpoint}}}
    )
    return {"ok": True}
```

### Task 10 — Backend: Trigger Pushes
מצא את הנקודה ב‑backend שבה משתנה סטטוס של task / נוצר ליקוי / משויך משתמש:
```bash
grep -rn "task.status\|task_assigned\|defect_created" backend/contractor_ops/ | head -10
```

הוסף קריאה לפונקציה:
```python
from .push_service import send_push_to_user

# בתוך task_assigned logic:
await send_push_to_user(assigned_user, {
    "title": "ליקוי חדש שויך אליך",
    "body": f"{task['title']} — בנייה {building_name}, דירה {unit_label}",
    "url": f"/tasks/{task['_id']}",
    "tag": f"task-{task['_id']}"
})
```

**אסור** להעמיס push על כל update — רק על:
- ליקוי חדש שויך למשתמש
- ליקוי שלי עבר לסטטוס "בביצוע"
- ליקוי שלי עבר לסטטוס "סגור"
- תזכורת על ליקוי overdue

### PHASE C: Frontend Permission Flow

### Task 11 — Frontend: Push Permission Service
**File חדש:** `frontend/src/services/pushNotifications.js`

```js
const VAPID_PUBLIC_KEY = process.env.REACT_APP_VAPID_PUBLIC_KEY;

const urlBase64ToUint8Array = (base64String) => {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
};

export const isPushSupported = () => {
  return 'Notification' in window
    && 'serviceWorker' in navigator
    && 'PushManager' in window;
};

export const isIosPwaInstalled = () => {
  return ('standalone' in navigator && navigator.standalone)
    || window.matchMedia('(display-mode: standalone)').matches;
};

export const isIosSafariNotInstalled = () => {
  const ua = navigator.userAgent;
  const isIos = /iPhone|iPad|iPod/.test(ua) && !window.MSStream;
  return isIos && !isIosPwaInstalled();
};

export const requestPushPermission = async (api) => {
  if (!isPushSupported()) {
    if (isIosSafariNotInstalled()) {
      // iOS Safari without PWA install
      return { granted: false, reason: 'ios-not-installed' };
    }
    return { granted: false, reason: 'unsupported' };
  }

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    return { granted: false, reason: 'denied' };
  }

  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
    });
    await api.post('/me/push-subscribe', sub.toJSON());
    return { granted: true };
  } catch (e) {
    console.error('Push subscribe failed', e);
    return { granted: false, reason: 'subscribe-failed', error: e };
  }
};
```

### Task 12 — UI: Push Permission Prompt
**File חדש:** `frontend/src/components/PushPermissionBanner.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import { Bell, X, Smartphone } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { requestPushPermission, isIosSafariNotInstalled } from '../services/pushNotifications';
import api from '../services/api';

const PushPermissionBanner = () => {
  const { user } = useAuth();
  const [dismissed, setDismissed] = useState(() => {
    return localStorage.getItem('push-banner-dismissed') === 'true';
  });
  const [iosHint, setIosHint] = useState(false);

  // Show banner only:
  // 1. Logged in
  // 2. Onboarding completed (don't pile prompts)
  // 3. Not dismissed
  // 4. Permission still 'default' (not yet asked)
  if (!user || !user.onboarding_completed || dismissed) return null;
  if (typeof Notification !== 'undefined' && Notification.permission !== 'default') return null;

  const handleEnable = async () => {
    if (isIosSafariNotInstalled()) {
      setIosHint(true);
      return;
    }
    const result = await requestPushPermission(api);
    if (result.granted) {
      setDismissed(true);
      localStorage.setItem('push-banner-dismissed', 'true');
    }
  };

  const handleDismiss = () => {
    setDismissed(true);
    localStorage.setItem('push-banner-dismissed', 'true');
  };

  if (iosHint) {
    return (
      <div className="bg-blue-50 dark:bg-blue-950 border-b border-blue-200 dark:border-blue-900 px-4 py-3 flex items-start gap-3" dir="rtl">
        <Smartphone className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1 text-sm">
          <p className="font-medium text-slate-900 dark:text-slate-100">להתראות ב‑iPhone — צריך להתקין את האפליקציה תחילה</p>
          <p className="text-slate-600 dark:text-slate-400 text-xs mt-1">לחץ על Share ב‑Safari → "הוסף למסך הבית"</p>
        </div>
        <button onClick={handleDismiss} className="text-slate-400">
          <X className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="bg-amber-50 dark:bg-amber-950 border-b border-amber-200 dark:border-amber-900 px-4 py-3 flex items-center gap-3" dir="rtl">
      <Bell className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0" />
      <p className="flex-1 text-sm text-slate-900 dark:text-slate-100">
        קבל התראות מיידיות על ליקויים שמשויכים אליך
      </p>
      <button
        onClick={handleEnable}
        className="bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors"
      >
        הפעל
      </button>
      <button onClick={handleDismiss} className="text-slate-400">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};

export default PushPermissionBanner;
```

**File:** `frontend/src/App.js` — הוסף את ה‑banner למעלה:
```jsx
import PushPermissionBanner from './components/PushPermissionBanner';

// אחרי TrialBanner:
<PushPermissionBanner />
```

## Relevant files

### חדשים
- `frontend/src/services/pushNotifications.js`
- `frontend/src/components/PushPermissionBanner.jsx`
- `frontend/src/service-worker.js` (אם custom Workbox)
- `backend/contractor_ops/push_service.py`

### עריכה
- `frontend/public/manifest.json` (full overhaul)
- `frontend/public/index.html` (apple meta + splash links)
- `frontend/public/icons/*.png` (אייקונים חדשים — design asset)
- `frontend/public/splash/*.png` (splash images — design asset)
- `frontend/src/index.js` (service worker register)
- `frontend/src/App.js` (mount PushPermissionBanner)
- `frontend/.env.example` (REACT_APP_VAPID_PUBLIC_KEY)
- `backend/contractor_ops/users_router.py` (push subscribe/unsubscribe endpoints)
- `backend/contractor_ops/...` (קוד קיים שיוצר tasks / משייך — הוספת קריאה ל‑send_push)
- `backend/requirements.txt` (+pywebpush)
- `backend/.env.example` (VAPID_PRIVATE_KEY, VAPID_SUBJECT)

## DO NOT
- ❌ אל תכנס ל‑Native push (FCM/APNs) — ספק אחר
- ❌ אל תוסיף email notifications
- ❌ אל תוסיף SMS
- ❌ אל תיצור preference center מלא
- ❌ אל תיצור rich push (תמונות גדולות, action buttons מותאמים)
- ❌ אל תשמור push private key ב‑git או בקוד
- ❌ אל תשלח push בכל update — רק 4 ה‑events שצוינו ב‑Task 10
- ❌ אל תפעיל push prompt לפני שהמשתמש סיים onboarding
- ❌ אל תפעיל push prompt בכל refresh — בדוק `Notification.permission !== 'default'`
- ❌ אל תיצור אייקונים בקוד — זה עבודת design
- ❌ אל תיגע ב‑existing notifications (NotificationBell.js, in‑app)
- ❌ אל תוסיף analytics ב‑backend על delivery — תוסיף ב‑ספק עתידי
- ❌ אל תיצור splash images עם canvas או SVG inline — צריך PNG אמיתי
- ❌ אל תפצל subscriptions per‑device בלי פתרון לתעוד אילו אייקונים — אם משתמש מתקין ב‑3 מכשירים, יש 3 subscriptions באותו array

## VERIFY

### Phase A — Manifest
1. DevTools → Application → Manifest → רואה את כל השדות החדשים
2. Lighthouse → PWA score ≥90 (תלוי באייקונים — בדוק שיש את כולם)
3. Install prompt: Chrome desktop → menu → Install BrikOps
4. אייקון על desktop נראה תקין (לא placeholder ריק)

### Phase A — iOS Splash
5. iOS Safari → Add to Home Screen → אייקון נראה תקין
6. לחיצה על אייקון → splash screen מופיע (לפי מימדי המכשיר)
7. אחרי splash → app נטענת ב‑standalone

### Phase B — Service Worker
8. DevTools → Application → Service Workers → רשום ופועל
9. DevTools → Application → Cache Storage → מכיל precached assets
10. Offline mode → רענן → static UI נטען (offline cache)

### Phase B — VAPID
11. תיקון: הרץ `web-push generate-vapid-keys` במקומי
12. ודא ש‑keys ב‑env (frontend + backend)
13. אין committed secrets ב‑git

### Phase C — Permission Flow
14. logged in + onboarding_complete=true + permission=default → רואה PushPermissionBanner
15. לחץ "הפעל" → browser prompt → אישור → POST /me/push-subscribe (בדוק Network)
16. בדוק ב‑MongoDB: `users.findOne({_id: ...}).push_subscriptions` → array עם 1 item
17. סגור banner → localStorage `push-banner-dismissed=true` → לא רואה שוב
18. iOS Safari (לא PWA installed) → לחץ "הפעל" → רואה הסבר על "הוסף למסך הבית"

### Phase C — Push Delivery
19. שייך task למשתמש בעל subscription → push מגיע למכשיר
20. לחץ על notification → נפתחת BrikOps בעמוד /tasks/:id
21. אם user מסיר את ה‑permission ב‑browser → push בא נכשל → DB מתנקה אוטומטית מה‑subscription
22. notification בעברית עם dir=rtl

### Cross‑platform
23. Android Chrome — הכל פועל
24. iOS Safari (PWA installed) — הכל פועל (iOS 16.4+)
25. iOS Safari (not installed) — banner מציג הסבר
26. Desktop Chrome — push פועל
27. Desktop Safari — push פועל (macOS 13+)

## Risks
- **גבוה: VAPID secret leak** — אם private key מודלף, מישהו יכול לשלוח push למשתמשים שלך. חובה ב‑secret manager (AWS Secrets, GCP Secret Manager, Replit Secrets). אסור ב‑repo.
- **גבוה: iOS PWA install rate נמוך** — מחקרים מראים שרק 5–15% מהמשתמשים מתקינים PWA. אם זה ה‑target הראשי שלך, הספק נותן ערך מוגבל. שקול אם שווה לבצע לפני שיש מטריקות התקנה.
- **גבוה: Push delivery rate** — Push notifications נכשלים ב‑10–30% מהמקרים מסיבות שונות (battery saver, DnD, expired subscription, browser dropped). לא להבטיח delivery.
- **גבוה: Service Worker debugging** — בעיות SW קשות לדבג. אם SW caches גרסה ישנה ולא מתעדכן, משתמשים תקועים עם UI ישן. חובה לבחון update strategy.
- **בינוני: GDPR / Privacy** — Push subscriptions הם PII (endpoint URL מזהה מכשיר). וודא שב‑Privacy Policy מצוין שאתה אוסף.
- **בינוני: Notification spam** — אם הצוות שלך מטריגר 50 push בשעה למשתמש, הוא יבטל את ה‑permission תוך יום. הגבל ל‑4 events המוצדקים.
- **בינוני: pywebpush + python async** — `webpush()` הוא sync. בקריאה מ‑async route, עוטף ב‑`run_in_executor` או הופך ל‑background task כדי לא לחסום.
- **נמוך: VAPID key rotation** — אם מחליפים keys, כל ה‑subscriptions הקיימים נשברים. תכנן rotation strategy עם migration.

## Rollback Plan
אם משהו שובר במהלך rollout:

**Phase A (manifest):** revert ל‑manifest הישן. אייקונים חדשים נשארים אבל לא בשימוש.

**Phase B (service worker):** השאיר את הקוד אבל אל תקרא ל‑`serviceWorkerRegistration.register()`. SW קיים ב‑browser cache — צריך unregister:
```js
navigator.serviceWorker.getRegistrations().then(rs => rs.forEach(r => r.unregister()));
```
שלח email למשתמשים הקיימים שיעשו hard refresh.

**Phase C (push flow):** הסר את `<PushPermissionBanner />` מ‑App.js. ה‑backend endpoints נשארים אבל לא נקראים.

---

**זמן עבודה משוער:** ~50 שעות (15A + 15B + 20C + design assets בנפרד)
**תוצאה צפויה:** ציון UX יעלה מ‑8.5 ל‑8.7
**תלות:** ספקים 345–349 חייבים להיות merged. תלות חיצונית: design assets (אייקונים + splash images)
**תלות ב‑backend dev:** קריטי. אסור לבצע ללא backend dev שמכיר את המערכת.
**זמן QA אחרי merge:** 2–3 ימים על iOS / Android / Desktop
**הערה אסטרטגית:** הספק הזה דורש החלטה מוצרית — האם push ב‑iOS PWA הוא ROI חיובי, או שעדיף להשקיע 50 שעות באפליקציית native אמיתית עם FCM/APNs (יותר אמין). שווה לבדוק יחסי המשתמשים iOS vs Android לפני שיצא לדרך.
