# #417 — Auth expiry UX — axios 401 interceptor + auto-logout

## What & Why

**The problem (from closed-beta testing):** When a user's JWT token expires mid-session, every subsequent API call returns 401, but nothing in the frontend catches this globally. The result is a confusing cascade of UI failures: "שגיאה בטעינת פרטי דירה" / "דירה לא נמצאה" / "אין ליקויים בפרויקט" — all because the data fetch failed with 401, not because the data is actually missing. The user has no idea they're logged out, panics, and thinks something broke. Only after manually clicking "התנתקות" and logging back in does the app behave normally.

**The fix:** When any API call returns 401 from a non-auth endpoint while the user has a token, automatically:
1. Clear the token (via existing `logout()` in AuthContext).
2. Show a toast: "החיבור פג, אנא התחבר מחדש".
3. Redirect to `/login`.

**Why this is careful:** The codebase already has strict guidance about where auth handling lives:
- `api.js` line 47-50: "Do NOT add 401 handling here. Auth errors are handled in AuthContext.fetchCurrentUser. Adding token cleanup here would bypass the network error resilience logic. See #171."
- `AuthContext.fetchCurrentUser` (line 94-103) ALREADY handles 401/403 on `/auth/me` during app startup — it clears token + user, and the app re-renders to the login flow.

This spec adds one NEW interceptor inside `AuthContext` that covers the **mid-session** case: 401 on business endpoints (not `/auth/me`, not login/register/otp endpoints) AFTER the user is authenticated.

**Architectural constraint:** `AuthProvider` is rendered OUTSIDE `BrowserRouter` (App.js:520 wraps `BrowserRouter` at 523). So we cannot call `useNavigate()` inside `AuthContext`. We use `window.location.href = '/login'` instead, which:
- Works anywhere (no router context needed)
- Does a full page reload — GUARANTEES all component state is reset cleanly (safer than trying to reset state piece-by-piece after a session ends)
- Is the right semantic for "your session ended, start fresh"
- Is only hit on rare token-expiry events — perf is not a concern

---

## Done looks like

### Happy path — token expires mid-session

1. User is logged in, using the app normally.
2. Token expires (e.g., after 24 hours or manually invalidated on the server).
3. User clicks any action that triggers an API call (open project, view unit, load tasks, etc.).
4. ✅ Within 1-2 seconds, a toast appears: "החיבור פג, אנא התחבר מחדש".
5. ✅ User is redirected to `/login` via full page reload.
6. ✅ localStorage `token` is cleared.
7. ✅ Cookie `brikops_logged_in` is cleared.
8. User logs back in → ends up on `/` (home) with fresh state.

### Regressions (MUST NOT BREAK)

1. ✅ Failed login attempts (wrong password) return 401 from `/auth/login` but do NOT trigger the auto-logout flow. The login page shows its own error. User stays on login.
2. ✅ Failed OTP verification returns 401 from OTP endpoints but does NOT trigger auto-logout. User stays on OTP screen.
3. ✅ App startup with an expired token still handled cleanly by the existing `fetchCurrentUser` logic on `/auth/me` — the new interceptor does NOT double-fire because `/auth/me` is also excluded.
4. ✅ Pending-deletion users (403) still handled by the existing interceptor at AuthContext.js:62-75 — the new interceptor is for 401 only, doesn't touch 403.
5. ✅ Network errors (no response, timeouts) are NOT mistaken for auth errors — they don't have `error.response?.status`.
6. ✅ Multiple concurrent 401s (e.g., 5 parallel API calls all fail) trigger the flow EXACTLY ONCE — no spam of toasts, no double-logout.
7. ✅ Users without a token (pre-login) hitting a 401 do NOT trigger the "session expired" flow — no token means there's no session to expire.
8. ✅ `api.js`'s primary response interceptor (lines 37-68) is UNTOUCHED per the #171 guidance.
9. ✅ The existing `pending_deletion` interceptor (AuthContext.js:62-75) is UNTOUCHED.
10. ✅ `fetchCurrentUser`'s auth error handling (AuthContext.js:94-103) is UNTOUCHED.

---

## Out of scope

- ❌ Any change to `services/api.js` — respects the #171 guidance explicitly stated in code.
- ❌ Any change to `fetchCurrentUser` or its retry logic — existing network resilience stays exactly as-is.
- ❌ Any change to the `logout` function's body — we call it, don't modify it.
- ❌ Any change to how the login page renders errors on failed login.
- ❌ Restoring the user to the page they were on before expiry (e.g., `?returnTo=/projects/X`) — nice-to-have, not in this patch. `/` home is fine.
- ❌ Refresh-token flow (obtaining a new token without logging out) — separate, bigger feature.
- ❌ Any backend change.
- ❌ Any new npm dependency.
- ❌ Any change to `AuthContext`'s exported value (`{ user, token, login, logout, ... }`) — we add internal behavior, not new public API.

---

## Tasks

### Task 1 — Add a 401 interceptor inside AuthProvider

**File:** `frontend/src/contexts/AuthContext.js`

**Location:** Add a NEW `useEffect` **immediately after** the existing `pending_deletion` interceptor effect at lines 62-75. The new effect follows the exact same registration/cleanup pattern.

**Find with:** `grep -n "pending_deletion" frontend/src/contexts/AuthContext.js`

**STEP 0 — INVESTIGATE FIRST:**

Before writing the interceptor, verify these assumptions by running:

```bash
# (a) Confirm the list of auth endpoints we must skip:
grep -rn "/auth/" frontend/src/services/api.js frontend/src/contexts/AuthContext.js | grep -v "test" | head -30
```

Report the exact endpoint paths you find (e.g., `/auth/login`, `/auth/register`, `/auth/me`, `/auth/otp-request`, `/auth/otp-verify`, `/auth/logout`, etc.). The spec below uses a prefix-match approach (`url.includes('/auth/')`) that covers all of them, but verify no business endpoint accidentally starts with `/auth/` (it shouldn't, but double-check).

**Add the new effect:**

Place this code immediately after the closing brace of the existing `pending_deletion` useEffect (after line ~75):

```js
  // Global 401 handler for mid-session token expiry.
  //
  // Fires when ANY API call returns 401 on a non-auth endpoint while the user
  // has a token. Clears the token, notifies the user, and redirects to /login.
  //
  // Why this lives here (not in api.js):
  //   See the comment in services/api.js line 47-50 — auth handling must
  //   stay in AuthContext to avoid breaking the network-error resilience
  //   logic in fetchCurrentUser.
  //
  // Why full-page reload (window.location.href):
  //   AuthProvider is rendered OUTSIDE BrowserRouter (App.js:520), so we
  //   can't use useNavigate() here. Full reload also guarantees clean
  //   state after session end — safer than trying to reset piece-by-piece.
  //
  // Debounce:
  //   If 5 concurrent API calls all return 401, we only want to fire the
  //   flow once. The ref guards against double-firing within a short window.
  useEffect(() => {
    const interceptorId = axios.interceptors.response.use(undefined, (error) => {
      try {
        const status = error?.response?.status;
        if (status !== 401) return Promise.reject(error);

        // Skip auth endpoints — failed login/OTP/register/logout legitimately return 401.
        const url = error.config?.url || '';
        if (url.includes('/auth/')) return Promise.reject(error);

        // Skip if user has no token — no session to expire.
        const currentToken = localStorage.getItem('token');
        if (!currentToken) return Promise.reject(error);

        // Debounce: fire once per expiry event.
        if (sessionExpiredRef.current) return Promise.reject(error);
        sessionExpiredRef.current = true;

        // Clear session state (without triggering another logout-related re-render).
        setToken(null);
        setUser(null);
        setNetworkError(false);
        localStorage.removeItem('token');
        _clearBrikopsCookie();

        // Notify and redirect.
        toast.info('החיבור פג, אנא התחבר מחדש');
        // 1500ms gives the user enough time to actually READ the Hebrew toast
        // before the page reloads. Concurrent 401s during this window are
        // caught by the sessionExpiredRef debounce above (they Promise.reject
        // without re-triggering the flow — API calls to backend still fire,
        // but are harmless 401 responses).
        setTimeout(() => {
          window.location.href = '/login';
        }, 1500);
      } catch (e) {
        console.warn('[AUTH] 401 interceptor failure', e);
      }
      return Promise.reject(error);
    });
    return () => axios.interceptors.response.eject(interceptorId);
  }, []);
```

**Add the debounce ref** near the other refs (around line 53-54, next to `retryTimerRef` and `toastShownRef`):

```js
  const sessionExpiredRef = useRef(false);
```

**Why this pattern:**
- The ref persists across re-renders so concurrent 401s see `true` after the first one fires.
- Using `setToken(null)` directly (instead of calling `logout()`) avoids any chance of double state updates or the logout function being stale via closure. The state cleanup matches what `logout()` does, just inlined for clarity and isolation.
- `setTimeout` with 1500ms gives the user enough time to READ the Hebrew toast ("החיבור פג, אנא התחבר מחדש") before the page reloads. 150ms would be too fast — the user would miss it. Concurrent 401s during this window hit the `sessionExpiredRef` debounce and Promise.reject without re-triggering the flow.
- Full `window.location.href` assignment triggers a hard navigation — all component state is gone, the app re-mounts, user sees `/login` with a clean slate.

**Do NOT:**
- ❌ Do NOT call `logout()` directly inside the interceptor — it's defined later in the same component (line 191) and referencing it here creates a temporal-dead-zone risk plus closure-staleness risk. Inline the 4 state setters + localStorage + cookie clear.
- ❌ Do NOT add dependencies to the `useEffect`'s dep array — the interceptor should be registered ONCE on mount, and reading the latest token via `localStorage.getItem('token')` inside the handler avoids the re-registration-on-state-change churn.
- ❌ Do NOT use a state variable (e.g., `sessionExpired`) for the debounce — `useRef` is correct here because it doesn't trigger re-renders and persists across renders.
- ❌ Do NOT touch the existing `pending_deletion` interceptor — keep it as-is, add the new one separately.
- ❌ Do NOT reset `sessionExpiredRef.current` back to `false` — after the redirect, the component unmounts and the ref is gone. A new session gets a fresh component instance with `useRef(false)`.
- ❌ Do NOT call `eject` outside the cleanup — the cleanup function returns from the useEffect correctly.

---

## Relevant files

### Modified:
- `frontend/src/contexts/AuthContext.js` — imports unchanged (`axios`, `toast`, `useRef` all already imported); add `sessionExpiredRef` near other refs; add new useEffect registering 401 interceptor.

### Untouched (CRITICAL):
- `frontend/src/services/api.js` — zero diff. Respects the #171 guidance.
- `frontend/src/App.js` — zero diff. Router structure untouched.
- `frontend/src/pages/LoginPage.js` — zero diff. Login page's own error handling unchanged.
- Any other file — zero diff.
- All Batch 2b files (`features.js`, `defectDraft.js`, `categoryBuckets.js`, `GroupedSelectField.js`) — zero diff.
- Backend — zero diff.
- Package files — zero diff.

---

## DO NOT

- ❌ Do NOT modify `services/api.js` interceptor. The #171 comment is explicit — follow it.
- ❌ Do NOT call `logout()` inside the interceptor (closure/TDZ risk). Inline the state resets.
- ❌ Do NOT add the interceptor outside AuthProvider. It needs access to `setToken` / `setUser` / `setNetworkError`, which only exist in this component.
- ❌ Do NOT use `useNavigate()` — AuthProvider is outside `<BrowserRouter>`.
- ❌ Do NOT skip the auth-endpoint guard — failed login/OTP would trigger a bogus "session expired" flow.
- ❌ Do NOT skip the token guard — a user on the login page hitting an unrelated 401 shouldn't see a "session expired" toast.
- ❌ Do NOT skip the debounce ref — concurrent 401s would spam the user with multiple toasts.
- ❌ Do NOT change the toast library — use `toast.info` from the already-imported Sonner. No new dependencies.
- ❌ Do NOT add a `returnTo` query param on the redirect — out of scope. User lands on `/login`, then on home.
- ❌ Do NOT handle 403. Pending_deletion is already handled separately at line 62-75. Other 403s (forbidden, not auth-expired) should not auto-logout.
- ❌ Do NOT add a ref reset. After full page reload the component is gone — the next session starts fresh.
- ❌ Do NOT feature-flag this change. It's a pure UX fix with no regression risk when the behavior is otherwise correct. If something goes wrong we revert, not toggle.
- ❌ Do NOT modify `fetchCurrentUser`. Its existing auth-error logic handles startup; our interceptor handles mid-session.

---

## VERIFY before commit

### 1. Grep sanity

```bash
# (a) The new ref is present:
grep -n "sessionExpiredRef" frontend/src/contexts/AuthContext.js
# Expected: 2 hits (declaration + usage inside interceptor).

# (b) The new interceptor registration is present:
grep -n "interceptors.response.use" frontend/src/contexts/AuthContext.js
# Expected: 2 hits (existing pending_deletion + new 401 handler).

# (c) The new toast message is exactly as specified:
grep -n "החיבור פג, אנא התחבר מחדש" frontend/src/contexts/AuthContext.js
# Expected: 1 hit.

# (d) The redirect target is /login:
grep -n "window.location.href = '/login'" frontend/src/contexts/AuthContext.js
# Expected: 1 hit.

# (e) The auth-endpoint skip is present:
grep -n "url.includes('/auth/')" frontend/src/contexts/AuthContext.js
# Expected: 1 hit.

# (f) services/api.js untouched:
git diff --stat frontend/src/services/api.js
# Expected: empty.

# (g) App.js untouched:
git diff --stat frontend/src/App.js
# Expected: empty.

# (h) LoginPage untouched:
git diff --stat frontend/src/pages/LoginPage.js
# Expected: empty.

# (i) Exactly one file changed:
git diff --name-only | sort
# Expected:
# frontend/src/contexts/AuthContext.js

# (j) Backend untouched:
git diff --stat backend/
# Expected: empty.

# (k) No package changes:
git diff frontend/package.json frontend/package-lock.json
# Expected: empty.

# (l) Existing fetchCurrentUser auth-error logic untouched:
grep -n "_isAuthError" frontend/src/contexts/AuthContext.js
# Expected: same count as before (2 hits — definition + usage in fetchCurrentUser catch block).

# (m) The existing pending_deletion interceptor is untouched:
grep -n "pending_deletion" frontend/src/contexts/AuthContext.js
# Expected: same count as before (2 hits — _isAuthError guard + interceptor body).
```

### 2. Build clean

```bash
cd frontend && REACT_APP_BACKEND_URL=https://example.com CI=true npm run build
```

Expected: no errors, no new warnings.

### 3. Manual tests

After deploy + hard refresh:

#### Test A — Mid-session token expiry (the main fix)

1. Log in normally.
2. Navigate to any page (e.g., a project, a unit).
3. Open DevTools → Application → Local Storage → manually change the `token` value to something invalid (e.g., add `XXX` to the end).
4. Trigger an API call — click into a project or refresh the unit page.
5. ✅ Within 1-2 seconds, a toast appears: "החיבור פג, אנא התחבר מחדש".
6. ✅ Page reloads, URL changes to `/login`.
7. ✅ localStorage `token` is empty.
8. ✅ Cookie `brikops_logged_in` is gone.
9. Log back in → ✅ lands on `/` with fresh state.

#### Test B — Failed login (regression — must NOT auto-logout)

1. From `/login`, type a wrong password.
2. Submit.
3. ✅ Login page shows "שם משתמש או סיסמה שגויים" (or whatever the existing error is).
4. ✅ NO toast "החיבור פג".
5. ✅ URL stays on `/login` (no reload).
6. Enter correct password → ✅ logs in normally.

#### Test C — Failed OTP (regression — must NOT auto-logout)

1. Start OTP login flow.
2. Enter wrong OTP code.
3. Submit.
4. ✅ OTP screen shows its own error.
5. ✅ NO toast "החיבור פג".
6. ✅ Stays on OTP screen.

#### Test D — App startup with expired token (regression)

1. Log in, then log out.
2. Manually set localStorage `token` to an old/invalid token.
3. Refresh the page.
4. ✅ The existing `fetchCurrentUser` logic catches the 401 from `/auth/me` and cleans up state.
5. ✅ User sees the login page.
6. ✅ NO "החיבור פג" toast (because the new interceptor skips `/auth/me` via the auth-endpoint filter).

#### Test E — Concurrent 401s (debounce)

1. Log in. Go to a page that fires 3+ parallel API calls on load (e.g., project control page).
2. Open DevTools → Network → enable "Offline" briefly? No, better: use DevTools → Application → Local Storage to invalidate the token, then quickly refresh.
3. Multiple API calls fire in parallel and all get 401.
4. ✅ EXACTLY ONE toast appears ("החיבור פג, אנא התחבר מחדש").
5. ✅ One redirect to `/login` (not multiple navigations).

#### Test F — 403 pending_deletion (regression — must use existing flow)

1. Set up a pending_deletion user (or simulate by mocking the backend response).
2. Trigger any API call.
3. ✅ The existing interceptor at AuthContext.js:62-75 fires — `error._pendingDeletion = true`, user's `user_status` updated to `pending_deletion`.
4. ✅ NO "החיבור פג" toast (because our new interceptor only handles 401, not 403).
5. ✅ NO redirect to `/login`. The app's pending-deletion UI path takes over.

#### Test G — Other 403 (regression — must NOT auto-logout)

1. As a logged-in non-admin user, try to hit an admin-only endpoint (e.g., a DevTools-crafted request to a billing-admin-only URL).
2. Response: 403 (not 401).
3. ✅ NO "החיבור פג" toast.
4. ✅ NO redirect.
5. ✅ The call's .catch handler shows whatever error message the caller decided.

#### Test H — User on login page hitting 401 (edge — no false alarm)

1. Open `/login` in a fresh incognito window (no token).
2. Manually craft a DevTools request to a protected endpoint (e.g., GET `/api/projects`).
3. Response: 401.
4. ✅ NO "החיבור פג" toast (no token → skipped).
5. ✅ Stays on `/login`.

---

## Commit message (exactly)

```
fix(auth): auto-logout on mid-session 401 + redirect to /login

When a user's JWT expires mid-session, every subsequent API call
returns 401 but nothing catches it globally. The UI shows a cascade
of confusing "לא נמצא" / "שגיאה בטעינה" errors because data fetches
fail with no auth context. Users don't realize they're logged out.

Fix: add a second response interceptor inside AuthProvider that
catches 401 on non-auth endpoints while the user has a token. Clears
token + cookie + user state, shows "החיבור פג, אנא התחבר מחדש" toast,
redirects to /login via full page reload (AuthProvider is outside
BrowserRouter so useNavigate isn't available — full reload also
guarantees clean post-session state).

Guards:
- Skips /auth/ endpoints (failed login/OTP/register legitimately 401)
- Skips when no token (pre-login 401s don't trigger session-expired)
- Debounced via ref (concurrent 401s fire the flow exactly once)

Respects the existing #171 guidance that keeps 401 handling out of
services/api.js interceptor. Existing pending_deletion 403 handler
(AuthContext.js:62-75) untouched. fetchCurrentUser's startup auth
logic untouched.

One file changed. No new deps. No backend changes.
```

---

## Deploy

```bash
./deploy.sh --prod
```

OTA only.

**Before declaring fix complete, Zahi should:**

1. Hard refresh browser (Cmd+Shift+R) or close/reopen the native app.
2. Run Test A (main fix — manually invalidate token, verify redirect).
3. Run Test B (failed login still works — regression).
4. Run Test D (app startup flow still works — regression).

---

## Definition of Done

- [ ] `sessionExpiredRef` declared once inside AuthProvider
- [ ] New useEffect registers a 401 interceptor that cleans up session + toast + redirect
- [ ] Auth endpoints (`/auth/*`) are skipped by the interceptor
- [ ] No-token case is skipped by the interceptor
- [ ] Debounce ref prevents double-firing on concurrent 401s
- [ ] All 13 grep checks pass
- [ ] `npm run build` clean (no new warnings)
- [ ] Tests A–H pass
- [ ] `./deploy.sh --prod` succeeded
