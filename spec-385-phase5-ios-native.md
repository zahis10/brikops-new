# #385 Phase 5 — iOS Native Apple Sign-In + App Store Submission

**Status:** Planning — chosen path **B (Native Apple Sign-In)** per Zahi's UX preference.

**Date planned:** 2026-04-18 (session continuation)

## Why this plan exists

Phases 1-4 of #385 are complete — Apple Sign-In works on web and is ready for the Capgo OTA pipeline. The remaining gap is **iOS native app** — it doesn't exist yet as a Capacitor platform. This plan walks from zero-iOS to App Store submission with native Apple Sign-In UX (Face ID / Touch ID sheet instead of web popup).

**Why B over A:** Zahi prioritizes UX quality; web popup feels inferior inside a WebView; native flow is the right long-term investment and also safest against Apple review.

## Current state (verified 2026-04-18)

- `frontend/ios/` — ❌ does not exist
- `frontend/package.json` — ❌ no `@capacitor/ios`, no Apple Sign-In plugin
- Apple Developer App ID `com.brikops.app` — ✅ registered with Sign in with Apple primary
- Apple Services ID `com.brikops.app.signin` — ✅ registered (web flow)
- Backend `APPLE_AUDIENCES` — ✅ accepts both Bundle ID and Services ID
- Frontend web Apple Sign-In — ✅ live (LoginPage.js / OnboardingPage.js via `window.AppleID.auth.init`)
- Xcode on Zahi's Mac — ⚠️ status unknown; likely needs ~10GB download if not installed

## The 6 steps

### Step 1 — Bootstrap iOS platform (Replit)

Replit adds iOS to the Capacitor project:

```bash
cd frontend
yarn add @capacitor/ios
npx cap add ios
npx cap sync ios
```

Artifacts created:
- `frontend/ios/App/App.xcworkspace` (what Zahi opens in Xcode)
- `frontend/ios/App/App.xcodeproj`
- `frontend/ios/App/Podfile` (CocoaPods — for native iOS dependencies)
- `frontend/ios/App/App/Info.plist` (app metadata)
- `frontend/ios/App/App/capacitor.config.json` (mirrored)

**Spec to write for Replit.** ~15 minutes. Ship as a dedicated task.

### Step 2 — Native Apple Sign-In plugin + frontend flow (Replit)

**Plugin choice:** `@capacitor-community/apple-sign-in` (official community plugin, maintained, supports Capacitor 7).

Installation:
```bash
yarn add @capacitor-community/apple-sign-in
npx cap sync ios
```

Frontend code changes in `LoginPage.js` and `OnboardingPage.js`:

```javascript
import { Capacitor } from '@capacitor/core';
import { SignInWithApple } from '@capacitor-community/apple-sign-in';

const handleAppleSignIn = async () => {
  setSocialLoading('apple');
  try {
    let idToken, appleName;

    if (Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'ios') {
      // iOS native flow — opens native Face ID / Touch ID sheet
      const result = await SignInWithApple.authorize({
        clientId: 'com.brikops.app',  // Bundle ID for native
        redirectURI: '',              // empty for native; required param
        scopes: 'email name',
        state: '',
        nonce: crypto.randomUUID(),
      });
      idToken = result.response.identityToken;
      appleName = result.response.givenName
        ? `${result.response.givenName} ${result.response.familyName || ''}`.trim()
        : null;
    } else {
      // Web flow — existing code with Services ID
      const appleServicesId = process.env.REACT_APP_APPLE_SERVICES_ID;
      if (!appleServicesId) {
        toast.error('שירות Apple לא מוגדר');
        setSocialLoading(false);
        return;
      }
      window.AppleID.auth.init({
        clientId: appleServicesId,
        scope: 'name email',
        redirectURI: window.location.origin + '/login',
        usePopup: true,
      });
      const data = await window.AppleID.auth.signIn();
      idToken = data.authorization.id_token;
      appleName = data.user?.name
        ? `${data.user.name.firstName} ${data.user.name.lastName}`.trim()
        : null;
    }

    const response = await onboardingService.socialAuth('apple', idToken, appleName);
    // ... rest unchanged
  } catch (err) {
    // ... existing error handling
  }
};
```

**Key points:**
- Platform detection via `Capacitor.getPlatform()` — zero impact on web users
- Native path uses **Bundle ID** (`com.brikops.app`) as audience — matches our multi-audience backend
- Web path still uses **Services ID** (`com.brikops.app.signin`)
- Backend `/auth/social` endpoint is **unchanged** — it already accepts both audiences (Phase 1 delivered this)
- Name capture: iOS native returns `givenName`/`familyName` separately; web returns `name.firstName`/`name.lastName`
- Android: falls through to web flow; OK for now (Android doesn't need native Apple per Play Store policy)

**Spec to write for Replit.** ~2-3 hours for Replit (code + testing). Ship as separate task.

### Step 3 — Xcode signing & capabilities (Zahi on Mac)

After Replit bootstrap + plugin integration, Zahi opens Xcode:

```bash
cd ~/brikops-new/frontend
open ios/App/App.xcworkspace
```

(Must be `.xcworkspace`, not `.xcodeproj` — CocoaPods requires workspace.)

In Xcode:
1. Left sidebar: click the `App` project root
2. Select **Signing & Capabilities** tab
3. **Team:** select his Apple Developer team (`8FV5CZ886X`)
4. Verify **Bundle Identifier:** `com.brikops.app`
5. Click **+ Capability** → search **Sign in with Apple** → add
6. Xcode auto-syncs provisioning profile with Apple Developer
7. Save

**Prerequisites (Zahi):**
- Xcode installed (Mac App Store, ~10GB)
- macOS recent enough for Xcode version
- Apple Developer Program membership ($99/yr) — ✅ already have

**Time:** 20-30 minutes + Xcode download if missing.

### Step 4 — App Store Connect — create the app listing (Zahi in browser)

Before any build can be uploaded, the app must exist in App Store Connect.

https://appstoreconnect.apple.com → **My Apps** → **+** → **New App**

Form fields:
- **Platform:** iOS
- **Name:** BrikOps
- **Primary Language:** Hebrew (Israel)
- **Bundle ID:** select `com.brikops.app` (appears in dropdown because we registered it)
- **SKU:** `brikops-ios` (internal identifier)
- **User Access:** Full Access

Then, required before App Store submission (but not before TestFlight):
- **App icon** (1024×1024, PNG, no alpha) — use `frontend/play_icon_512.png` as source, upscale to 1024
- **Screenshots** (required sizes):
  - iPhone 6.9" display (1320×2868) — 3 min, 10 max
  - iPhone 6.5" display (1284×2778) — 3 min, 10 max
- **App description** (Hebrew)
- **Keywords** (Hebrew)
- **Category:** Business or Productivity
- **Privacy Policy URL** (mandatory)
- **Support URL**
- **Age rating** questionnaire
- **Privacy practices** questionnaire ("App Privacy" — data collection labels)
- **Sign in with Apple** explicitly listed as login method in app description / metadata

**Time:** 1-2 hours for full metadata; 15 min for the initial app creation (metadata can be completed later).

### Step 5 — Archive + Upload to TestFlight (Zahi in Xcode)

After Step 3 capability + Step 4 listing exist:

1. In Xcode top bar: device selector → **Any iOS Device (arm64)** (NOT a simulator)
2. Menu: **Product → Archive**
3. Wait 5-10 min while Xcode builds release archive
4. **Organizer** window auto-opens → select the new archive
5. **Distribute App** → **App Store Connect** → **Upload**
6. Defaults OK for signing options
7. Upload 5-15 min
8. Build appears in App Store Connect TestFlight tab after 15-60 min processing

**Time:** ~1 hour active work.

### Step 6 — TestFlight testing + App Store review

**Internal Testing (immediate, no Apple review):**
1. App Store Connect → TestFlight → Internal Testing → add Zahi as tester
2. Email → install TestFlight app on iPhone → install BrikOps
3. **Critical test:** trigger Apple Sign-In, verify native sheet appears (Face ID), complete flow, verify backend receives id_token with Bundle ID audience, user lands authenticated

**External Testing (optional, requires Beta App Review ~24h):**
- Up to 100 external testers
- Apple does a lighter review for TestFlight external

**App Store submission:**
1. App Store → **+ Version** → 1.0.0
2. Attach the TestFlight-processed build
3. Complete all metadata from Step 4 if not yet done
4. **Submit for Review**
5. Apple review: 24-48h typical
6. If approved → app is in Store
7. If rejected → read feedback, fix, resubmit (Sign in with Apple issues are common grounds — having native flow minimizes risk)

**Time:** 2-3 days (mostly Apple's review queue).

## Total time budget

| Step | Owner | Active work | Wall time |
|------|-------|-------------|-----------|
| 1. Bootstrap iOS | Replit | 15 min | 15 min |
| 2. Native plugin + frontend | Replit | 2-3 hours | half day |
| 3. Xcode config | Zahi | 30 min | 1 hour (+ Xcode DL) |
| 4. App Store Connect listing | Zahi | 1-2 hours | 2 hours |
| 5. Archive + upload | Zahi | 1 hour | 1 hour |
| 6. TestFlight + review | Apple | - | 2-3 days |

**Active Zahi time:** 4-5 hours spread across 2-3 days.
**Active Replit time:** ~half day (two specs).
**Wall clock to live in App Store:** ~4-5 days assuming Apple review passes first try.

## Open decisions / deferred

- **Provisioning profile strategy:** Automatic vs Manual. Default: Automatic — let Xcode handle.
- **App icon 1024×1024:** Zahi needs to produce this from existing `play_icon_512.png` (upscale or regenerate).
- **Screenshot generation:** Do this on a real device or via Simulator framed screenshots. Recommend using the device he tests on.
- **Privacy policy URL:** Does BrikOps have one at `app.brikops.com/privacy` or similar? If not, create it before submitting.
- **Backend logging:** Add a log line that distinguishes native-audience vs web-audience for analytics — optional nice-to-have.
- **Android native Apple Sign-In:** Out of scope for this phase. Android keeps web flow.

## What NOT to do

- ❌ Don't bootstrap iOS from Zahi's Mac — Replit does it to keep everything in the normal commit flow.
- ❌ Don't commit `frontend/ios/` to git manually — Replit's spec will include a correct `.gitignore` update if needed.
- ❌ Don't change `APPLE_BUNDLE_ID` on backend — it's already set to `com.brikops.app`, same as Xcode will use.
- ❌ Don't skip the native plugin for a "ship it faster" web-only iOS — Apple review history shows they flag non-native Sign in with Apple frequently.
- ❌ Don't submit without Privacy Policy URL — Apple will reject immediately.

## Execution order

The steps depend on each other. Proceed in order:

1. Step 1 (Replit bootstrap) — unblocks Step 2 and Step 3
2. Step 2 (Replit native plugin) — can run in parallel with Zahi doing Step 3 & 4
3. Step 3 (Xcode signing) — requires Step 1 output
4. Step 4 (App Store Connect listing) — can be done anytime after Step 1
5. Step 5 (Archive + upload) — requires Step 2 merged + Step 3 + Step 4
6. Step 6 (TestFlight + review) — requires Step 5 upload processed

## Next immediate action

Write a focused spec for **Step 1 only** (Bootstrap iOS) and send to Replit. Keep Step 2 as a separate spec — don't bundle. Phased delivery reduces risk and lets Zahi run Xcode setup (Step 3) on Step 1's output while Replit works on Step 2.

---

**Document owner:** Zahi + Claude (planning session 2026-04-18)
**Supersedes:** None — new document
**Related specs:**
- `spec-385-sign-in-with-apple.md` (original #385)
- `spec-385-phase2-frontend.md` (Phase 2 completed)
