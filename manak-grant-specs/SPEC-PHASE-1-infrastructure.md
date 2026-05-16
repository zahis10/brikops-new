# Spec — manak-grant Phase 1 (Infrastructure Foundation)

**Project:** `manak-grant`
**Phase:** 1 of 5 — תשתית בסיסית
**Estimated:** 1 day for Replit
**Status:** Ready to start

---

## Goal

Build a deployable end-to-end skeleton:
- Supabase project (DB + Auth + Storage)
- FastAPI backend on Render with `/health` + `/api/me`
- React+Vite frontend on Cloudflare Pages with Login + Home (proves auth roundtrip)
- DB schema in place
- All credentials in env vars
- Zero business logic yet — just the rails

When this phase is done: a user can log in via the deployed URL, see their name, and get a 200 from a protected backend endpoint. Phase 2 onward layers in business logic on top of these working rails.

## Architecture (locked)

| Component | Service | Free tier limit |
|-----------|---------|----------------|
| Frontend | Cloudflare Pages | unlimited |
| Backend | Render Web Service | 750 hours/month, sleeps after 15 min idle (acceptable for MVP) |
| DB / Auth / Storage | Supabase | 500MB DB, 50K MAU, 1GB storage |
| Code | GitHub private repo | unlimited |

**No paid services. No vendor lock-in beyond standard Postgres + Python.**

## Repo structure

```
manak-grant/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── deps.py              # auth dependency (validates Supabase JWT)
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   └── auth.py          # /api/me only this phase
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── supabase.py      # Supabase admin client init
│   │   └── models/
│   │       ├── __init__.py
│   │       └── schemas.py       # Pydantic
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_health.py
│   ├── requirements.txt
│   ├── render.yaml              # Render auto-deploy config
│   ├── Dockerfile               # for portability
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   └── Home.jsx
│   │   ├── lib/
│   │   │   ├── api.js           # fetch wrapper with auth header
│   │   │   └── supabase.js      # Supabase client init
│   │   ├── components/
│   │   │   └── Layout.jsx
│   │   └── index.css
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── _redirects               # Cloudflare SPA fallback
│   └── .env.example
├── infra/
│   ├── supabase-schema.sql
│   └── README.md
├── docs/
│   ├── handover.md              # for friend transfer (provided separately)
│   ├── architecture.md
│   └── deploy.md
├── .gitignore
└── README.md
```

## Database schema

Run this SQL in Supabase SQL editor (file: `infra/supabase-schema.sql`).
Full file is provided separately.

Tables:
- `firms` — single firm row inserted manually for now
- `user_profiles` — extends Supabase `auth.users` with firm_id + role
- `clients` — businesses managed by the firm
- `claims` — grant requests per client
- `audit_log` — append-only

Row-level security:
- Clerk: sees only clients where `assigned_to = auth.uid()`
- Owner: sees all clients in their firm
- Same logic for claims (via client.firm_id)

## Backend — Phase 1 endpoints

### `GET /health`
No auth. Returns `{"status": "ok", "version": "0.1.0"}`.

### `GET /api/me`
Auth required. Returns user profile:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "מיכל כהן",
  "role": "clerk",
  "firm_id": "uuid",
  "firm_name": "משרד רוה״ח"
}
```

If JWT invalid: 401.
If JWT valid but no profile row: 403 with message "user not provisioned".

### Auth dependency (`app/deps.py`)

Implementation: validate Supabase JWT using `SUPABASE_JWT_SECRET`. Use `python-jose` or `pyjwt`. Extract `sub` (user ID), then query `user_profiles` table. Cache profile per request.

Do NOT use Supabase admin client to validate token — verify locally with the JWT secret. This is the standard Supabase pattern.

## Frontend — Phase 1 routes

### `/login`
Email + password form. On submit: `supabase.auth.signInWithPassword(...)`. On success → redirect `/`. On fail → show error inline.

### `/` (Home, protected)
If not logged in → redirect `/login`.
On mount: call `GET /api/me`.
Show: `שלום, {full_name} — אתה {role === 'owner' ? 'מנהל' : 'עובדת'} ב-{firm_name}`.
Show a logout button.

That's it for Phase 1 frontend. No client management, no wizard, no dashboard.

### Layout component
RTL (`dir="rtl"`), Hebrew font (Heebo), Tailwind setup. Header with project name + logout.

## Environment variables

### Backend (`.env`)
```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=<anon key>
SUPABASE_SERVICE_KEY=<service role key>     # for admin ops, never sent to frontend
SUPABASE_JWT_SECRET=<jwt secret from API settings>
ALLOWED_ORIGINS=https://manak-grant.pages.dev,http://localhost:5173
PORT=8000
```

### Frontend (`.env`)
```
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key>
VITE_API_BASE_URL=https://manak-grant-api.onrender.com
```

`.env` files are gitignored. `.env.example` files are committed with placeholder values.

## Deploy targets

### Backend → Render
- Service type: Web Service
- Runtime: Python 3.11
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Env vars: as listed above
- Add `render.yaml` for blueprint-based deploys

### Frontend → Cloudflare Pages
- Framework preset: Vite
- Build command: `npm run build`
- Build output: `dist`
- Root directory: `frontend`
- Env vars: as listed above (frontend ones only)

## Acceptance criteria (VERIFY)

A reviewer can:
1. Clone the repo from GitHub
2. Run `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload` → server starts on :8000
3. `curl http://localhost:8000/health` → `{"status":"ok","version":"0.1.0"}`
4. Run `cd frontend && npm install && npm run dev` → opens at :5173
5. Visit `/login`, sign in with credentials provided in seed step → redirected to `/`
6. See "שלום, [name] — אתה [role] ב-[firm name]"
7. Open DevTools network tab → see request to `/api/me` with `Authorization: Bearer <jwt>` header → response is 200 with profile data
8. `pytest backend/tests/` → all tests pass

Deployed verification:
1. Visit `https://manak-grant.pages.dev` → login page loads
2. Sign in → home page shows correct user info
3. Network tab → backend responds from Render URL

## Initial seed data

After running the schema SQL in Supabase, also run:

```sql
-- Insert the firm (single firm for now)
insert into firms (name) values ('משרד רוה״ח להדגמה') returning id;
-- copy the returned uuid for the next step

-- Manually create an owner user in Supabase Auth dashboard:
-- email: owner@example.com
-- password: <strong password>
-- After creation, copy the user's auth.uid

insert into user_profiles (id, firm_id, full_name, role)
values (
  '<auth.uid from above>',
  '<firm uuid from above>',
  'אורי הבעלים',
  'owner'
);
```

This creates one owner user. Later phases add UI for inviting employees.

## DO NOT (this phase)

- **DO NOT** translate the calculator to Python yet. Phase 2.
- **DO NOT** upload the Excel template anywhere yet. Phase 4.
- **DO NOT** build CRUD endpoints for clients/claims yet. Phase 3.
- **DO NOT** build the wizard or dashboard. Phase 4-5.
- **DO NOT** put any secrets in code. Env vars only.
- **DO NOT** set up CI/CD beyond a basic `pytest` GitHub Action. Auto-deploy via Render+Cloudflare is enough for now.
- **DO NOT** use TypeScript for frontend. Plain JavaScript + JSX (matches MVP).
- **DO NOT** use Tailwind plugins beyond what comes default. Keep config minimal.
- **DO NOT** add component libraries (shadcn, MUI, Chakra). Plain Tailwind.
- **DO NOT** install pdf.js, sheetjs, or any client-side parsers. These come in Phase 4 (frontend integration).
- **DO NOT** add any analytics, error tracking, or telemetry.

## Tech versions

- Python: 3.11
- FastAPI: latest
- pydantic: v2
- Supabase Python SDK: latest (`supabase`)
- Node: 20 LTS
- Vite: latest
- React: 18
- Tailwind: 3.x

## Testing

- `pytest backend/tests/test_health.py` — sanity that the app starts and `/health` returns 200
- No frontend tests this phase (phase 5)
- A `conftest.py` should set up a TestClient

## Documentation deliverables

- `README.md` — quick start (clone, install, run dev)
- `docs/architecture.md` — diagram + explanation of the stack
- `docs/deploy.md` — step-by-step how to deploy to Render + Cloudflare
- `infra/supabase-schema.sql` — full schema, runnable in SQL editor
- `infra/README.md` — how to set up Supabase project from scratch

## Files to deliver in Replit's review.txt

When complete, Replit must list:
1. All files created (path + LOC)
2. URLs of deployed services (Render + Cloudflare)
3. The Supabase project URL (without exposing secrets)
4. Output of `pytest backend/tests/` showing all tests passed
5. Screenshot of `/login` page
6. Screenshot of `/` page after login
7. The seeded owner email (NOT the password — that goes to Zahi separately)
8. Any deviations from this spec, with reasons

## When this is done

Phase 2 brief:
- Translate `calculator.js` (40 unit tests included) to Python
- Add `POST /api/calculate` endpoint
- All tests pass in Python
- Frontend can call it and display results

That's the next spec. We'll write it after Phase 1 is verified.
