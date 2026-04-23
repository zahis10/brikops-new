import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowRight, AlertTriangle, Clock, GraduationCap, AlertCircle,
  Users, TrendingUp, ShieldAlert, Wrench, Hammer,
} from 'lucide-react';
import { toast } from 'sonner';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { safetyService, projectService } from '../services/api';
import SafetyScoreGauge from '../components/safety/SafetyScoreGauge';
import SafetyKpiCard from '../components/safety/SafetyKpiCard';

const SEVERITY_HE = { '1': 'נמוכה', '2': 'בינונית', '3': 'גבוהה', 1: 'נמוכה', 2: 'בינונית', 3: 'גבוהה' };
const SEVERITY_COLOR = {
  '1': 'bg-blue-100 text-blue-800', '2': 'bg-amber-100 text-amber-800', '3': 'bg-red-100 text-red-800',
  1: 'bg-blue-100 text-blue-800', 2: 'bg-amber-100 text-amber-800', 3: 'bg-red-100 text-red-800',
};
const DOC_STATUS_HE = { open: 'פתוח', in_progress: 'בביצוע', resolved: 'נפתר', verified: 'אומת' };
const TASK_STATUS_HE = { open: 'פתוח', in_progress: 'בביצוע', completed: 'הושלם', cancelled: 'בוטל' };

export default function SafetyHomePage() {
  const { projectId } = useParams();
  const navigate = useNavigate();

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
        let proj = null;
        try {
          proj = await projectService.get(projectId);
        } catch (e) {
          // Fall through — safety endpoints will surface their own status
        }
        if (cancelled) return;
        if (proj) setProject(proj);

        const [scoreResp, docsResp, tasksResp, workersResp] = await Promise.all([
          safetyService.getScore(projectId).catch((e) => ({ __err: e })),
          safetyService.listDocuments(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listTasks(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listWorkers(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
        ]);
        if (cancelled) return;

        const responses = [scoreResp, docsResp, tasksResp, workersResp];
        const has404 = responses.some((r) => r?.__err?.response?.status === 404);
        const has403 = responses.some((r) => r?.__err?.response?.status === 403);

        if (has404) { setFlagOff(true); setLoading(false); return; }
        if (has403) { setForbidden(true); setLoading(false); return; }

        const otherErr = responses.find((r) => r?.__err);
        if (otherErr) {
          toast.error('שגיאה בטעינת נתוני בטיחות');
          setLoading(false);
          return;
        }

        setScoreData(scoreResp);
        setDocs(docsResp || { items: [], total: 0 });
        setTasks(tasksResp || { items: [], total: 0 });
        setWorkers(workersResp || { items: [], total: 0 });
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
  if (flagOff) return <SafetyFlagOff onBack={() => navigate(`/projects/${projectId}/dashboard`)} />;

  const b = scoreData?.breakdown || {};
  const caps = b.caps || {};
  const cacheAge = scoreData?.cache_age_seconds ?? 0;

  const sev3 = b.doc_counts?.sev3 ?? 0;
  const sev2 = b.doc_counts?.sev2 ?? 0;
  const sev1 = b.doc_counts?.sev1 ?? 0;
  const openDocs = sev3 + sev2 + sev1;
  const overdueTotal = b.overdue_task_counts?.total ?? 0;
  const overdueSev3 = b.overdue_task_counts?.sev3 ?? 0;
  const untrained = b.workers_without_training ?? 0;
  const totalWorkers = b.total_workers ?? 0;
  const incidentsTotal = b.incidents_last_90d?.total ?? 0;
  const incidentsInjury = b.incidents_last_90d?.injury ?? 0;

  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 pb-16">
      <div className="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-3 sticky top-0 z-20">
        <button
          onClick={() => navigate(`/projects/${projectId}/dashboard`)}
          className="p-2 rounded-lg hover:bg-slate-100"
          aria-label="חזור"
          type="button"
        >
          <ArrowRight className="w-5 h-5 text-slate-700" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-bold text-slate-900 truncate">בטיחות</h1>
          {project?.name && <p className="text-xs text-slate-500 truncate">{project.name}</p>}
        </div>
        {cacheAge > 0 && (
          <p className="text-[11px] text-slate-400">עודכן לפני {Math.max(1, Math.round(cacheAge / 60))} דק׳</p>
        )}
      </div>

      <div className="max-w-6xl mx-auto px-4 py-5 space-y-6">
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

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <SafetyKpiCard
            icon={ShieldAlert}
            label="ליקויים פתוחים"
            value={openDocs}
            sub={`חמור: ${sev3}`}
            tone={sev3 > 0 ? 'danger' : 'neutral'}
            onClick={() => setActiveTab('documents')}
          />
          <SafetyKpiCard
            icon={Clock}
            label="משימות באיחור"
            value={overdueTotal}
            sub={`חמור: ${overdueSev3}`}
            tone={overdueTotal > 0 ? 'warning' : 'neutral'}
            onClick={() => setActiveTab('tasks')}
          />
          <SafetyKpiCard
            icon={GraduationCap}
            label="עובדים ללא הדרכה"
            value={untrained}
            sub={`מתוך ${totalWorkers} עובדים`}
            tone={untrained > 0 ? 'warning' : 'success'}
            onClick={() => setActiveTab('workers')}
          />
          <SafetyKpiCard
            icon={AlertCircle}
            label="אירועים (90 יום)"
            value={incidentsTotal}
            sub={`פציעות: ${incidentsInjury}`}
            tone={incidentsInjury > 0 ? 'danger' : 'neutral'}
          />
          <SafetyKpiCard
            icon={Users}
            label="סך עובדים באתר"
            value={totalWorkers}
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

        <Card className="p-0 overflow-hidden bg-white shadow-sm">
          <Tabs value={activeTab} onValueChange={setActiveTab} dir="rtl">
            <TabsList className="w-full justify-start rounded-none border-b bg-slate-50 p-0 h-auto overflow-x-auto flex">
              <TabsTrigger
                value="documents"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                ליקויים ({docs.total})
              </TabsTrigger>
              <TabsTrigger
                value="tasks"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                משימות ({tasks.total})
              </TabsTrigger>
              <TabsTrigger
                value="workers"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
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

function BreakdownBar({ label, value = 0, max = 1, color }) {
  const safeMax = Number(max) > 0 ? Number(max) : 1;
  const safeVal = Math.max(0, Number(value) || 0);
  const pct = Math.min(100, (safeVal / safeMax) * 100);
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-slate-600">{label}</span>
        <span className="text-xs text-slate-500">{safeVal.toFixed(1)} / {safeMax}</span>
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
            {(d.found_at || '').slice(0, 10)}
          </time>
        </li>
      ))}
    </ul>
  );
}

function TasksList({ items }) {
  if (!items?.length) return <EmptyState icon={Wrench} text="אין משימות בטיחות פתוחות" />;
  const nowIso = new Date().toISOString();
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((tk) => {
        const overdue = tk.due_at && tk.due_at < nowIso && !['completed', 'cancelled'].includes(tk.status);
        return (
          <li key={tk.id} className="px-4 py-3 flex items-start gap-3 hover:bg-slate-50">
            <Badge className={SEVERITY_COLOR[tk.severity] || 'bg-slate-100 text-slate-700'}>
              {SEVERITY_HE[tk.severity] || '—'}
            </Badge>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-slate-900 truncate">{tk.title}</p>
              <p className="text-xs text-slate-500 truncate">
                {TASK_STATUS_HE[tk.status] || tk.status}
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
      <button onClick={onBack} className="mt-4 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm" type="button">
        חזור לדאשבורד
      </button>
    </div>
  );
}

function SafetyFlagOff({ onBack }) {
  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8 text-center">
      <ShieldAlert className="w-12 h-12 text-slate-400 mb-3" />
      <h2 className="text-lg font-bold text-slate-900">מודול הבטיחות אינו פעיל בארגון זה</h2>
      <p className="text-sm text-slate-600 mt-2">צור קשר עם התמיכה להפעלה.</p>
      <button onClick={onBack} className="mt-4 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm" type="button">
        חזור לדאשבורד
      </button>
    </div>
  );
}
