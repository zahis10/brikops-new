# Task #40 — Safety Phase 1 Part 4 — Frontend Core (Home + Score + Tabs)

**Scope:** ~5 new files, ~1 touch to `services/api.js`, 1 touch to `App.js`, 1 touch to `i18n/locales/he.json`. No new deps, no backend changes.

**Why:** Backend is shipped and the response contract is locked (Part 3a `breakdown` shape). Frontend needs a management-only Safety Home page that renders the score gauge + 6 KPI tiles + 3 tabs (ליקויים / משימות / עובדים). **Deliberately excludes** the full filter sheet, bulk select, and export buttons — those are Part 5.

## Done looks like

- Navigate to `/projects/:projectId/safety` on a project where `ENABLE_SAFETY_MODULE=true` (local) → see score gauge, 6 KPI tiles, 3 tabs with live data from the 5 Part 2 list endpoints + `/score`.
- Page is **management-only** — contractor role sees a friendly "אין הרשאה" state, not a crash.
- On a project where the flag is off (production default), the page renders an empty state, not a 500 toast.
- No raw `id_number`, `id_number_hash`, or any hashed PII visible in the DOM or network payloads.
- RTL layout correct; Hebrew labels everywhere; text aligned right; icons on the left.
- Mobile (375px) and desktop (1280px+) both look right — grid stacks, gauge scales, tabs scroll horizontally if needed.

## Out of scope for Part 4

- ❌ Full 7-dim filter sheet (Part 5).
- ❌ Bulk select + bulk soft-delete (Part 5).
- ❌ Export buttons wired to `/export/excel`, `/export/filtered`, `/export/pdf-register` (Part 5).
- ❌ Create/edit modals for documents/tasks/workers — Part 4 shows read-only lists. Minimal "+" button on each tab routes to a future `/new` sub-route (not built yet) — leave the button with `onClick={() => toast.info('בקרוב')}`.
- ❌ Incident tab (use KPI card for count; full list lives in Part 5 filter drawer or a dedicated route later).
- ❌ Score refresh toast polling.
- ❌ Real-time WebSocket updates.
- ❌ Any backend change. If you think the contract is wrong, STOP and ask Zahi. Do not touch safety_router.py or safety_pdf.py.

---

## Steps

### Step 1 — Add `safetyService` to the API client

**File:** `frontend/src/services/api.js`

Near the other service exports (after `taskService`), add:

```javascript
export const safetyService = {
  async getScore(projectId, refresh = false) {
    const params = refresh ? { refresh: 'true' } : {};
    const response = await axios.get(
      `${API}/safety/${projectId}/score`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },

  async listDocuments(projectId, params = {}) {
    // Part 2 endpoint — accepts category/severity/status/company_id/assignee_id/reporter_id/date_from/date_to/limit/offset
    const response = await axios.get(
      `${API}/safety/${projectId}/documents`,
      { headers: getAuthHeader(), params }
    );
    return response.data; // {items, total, limit, offset}
  },

  async listTasks(projectId, params = {}) {
    const response = await axios.get(
      `${API}/safety/${projectId}/tasks`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },

  async listWorkers(projectId, params = {}) {
    const response = await axios.get(
      `${API}/safety/${projectId}/workers`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },

  async listTrainings(projectId, params = {}) {
    const response = await axios.get(
      `${API}/safety/${projectId}/trainings`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },

  async listIncidents(projectId, params = {}) {
    const response = await axios.get(
      `${API}/safety/${projectId}/incidents`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },

  async healthz() {
    const response = await axios.get(`${API}/safety/healthz`, { headers: getAuthHeader() });
    return response.data; // {ok: true, flag: bool, collections: [...]}
  },
};
```

**Cache:** do NOT wrap these in `cachedFetch` — score has its own server-side cache, and list endpoints need to be live.

---

### Step 2 — Create `SafetyScoreGauge` component

**File:** `frontend/src/components/safety/SafetyScoreGauge.js` (new directory `safety/`)

A pure SVG donut gauge, 0–100. No external chart library. Color tiers:

- `score ≥ 85` → `#10b981` (emerald-500) — "מצוין"
- `70 ≤ score < 85` → `#3b82f6` (blue-500) — "טוב"
- `50 ≤ score < 70` → `#f59e0b` (amber-500) — "תקין"
- `score < 50` → `#ef4444` (red-500) — "דורש תיקון"

**Component signature:**

```javascript
import React from 'react';

/**
 * 0-100 donut gauge. RTL-safe (no direction-specific markup).
 * @param {number} score       0..100
 * @param {number} size        px, default 180
 * @param {number} stroke      px, default 14
 * @param {string} label       optional Hebrew label under the number
 */
export default function SafetyScoreGauge({ score = 0, size = 180, stroke = 14, label }) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  const offset = circumference * (1 - clamped / 100);

  let color = '#ef4444', tierHe = 'דורש תיקון';
  if (clamped >= 85)      { color = '#10b981'; tierHe = 'מצוין'; }
  else if (clamped >= 70) { color = '#3b82f6'; tierHe = 'טוב'; }
  else if (clamped >= 50) { color = '#f59e0b'; tierHe = 'תקין'; }

  return (
    <div className="flex flex-col items-center justify-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label={`ציון בטיחות ${clamped} מתוך 100`}>
        {/* Track */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          stroke="#e5e7eb" strokeWidth={stroke} fill="none"
        />
        {/* Value — starts at top (-90deg), clockwise */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          stroke={color} strokeWidth={stroke} fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 400ms ease-out, stroke 400ms ease-out' }}
        />
        {/* Center text */}
        <text
          x="50%" y="47%"
          textAnchor="middle" dominantBaseline="central"
          fontSize={size * 0.28} fontWeight="800"
          fill="#0f172a"
        >
          {clamped}
        </text>
        <text
          x="50%" y="62%"
          textAnchor="middle" dominantBaseline="central"
          fontSize={size * 0.08} fontWeight="600"
          fill="#64748b"
        >
          {tierHe}
        </text>
      </svg>
      {label && <p className="text-sm text-slate-600 mt-2 font-medium">{label}</p>}
    </div>
  );
}
```

**Accessibility:** SVG has `aria-label` with the score. No reliance on color alone — tier name is rendered as text.

---

### Step 3 — Create `SafetyKpiCard` component

**File:** `frontend/src/components/safety/SafetyKpiCard.js`

Follow the pattern from `ProjectDashboardPage.js` KpiCard (inline) but pull it out so it's reusable:

```javascript
import React from 'react';

/**
 * KPI tile for safety home.
 * @param {Component} icon        lucide-react icon component
 * @param {string} label          Hebrew label
 * @param {number|string} value   big number or text
 * @param {string} sub            small sub-line (e.g., "מתוך 12")
 * @param {string} tone           'neutral' | 'info' | 'warning' | 'danger' | 'success'
 * @param {function} onClick      optional — click to switch tab or open drawer
 */
export default function SafetyKpiCard({ icon: Icon, label, value, sub, tone = 'neutral', onClick }) {
  const toneMap = {
    neutral: { bg: 'bg-white',       border: 'border-slate-200',  iconBg: 'bg-slate-100',   iconFg: 'text-slate-600', num: 'text-slate-900' },
    info:    { bg: 'bg-blue-50',     border: 'border-blue-200',   iconBg: 'bg-blue-100',    iconFg: 'text-blue-700',  num: 'text-blue-900' },
    warning: { bg: 'bg-amber-50',    border: 'border-amber-200',  iconBg: 'bg-amber-100',   iconFg: 'text-amber-700', num: 'text-amber-900' },
    danger:  { bg: 'bg-red-50',      border: 'border-red-200',    iconBg: 'bg-red-100',     iconFg: 'text-red-700',   num: 'text-red-900' },
    success: { bg: 'bg-emerald-50',  border: 'border-emerald-200',iconBg: 'bg-emerald-100', iconFg: 'text-emerald-700', num: 'text-emerald-900' },
  };
  const t = toneMap[tone] || toneMap.neutral;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-right ${t.bg} ${t.border} border rounded-xl p-4 shadow-sm
                  transition-all hover:shadow-md active:scale-[0.98] disabled:opacity-60
                  min-h-[96px] w-full`}
      disabled={!onClick}
    >
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${t.iconBg}`}>
          <Icon className={`w-5 h-5 ${t.iconFg}`} />
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-2xl font-black ${t.num} leading-none`}>{value ?? '—'}</p>
          <p className="text-xs text-slate-600 mt-1 font-medium truncate">{label}</p>
          {sub && <p className="text-[11px] text-slate-500 mt-0.5 truncate">{sub}</p>}
        </div>
      </div>
    </button>
  );
}
```

Touch-friendly: `min-h-[96px]`, native `<button>` for keyboard nav, `disabled` state when no `onClick`.

---

### Step 4 — Create the main page

**File:** `frontend/src/pages/SafetyHomePage.js`

Layout (top to bottom):

1. **Header bar** — back button (→ `/projects/:projectId/dashboard`), title "בטיחות", project name, cache-age indicator (small `updated Xm ago`).
2. **Score section** — SafetyScoreGauge (center), 4 breakdown bars on its side (docs/tasks/training/incidents with `penalty / max` as Progress bars).
3. **KPI grid** — 6 SafetyKpiCards in a 2×3 grid on mobile, 3×2 on tablet, 6×1 on desktop.
4. **Tabs** — Radix Tabs from shadcn/ui: ליקויים / משימות / עובדים. Each tab shows a simple list (no filter, no pagination beyond first 50 items) with severity badges + status pills + click-to-detail (detail modal is a Part 5 thing — for Part 4, click is a no-op or a `toast.info('בקרוב')`).

**Skeleton (fill in):**

```javascript
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowRight, AlertTriangle, Clock, GraduationCap, AlertCircle, Users, TrendingUp, ShieldAlert, Wrench, Hammer, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { safetyService, projectService } from '../services/api';

// NOTE: codebase uses RELATIVE imports (../components/ui/...) — NOT the @/ alias.
// Verify by grepping: grep "from '\.\./components/ui" frontend/src/pages/ — existing
// pages like LoginPage.js / TaskDetailPage.js / ProjectControlPage.js all use the
// relative pattern. Do NOT introduce @/ imports for this page.
import { useAuth } from '../contexts/AuthContext';
import { t } from '../i18n';
import SafetyScoreGauge from '../components/safety/SafetyScoreGauge';
import SafetyKpiCard from '../components/safety/SafetyKpiCard';

const SEVERITY_HE = { '1': 'נמוכה', '2': 'בינונית', '3': 'גבוהה' };
const SEVERITY_COLOR = { '1': 'bg-blue-100 text-blue-800', '2': 'bg-amber-100 text-amber-800', '3': 'bg-red-100 text-red-800' };
const DOC_STATUS_HE = { open: 'פתוח', in_progress: 'בביצוע', resolved: 'נפתר', verified: 'אומת' };
const TASK_STATUS_HE = { open: 'פתוח', in_progress: 'בביצוע', completed: 'הושלם', cancelled: 'בוטל' };

export default function SafetyHomePage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [project, setProject] = useState(null);
  const [scoreData, setScoreData] = useState(null);
  const [docs, setDocs] = useState({ items: [], total: 0 });
  const [tasks, setTasks] = useState({ items: [], total: 0 });
  const [workers, setWorkers] = useState({ items: [], total: 0 });
  const [flagOff, setFlagOff] = useState(false);
  const [forbidden, setForbidden] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('documents');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const proj = await projectService.get(projectId);
        if (cancelled) return;
        setProject(proj);

        // 5 calls in parallel
        const [scoreResp, docsResp, tasksResp, workersResp] = await Promise.all([
          safetyService.getScore(projectId).catch((e) => ({ __err: e })),
          safetyService.listDocuments(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listTasks(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listWorkers(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
        ]);
        if (cancelled) return;

        // Detect flag-off (404 on every safety route) vs forbidden (403 on project access)
        const firstErr = [scoreResp, docsResp, tasksResp, workersResp].find((r) => r?.__err);
        if (firstErr) {
          const status = firstErr.__err?.response?.status;
          if (status === 404) { setFlagOff(true); setLoading(false); return; }
          if (status === 403) { setForbidden(true); setLoading(false); return; }
          toast.error('שגיאה בטעינת נתוני בטיחות');
          setLoading(false);
          return;
        }

        setScoreData(scoreResp);
        setDocs(docsResp);
        setTasks(tasksResp);
        setWorkers(workersResp);
      } catch (err) {
        if (!cancelled) toast.error('שגיאה בטעינת נתונים');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  if (loading) return <SafetySkeleton />;
  if (forbidden) return <SafetyForbidden onBack={() => navigate(`/projects/${projectId}/dashboard`)} />;
  if (flagOff)   return <SafetyFlagOff  onBack={() => navigate(`/projects/${projectId}/dashboard`)} />;

  const b = scoreData?.breakdown || {};
  const caps = b.caps || {};
  const cacheAge = scoreData?.cache_age_seconds ?? 0;

  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 pb-16">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-3 sticky top-0 z-20">
        <button onClick={() => navigate(`/projects/${projectId}/dashboard`)} className="p-2 rounded-lg hover:bg-slate-100" aria-label="חזור">
          <ArrowRight className="w-5 h-5 text-slate-700" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-bold text-slate-900 truncate">בטיחות</h1>
          <p className="text-xs text-slate-500 truncate">{project?.name}</p>
        </div>
        {cacheAge > 0 && (
          <p className="text-[11px] text-slate-400">עודכן לפני {Math.round(cacheAge / 60)} דק׳</p>
        )}
      </div>

      <div className="max-w-6xl mx-auto px-4 py-5 space-y-6">
        {/* Score section */}
        <Card className="p-5 bg-white shadow-sm">
          <div className="flex flex-col md:flex-row items-center gap-6">
            <SafetyScoreGauge score={scoreData?.score ?? 0} label="ציון בטיחות" />
            <div className="flex-1 w-full grid grid-cols-1 sm:grid-cols-2 gap-3">
              <BreakdownBar label="ליקויים" value={b.doc_penalty} max={caps.doc_max} color="bg-red-500" />
              <BreakdownBar label="משימות באיחור" value={b.task_penalty} max={caps.task_max} color="bg-amber-500" />
              <BreakdownBar label="הדרכות" value={b.training_penalty} max={caps.training_max} color="bg-blue-500" />
              <BreakdownBar label="אירועים (90 יום)" value={b.incident_penalty} max={caps.incident_max} color="bg-fuchsia-500" />
            </div>
          </div>
        </Card>

        {/* KPI grid — 6 tiles */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <SafetyKpiCard
            icon={ShieldAlert}
            label="ליקויים פתוחים"
            value={(b.doc_counts?.sev3 ?? 0) + (b.doc_counts?.sev2 ?? 0) + (b.doc_counts?.sev1 ?? 0)}
            sub={`חמור: ${b.doc_counts?.sev3 ?? 0}`}
            tone={(b.doc_counts?.sev3 ?? 0) > 0 ? 'danger' : 'neutral'}
            onClick={() => setActiveTab('documents')}
          />
          <SafetyKpiCard
            icon={Clock}
            label="משימות באיחור"
            value={b.overdue_task_counts?.total ?? 0}
            sub={`חמור: ${b.overdue_task_counts?.sev3 ?? 0}`}
            tone={(b.overdue_task_counts?.total ?? 0) > 0 ? 'warning' : 'neutral'}
            onClick={() => setActiveTab('tasks')}
          />
          <SafetyKpiCard
            icon={GraduationCap}
            label="עובדים ללא הדרכה"
            value={b.workers_without_training ?? 0}
            sub={`מתוך ${b.total_workers ?? 0} עובדים`}
            tone={(b.workers_without_training ?? 0) > 0 ? 'warning' : 'success'}
            onClick={() => setActiveTab('workers')}
          />
          <SafetyKpiCard
            icon={AlertCircle}
            label="אירועים (90 יום)"
            value={b.incidents_last_90d?.total ?? 0}
            sub={`פציעות: ${b.incidents_last_90d?.injury ?? 0}`}
            tone={(b.incidents_last_90d?.injury ?? 0) > 0 ? 'danger' : 'neutral'}
          />
          <SafetyKpiCard
            icon={Users}
            label="סך עובדים באתר"
            value={b.total_workers ?? 0}
            tone="info"
            onClick={() => setActiveTab('workers')}
          />
          <SafetyKpiCard
            icon={TrendingUp}
            label="ציון מצטבר"
            value={`${scoreData?.score ?? 0}%`}
            sub="מעודכן כל 5 דק׳"
            tone="info"
          />
        </div>

        {/* Tabs */}
        <Card className="p-0 overflow-hidden bg-white shadow-sm">
          <Tabs value={activeTab} onValueChange={setActiveTab} dir="rtl">
            <TabsList className="w-full justify-start rounded-none border-b bg-slate-50 p-0 h-auto">
              <TabsTrigger value="documents" className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3">
                ליקויים ({docs.total})
              </TabsTrigger>
              <TabsTrigger value="tasks" className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3">
                משימות ({tasks.total})
              </TabsTrigger>
              <TabsTrigger value="workers" className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3">
                עובדים ({workers.total})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="documents" className="p-0 m-0">
              <DocumentsList items={docs.items} />
            </TabsContent>
            <TabsContent value="tasks" className="p-0 m-0">
              <TasksList items={tasks.items} />
            </TabsContent>
            <TabsContent value="workers" className="p-0 m-0">
              <WorkersList items={workers.items} />
            </TabsContent>
          </Tabs>
        </Card>
      </div>
    </div>
  );
}

// ---- sub-components (same file, unexported) ----

function BreakdownBar({ label, value = 0, max = 1, color }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-slate-600">{label}</span>
        <span className="text-xs text-slate-500">{Number(value || 0).toFixed(1)} / {max}</span>
      </div>
      <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function DocumentsList({ items }) {
  if (!items?.length) return <EmptyState icon={ShieldAlert} text="אין ליקויים פתוחים" />;
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((d) => (
        <li key={d.id} className="px-4 py-3 flex items-start gap-3 hover:bg-slate-50">
          <Badge className={SEVERITY_COLOR[d.severity] || 'bg-slate-100 text-slate-700'}>
            {SEVERITY_HE[d.severity] || '—'}
          </Badge>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-slate-900 truncate">{d.title}</p>
            <p className="text-xs text-slate-500 truncate">
              {DOC_STATUS_HE[d.status] || d.status} · {d.location || 'ללא מיקום'}
            </p>
          </div>
          <time className="text-xs text-slate-400 shrink-0">
            {d.found_at?.slice(0, 10) || ''}
          </time>
        </li>
      ))}
    </ul>
  );
}

function TasksList({ items }) {
  if (!items?.length) return <EmptyState icon={Wrench} text="אין משימות בטיחות פתוחות" />;
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((tk) => {
        const overdue = tk.due_at && tk.due_at < new Date().toISOString() && !['completed', 'cancelled'].includes(tk.status);
        return (
          <li key={tk.id} className="px-4 py-3 flex items-start gap-3 hover:bg-slate-50">
            <Badge className={SEVERITY_COLOR[tk.severity] || 'bg-slate-100 text-slate-700'}>
              {SEVERITY_HE[tk.severity] || '—'}
            </Badge>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-slate-900 truncate">{tk.title}</p>
              <p className="text-xs text-slate-500 truncate">
                {TASK_STATUS_HE[tk.status]}
                {tk.due_at && <> · יעד {tk.due_at.slice(0, 10)}</>}
              </p>
            </div>
            {overdue && <Badge className="bg-red-100 text-red-800 shrink-0">באיחור</Badge>}
          </li>
        );
      })}
    </ul>
  );
}

function WorkersList({ items }) {
  if (!items?.length) return <EmptyState icon={Users} text="אין עובדים רשומים" />;
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((w) => (
        <li key={w.id} className="px-4 py-3 flex items-center gap-3 hover:bg-slate-50">
          <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center shrink-0">
            <Hammer className="w-5 h-5 text-slate-500" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-slate-900 truncate">{w.full_name}</p>
            <p className="text-xs text-slate-500 truncate">
              {w.profession || 'ללא מקצוע'}{w.phone && ` · ${w.phone}`}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function EmptyState({ icon: Icon, text }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-slate-400">
      <Icon className="w-10 h-10 mb-2" />
      <p className="text-sm font-medium">{text}</p>
    </div>
  );
}

function SafetySkeleton() {
  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 p-4 space-y-4 animate-pulse">
      <div className="h-12 bg-white rounded" />
      <div className="h-48 bg-white rounded" />
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {[...Array(6)].map((_, i) => <div key={i} className="h-24 bg-white rounded" />)}
      </div>
      <div className="h-64 bg-white rounded" />
    </div>
  );
}

function SafetyForbidden({ onBack }) {
  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8 text-center">
      <AlertTriangle className="w-12 h-12 text-amber-500 mb-3" />
      <h2 className="text-lg font-bold text-slate-900">אין הרשאה לצפייה בנתוני בטיחות</h2>
      <p className="text-sm text-slate-600 mt-2">מודול הבטיחות זמין לניהול פרויקט בלבד.</p>
      <button onClick={onBack} className="mt-4 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm">חזור לדאשבורד</button>
    </div>
  );
}

function SafetyFlagOff({ onBack }) {
  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8 text-center">
      <ShieldAlert className="w-12 h-12 text-slate-400 mb-3" />
      <h2 className="text-lg font-bold text-slate-900">מודול הבטיחות אינו פעיל בארגון זה</h2>
      <p className="text-sm text-slate-600 mt-2">צור קשר עם התמיכה להפעלה.</p>
      <button onClick={onBack} className="mt-4 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm">חזור לדאשבורד</button>
    </div>
  );
}
```

**Performance:** 5 network calls happen in parallel via `Promise.all` with per-promise `.catch` so one failure doesn't sink the page. Lists capped at 50 items (first page only for Part 4). Status detection:
- `404` on ANY of the safety endpoints → flag is off in this environment → show `SafetyFlagOff`
- `403` → user is not project_manager/management_team → show `SafetyForbidden`
- any other error → toast

---

### Step 5 — Register the route

**File:** `frontend/src/App.js`

Near the other `/projects/:projectId/*` routes (around line 157+), add:

```javascript
import SafetyHomePage from './pages/SafetyHomePage';

// ... inside <Routes> ...
<Route
  path="/projects/:projectId/safety"
  element={
    <ProtectedRoute allowedRoles={['project_manager', 'management_team']}>
      <SafetyHomePage />
    </ProtectedRoute>
  }
/>
```

**IMPORTANT:** Use the `allowedRoles` prop — do NOT skip it. Mirror the backend's `SAFETY_WRITERS` list so unauthorized users bounce at the router level without even hitting the backend.

---

### Step 6 — Add navigation entry + i18n keys

**File:** `frontend/src/pages/ProjectControlPage.js` — the project-level top nav lives here as the local `workTabs` array (line ~3497) + `handleWorkTab` handler (line ~3506). The HamburgerMenu is a **global app-shell** menu and does NOT contain project-scoped links — don't touch it.

The existing `workTabs` array looks like this:

```javascript
// BEFORE (line 3497-3504)
const workTabs = [
  { id: 'dashboard', label: 'דשבורד',      icon: BarChart3,       hidden: !['owner','admin','project_manager','management_team'].includes(myRole) },
  { id: 'structure', label: 'מבנה',         icon: Building2 },
  { id: 'qc',        label: 'בקרת ביצוע',   icon: ClipboardCheck,  hidden: !['owner','admin','project_manager','management_team'].includes(myRole) },
  { id: 'defects',   label: 'ליקויים',      icon: AlertTriangle },
  { id: 'handover',  label: 'מסירות',       icon: FileSignature,   hidden: !['owner','admin','project_manager','management_team','contractor'].includes(myRole) },
  { id: 'plans',     label: 'תוכניות',      icon: FileText },
].filter(t => !t.hidden);
```

**Insert `safety` between `handover` and `plans`** — position 6 per Zahi:

```javascript
// AFTER
const workTabs = [
  { id: 'dashboard', label: 'דשבורד',    icon: BarChart3,     hidden: !['owner','admin','project_manager','management_team'].includes(myRole) },
  { id: 'structure', label: 'מבנה',       icon: Building2 },
  { id: 'qc',        label: 'בקרת ביצוע', icon: ClipboardCheck, hidden: !['owner','admin','project_manager','management_team'].includes(myRole) },
  { id: 'defects',   label: 'ליקויים',    icon: AlertTriangle },
  { id: 'handover',  label: 'מסירות',     icon: FileSignature, hidden: !['owner','admin','project_manager','management_team','contractor'].includes(myRole) },
  { id: 'safety',    label: 'בטיחות',     icon: ShieldAlert,   hidden: !['owner','admin','project_manager','management_team'].includes(myRole) },  // NEW
  { id: 'plans',     label: 'תוכניות',    icon: FileText },
].filter(t => !t.hidden);
```

**Then add the handler branch** in `handleWorkTab` (line ~3506-3514), placed alphabetically near the other top-level navigates — put it right before the `if (id === 'qc')` line so visual order matches the array:

```javascript
// BEFORE (line 3506-3514)
const handleWorkTab = (id) => {
  if (id === 'dashboard') { navigate(`/projects/${projectId}/dashboard`); return; }
  if (id === 'qc')        { navigate(`/projects/${projectId}/qc`);        return; }
  if (id === 'handover')  { navigate(`/projects/${projectId}/handover`);  return; }
  if (id === 'plans')     { navigate(`/projects/${projectId}/plans`);     return; }
  setWorkMode(id);
  if (id !== 'structure') setActiveTab('');
  try { localStorage.setItem(`brikops_workMode_${projectId}`, id); } catch {}
};

// AFTER — add the safety branch
const handleWorkTab = (id) => {
  if (id === 'dashboard') { navigate(`/projects/${projectId}/dashboard`); return; }
  if (id === 'qc')        { navigate(`/projects/${projectId}/qc`);        return; }
  if (id === 'handover')  { navigate(`/projects/${projectId}/handover`);  return; }
  if (id === 'safety')    { navigate(`/projects/${projectId}/safety`);    return; }  // NEW
  if (id === 'plans')     { navigate(`/projects/${projectId}/plans`);     return; }
  setWorkMode(id);
  if (id !== 'structure') setActiveTab('');
  try { localStorage.setItem(`brikops_workMode_${projectId}`, id); } catch {}
};
```

**Import** — `ShieldAlert` from `lucide-react` is probably already imported in ProjectControlPage (check first); if not, add it to the existing `lucide-react` import statement at the top of the file. Do NOT add a new import line.

**Visibility rule** — the `hidden` check uses the full 4-role set `['owner','admin','project_manager','management_team']` to match the existing `dashboard` and `qc` tabs. Backend `_check_project_access` still enforces project_manager/management_team at the project membership level — `owner`/`admin` users who lack a project membership will bounce to `SafetyForbidden`. That's acceptable.

**Note:** the `workTabs` array is defined locally inside `ProjectControlPage`, NOT shared. The nav bar therefore only appears on this page. ProjectDashboardPage uses a different header. Users on `/dashboard` reach `/safety` through the workTabs nav when they're on Control, and through the new entry in `App.js` routing from anywhere else.

**File:** `frontend/src/i18n/he.json`

(Verified: locale files live directly under `frontend/src/i18n/` — `he.json`, `en.json`, `ar.json`, `zh.json`. No `locales/` subdirectory. The `index.js` in that folder exports `t(section, key)` with fallback to `he`.)

Add a `safety` section (merge into the existing top-level JSON object):

```json
"safety": {
  "title": "בטיחות",
  "score_label": "ציון בטיחות",
  "tier_excellent": "מצוין",
  "tier_good": "טוב",
  "tier_ok": "תקין",
  "tier_fix": "דורש תיקון",
  "breakdown_docs": "ליקויים",
  "breakdown_tasks": "משימות באיחור",
  "breakdown_training": "הדרכות",
  "breakdown_incidents": "אירועים (90 יום)",
  "kpi_open_docs": "ליקויים פתוחים",
  "kpi_overdue_tasks": "משימות באיחור",
  "kpi_untrained": "עובדים ללא הדרכה",
  "kpi_incidents_90d": "אירועים (90 יום)",
  "kpi_total_workers": "סך עובדים באתר",
  "kpi_score_percent": "ציון מצטבר",
  "tab_documents": "ליקויים",
  "tab_tasks": "משימות",
  "tab_workers": "עובדים",
  "empty_docs": "אין ליקויים פתוחים",
  "empty_tasks": "אין משימות בטיחות פתוחות",
  "empty_workers": "אין עובדים רשומים",
  "sev_1": "נמוכה",
  "sev_2": "בינונית",
  "sev_3": "גבוהה",
  "doc_status_open": "פתוח",
  "doc_status_in_progress": "בביצוע",
  "doc_status_resolved": "נפתר",
  "doc_status_verified": "אומת",
  "task_status_open": "פתוח",
  "task_status_in_progress": "בביצוע",
  "task_status_completed": "הושלם",
  "task_status_cancelled": "בוטל",
  "overdue_badge": "באיחור",
  "forbidden_title": "אין הרשאה לצפייה בנתוני בטיחות",
  "forbidden_sub": "מודול הבטיחות זמין לניהול פרויקט בלבד.",
  "flag_off_title": "מודול הבטיחות אינו פעיל בארגון זה",
  "flag_off_sub": "צור קשר עם התמיכה להפעלה.",
  "updated_ago": "עודכן לפני",
  "minutes_short": "דק׳",
  "no_location": "ללא מיקום",
  "no_profession": "ללא מקצוע",
  "coming_soon": "בקרוב"
}
```

Replit — once this section exists, you MAY convert hardcoded Hebrew in `SafetyHomePage.js` to `t('safety', 'key')` calls. It's optional polish for Part 4; if it complicates, leave the Hebrew inline (the inline pattern is what `ProjectDashboardPage` uses).

---

## DO NOT

- ❌ Do NOT change anything in `safety_router.py`, `safety_pdf.py`, `schemas.py`, or any backend file. Backend contract is locked.
- ❌ Do NOT wire the "+" buttons to create modals — that's Part 5.
- ❌ Do NOT add a filter drawer — Part 5.
- ❌ Do NOT wire export buttons — Part 5.
- ❌ Do NOT render `id_number`, `id_number_hash`, or ANY field from a worker that you haven't explicitly listed in the spec. The backend already strips PII — don't reintroduce it client-side by requesting different fields.
- ❌ Do NOT use `WebkitOverflowScrolling: 'touch'` anywhere — it freezes iOS. Use native scroll.
- ❌ Do NOT add a new hook in `hooks/`. useEffect + useState with the `cancelled` flag is the house pattern.
- ❌ Do NOT add SWR or react-query — codebase uses plain fetch.
- ❌ Do NOT add server-side pagination UI — limit=50 is fine for Part 4.
- ❌ Do NOT use `localStorage.setItem('lastSafetyProject...')` or similar — no client-side persistence for Part 4.
- ❌ Do NOT add CSS-in-JS or new Tailwind config — use existing utility classes only.
- ❌ Do NOT create a new `ProtectedRoute` variant — the existing one with `allowedRoles` is the pattern.
- ❌ Do NOT hit `/api/safety/healthz` from the page — use the 404-from-score heuristic to detect flag-off.
- ❌ Do NOT cache `safetyService.getScore` client-side — the backend already has a 5-min cache with `cache_age_seconds`.
- ❌ Do NOT bump `package.json` — no new deps. All icons used are already in lucide-react (check with `grep -r "from 'lucide-react'" frontend/src | head -5`).

---

## VERIFY before commit

### 1. Build + boot clean

```bash
cd frontend
npm run build
# Expected: no errors, no new warnings beyond existing baseline.

npm start
# Expected: dev server boots on localhost:3000, page renders.
```

**Pre-build sanity greps** — catch import / path mistakes before building:

```bash
# (a) No @/ alias imports in the new files (codebase uses relative):
grep -rn "from '@/" frontend/src/pages/SafetyHomePage.js \
                    frontend/src/components/safety/
# Expected: EMPTY. If not empty, you used @/ alias — replace with '../components/ui/...'
# or '../../components/ui/...' as appropriate.

# (b) safetyService imported wherever used:
grep -n "safetyService" frontend/src/pages/SafetyHomePage.js
# Expected: at least 2 hits (import + usage)

# (c) Hebrew locale file touched correctly:
jq '.safety | keys | length' frontend/src/i18n/he.json
# Expected: a number >= 25 (the safety section we added).

# (d) projectService.get exists (spec assumes this):
grep -n "async get(" frontend/src/services/api.js | head
# Expected: at least one hit inside the projectService block (line ~80).

# (e) All 4 shadcn components used exist:
ls frontend/src/components/ui/{tabs,card,badge,progress}.jsx 2>/dev/null | wc -l
# Expected: 4. If less — one of the components is missing; switch the import
# or replace with a primitive (BreakdownBar already avoids Progress, so the
# spec code only imports tabs/card/badge — progress.jsx is optional).
```

### 2. Route works

Navigate to `http://localhost:3000/projects/<project_id>/safety` logged in as:
- A `project_manager` → see full page
- A `contractor` → see `SafetyForbidden`
- Logged out → bounced to login

### 2b. Nav tab appears in correct position

Open `/projects/<project_id>/control` as a PM or management_team user. Verify the top tab bar reads **in this exact order**:

```
דשבורד  ·  מבנה  ·  בקרת ביצוע  ·  ליקויים  ·  מסירות  ·  בטיחות  ·  תוכניות
```

Click "בטיחות" → navigates to `/projects/<project_id>/safety`. As a `contractor` user, the "בטיחות" tab must not appear at all (same hidden pattern as dashboard/qc).

### 3. Flag-off behavior (on a backend env where `ENABLE_SAFETY_MODULE=false`)

Navigate to the safety page → see `SafetyFlagOff` card. No red toasts, no console errors beyond the expected 404s.

### 4. Score renders correctly

With a project that has seeded data:
- Score 88 → gauge is emerald, center reads "88 / מצוין"
- Score 72 → blue, "טוב"
- Score 55 → amber, "תקין"
- Score 40 → red, "דורש תיקון"
- Score 0 → red, "דורש תיקון", gauge is empty ring

### 5. Breakdown bars

4 bars render, each showing `value / max`. If `value=0`, bar is empty but visible. If `value ≥ max`, bar is fully filled (no overflow).

### 6. KPI grid responsive

- 375px (mobile): 2 columns, 3 rows
- 768px (tablet): 3 columns, 2 rows
- 1280px+ (desktop): 6 columns, 1 row
- No horizontal scroll at any breakpoint.

### 7. Tabs

Click each tab → content switches. Click a KPI card → correct tab becomes active (document card → documents tab, worker card → workers tab).

### 8. Empty states

On a brand-new project with zero safety data → all 3 tabs show `EmptyState`, score is 100 (no penalties), all KPI counts are 0.

### 9. RTL

- Text aligned right everywhere
- Back arrow on the right side of the header, chevron pointing right
- No LTR leaks (dollar signs, numbers inside Hebrew sentences don't flip weirdly)

### 10. No PII in DevTools Network tab

Open Network → click `/api/safety/{pid}/workers` response → verify `id_number`, `id_number_hash` are NOT in the JSON. (Backend Part 2 should already strip — this is a check, not a fix.)

### 11. iOS smoke (if you have access)

Build for iOS (if native changes NOT involved — this should be pure OTA) → open in TestFlight or Capgo channel → verify no scroll freeze, tabs tappable, gauge renders.

### 12. No backend changes

```bash
git diff --stat backend/ | grep -v "^$"
# Expected: empty (no backend file touched).
```

---

## Commit message (exactly)

```
feat(safety): Part 4 — Frontend Core (SafetyHome + score gauge + 3 tabs)

Adds /projects/:projectId/safety page visible to project_manager +
management_team. Renders Part 3a /score response (gauge 0-100, tier
color + label, 4 breakdown bars), 6 KPI tiles (open docs / overdue
tasks / untrained workers / incidents 90d / total workers / score %),
and 3 tabs (ליקויים / משימות / עובדים) each showing first 50 items
from the respective Part 2 list endpoint.

New files:
- frontend/src/pages/SafetyHomePage.js
- frontend/src/components/safety/SafetyScoreGauge.js
- frontend/src/components/safety/SafetyKpiCard.js

Modified:
- frontend/src/services/api.js — added safetyService with 7 methods
- frontend/src/App.js — registered /safety route behind ProtectedRoute
- frontend/src/pages/ProjectControlPage.js — inserted "בטיחות" tab between
  מסירות (handover) and תוכניות (plans) in the workTabs array at ~line 3497,
  with matching navigate branch in handleWorkTab at ~line 3506. Visible to
  owner/admin/project_manager/management_team.
- frontend/src/i18n/he.json — safety section

Auth: management-only via ProtectedRoute allowedRoles. Flag-off
rendering: if any safety endpoint returns 404, show "module disabled"
card instead of crashing. Forbidden rendering: 403 → "no permission"
card.

No new deps. No backend changes. Feature flag ENABLE_SAFETY_MODULE
stays off in prod — page will render the flag-off state until toggled.

Scope matches Part 4 spec exactly. Filter sheet, bulk select, export
buttons, and create/edit modals are Part 5.
```

---

## Deploy

```bash
./deploy.sh --prod
```

זה ה-commit וה-push. שום שלב מה-מק. זה OTA דרך Capgo.

אחרי ה-deploy — שלח ל-Zahi:
- `git log -1 --stat`
- Unified diff
- Screenshot ממסך 375px + 1280px של הדף הזה על פרויקט עם seeded data (אפשר מקומי)

---

## Definition of Done

- [ ] `safetyService` added to `services/api.js` with 6 methods
- [ ] `SafetyScoreGauge.js` created in `components/safety/`
- [ ] `SafetyKpiCard.js` created in `components/safety/`
- [ ] `SafetyHomePage.js` created in `pages/`
- [ ] Route registered in `App.js` with `allowedRoles={['project_manager', 'management_team']}`
- [ ] Menu link added, visible to management only
- [ ] i18n `safety` section added to Hebrew locale
- [ ] All 12 VERIFY steps pass
- [ ] `git diff --stat backend/` is empty
- [ ] `./deploy.sh --prod` ran successfully
- [ ] Screenshots sent to Zahi
- [ ] No new deps in `package.json`
