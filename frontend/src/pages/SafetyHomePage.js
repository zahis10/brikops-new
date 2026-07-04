import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowRight, AlertTriangle, Clock, GraduationCap, AlertCircle,
  Users, TrendingUp, ShieldAlert, Wrench, Hammer, Filter, Plus, Pencil, Camera, FileText,
} from 'lucide-react';
import { toast } from 'sonner';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import { Button } from '../components/ui/button';
import { safetyService, projectService, projectCompanyService } from '../services/api';
import SafetyScoreGauge from '../components/safety/SafetyScoreGauge';
import SafetyKpiCard from '../components/safety/SafetyKpiCard';
import SafetyFilterSheet, { countActiveFilters, EMPTY_FILTER } from '../components/safety/SafetyFilterSheet';
import SafetyExportMenu from '../components/safety/SafetyExportMenu';
import SafetyBulkActionBar from '../components/safety/SafetyBulkActionBar';
import SafetyWorkerForm from '../components/safety/SafetyWorkerForm';
import SafetyDocumentForm from '../components/safety/SafetyDocumentForm';
import SafetyDocumentDetail from '../components/safety/SafetyDocumentDetail';
import SafetyTaskForm from '../components/safety/SafetyTaskForm';
import SafetyTrainingForm from '../components/safety/SafetyTrainingForm';
import SafetyIncidentForm from '../components/safety/SafetyIncidentForm';
import SafetyWorkerCard from '../components/safety/SafetyWorkerCard';
import {
  SEVERITY_HE, DOC_STATUS_HE, TASK_STATUS_HE, INCIDENT_TYPE_HE, INCIDENT_STATUS_HE,
} from '../components/safety/safetyLabels';

// Writers = the two project roles the safety backend accepts for create/edit
// (safety_router.py SAFETY_WRITERS). The "+"/edit affordances gate on these.
const SAFETY_WRITERS = ['project_manager', 'management_team'];
const VALID_TABS = ['overview', 'documents', 'tasks', 'workers', 'trainings', 'incidents'];
const SEVERITY_COLOR = {
  '1': 'bg-blue-100 text-blue-800',
  '2': 'bg-amber-100 text-amber-800',
  '3': 'bg-red-100 text-red-800',
};

export default function SafetyHomePage() {
  const { projectId } = useParams();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [scoreData, setScoreData] = useState(null);
  const [docs, setDocs] = useState({ items: [], total: 0 });
  const [tasks, setTasks] = useState({ items: [], total: 0 });
  const [workers, setWorkers] = useState({ items: [], total: 0 });
  const [trainings, setTrainings] = useState({ items: [], total: 0 });
  const [incidents, setIncidents] = useState({ items: [], total: 0 });
  const [flagOff, setFlagOff] = useState(false);
  const [forbidden, setForbidden] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get('tab');
  const activeTab = VALID_TABS.includes(rawTab) ? rawTab : 'overview';
  const setActiveTab = (t) => {
    if (t === activeTab) return;
    const next = new URLSearchParams(searchParams);
    if (t === 'overview') next.delete('tab');
    else next.set('tab', t);
    setSearchParams(next);
  };

  // Part 5 — filter / selection / bulk state
  const [filter, setFilter] = useState(EMPTY_FILTER);
  const [filterOpen, setFilterOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [companies, setCompanies] = useState([]);
  const [users, setUsers] = useState([]);

  // Batch safety-p2-1 — create/edit modal state (one pair per entity).
  const [docForm, setDocForm] = useState({ open: false, record: null });
  const [workerForm, setWorkerForm] = useState({ open: false, record: null });
  const [taskForm, setTaskForm] = useState({ open: false, record: null });
  const [trainingForm, setTrainingForm] = useState({ open: false, record: null });
  const [incidentForm, setIncidentForm] = useState({ open: false, record: null });
  const [addChooserOpen, setAddChooserOpen] = useState(false);
  const [workerChain, setWorkerChain] = useState(null);
  const [workerCard, setWorkerCard] = useState(null);
  const [trainingCardLock, setTrainingCardLock] = useState(null);
  // Batch safety-p2-1d — read-only detail modal (row tap opens it).
  const [detailDoc, setDetailDoc] = useState(null);

  // Skip the filter useEffect's initial run — main useEffect's Promise.all
  // already fetched documents. The ref flips to false after the first real run.
  const filterFetchFirstRun = useRef(true);

  // Initial load: project + safety data + best-effort companies/memberships.
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

        const [scoreResp, docsResp, tasksResp, workersResp, trainingsResp, incidentsResp] = await Promise.all([
          safetyService.getScore(projectId).catch((e) => ({ __err: e })),
          safetyService.listDocuments(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listTasks(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listWorkers(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listTrainings(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listIncidents(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
        ]);
        if (cancelled) return;

        const responses = [scoreResp, docsResp, tasksResp, workersResp, trainingsResp, incidentsResp];
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
        setTrainings(trainingsResp || { items: [], total: 0 });
        setIncidents(incidentsResp || { items: [], total: 0 });
      } catch (err) {
        if (!cancelled) toast.error('שגיאה בטעינת נתונים');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  // Best-effort enrichment for filter dropdowns — runs once the page is
  // interactive, NOT during the loading gate. Dropdowns render "טוען..."
  // until this completes. Failures are silent.
  useEffect(() => {
    if (!projectId || loading || flagOff || forbidden) return;
    let cancelled = false;
    (async () => {
      const [membershipsResp, companiesResp] = await Promise.all([
        projectService.getMemberships(projectId).catch(() => null),
        projectCompanyService.list(projectId).catch(() => null),
      ]);
      if (cancelled) return;

      const memberList = Array.isArray(membershipsResp)
        ? membershipsResp
        : (membershipsResp?.items || []);
      const userMap = new Map();
      memberList.forEach((m) => {
        const uid = m.user_id || m.id;
        if (uid && !userMap.has(uid)) {
          userMap.set(uid, {
            id: uid,
            name: m.user_name || m.name || m.full_name || m.email || uid,
          });
        }
      });
      setUsers(Array.from(userMap.values()));

      const companyList = Array.isArray(companiesResp)
        ? companiesResp
        : (companiesResp?.items || []);
      setCompanies(companyList.map((c) => ({ id: c.id, name: c.name || c.id })));
    })();
    return () => { cancelled = true; };
  }, [projectId, loading, flagOff, forbidden]);

  // Refetch documents whenever the filter changes. Skipped on the first run
  // (main useEffect's Promise.all already fetched documents with no filter)
  // and on forbidden / flag-off / loading terminal states.
  useEffect(() => {
    if (!projectId || loading || flagOff || forbidden) return;

    // First run after the page finishes loading: skip — docs already fetched.
    if (filterFetchFirstRun.current) {
      filterFetchFirstRun.current = false;
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const params = { limit: 50 };
        Object.entries(filter).forEach(([k, v]) => {
          if (v != null && v !== '') params[k] = v;
        });
        const resp = await safetyService.listDocuments(projectId, params);
        if (!cancelled) setDocs(resp || { items: [], total: 0 });
      } catch (err) {
        if (!cancelled) toast.error('שגיאה בטעינת ליקויים מסוננים');
      }
    })();
    return () => { cancelled = true; };
  }, [projectId, filter, loading, flagOff, forbidden]);

  // Clear selection whenever the filter changes or the active tab leaves documents.
  useEffect(() => { setSelectedIds(new Set()); }, [filter]);
  useEffect(() => {
    if (activeTab !== 'documents') setSelectedIds(new Set());
  }, [activeTab]);

  if (loading) return <SafetySkeleton />;
  if (forbidden) return <SafetyForbidden onBack={() => navigate(`/projects/${projectId}/control?workMode=structure`)} />;
  if (flagOff) return <SafetyFlagOff onBack={() => navigate(`/projects/${projectId}/control?workMode=structure`)} />;

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

  const activeFilterCount = countActiveFilters(filter);
  const hasActiveFilter = activeFilterCount > 0;
  const isWriter = SAFETY_WRITERS.includes(project?.my_role);

  const docItems = docs.items || [];
  const allSelected = docItems.length > 0 && docItems.every((d) => selectedIds.has(d.id));

  const toggleOne = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(docItems.map((d) => d.id)));
    }
  };

  const clearFilter = () => setFilter(EMPTY_FILTER);

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    setBulkConfirmOpen(false);
    setBulkDeleting(true);
    const ids = Array.from(selectedIds);
    const results = await Promise.allSettled(
      ids.map((id) => safetyService.deleteDocument(projectId, id))
    );
    const failed = results.filter((r) => r.status === 'rejected').length;
    setBulkDeleting(false);
    setSelectedIds(new Set());
    if (failed > 0) {
      toast.error(`${failed} מתוך ${ids.length} לא נמחקו`);
    } else {
      toast.success(`${ids.length} ליקויים נמחקו`);
    }
    // Re-trigger the documents refetch effect with the same filter object.
    setFilter((f) => ({ ...f }));
  };

  // After a create/edit — reload the affected list + the score (a defect changes
  // the score; a worker can change the "untrained" count). Best-effort: a refresh
  // failure does not undo the save (the toast already confirmed it).
  const buildDocParams = () => {
    const params = { limit: 50 };
    Object.entries(filter).forEach(([k, v]) => {
      if (v != null && v !== '') params[k] = v;
    });
    return params;
  };

  const reloadDocuments = async () => {
    try {
      const [docsResp, scoreResp] = await Promise.all([
        safetyService.listDocuments(projectId, buildDocParams()),
        safetyService.getScore(projectId, true).catch(() => null),
      ]);
      setDocs(docsResp || { items: [], total: 0 });
      if (scoreResp) setScoreData(scoreResp);
    } catch (e) {
      toast.error('שגיאה ברענון רשימת הליקויים');
    }
  };

  const reloadTasks = async () => {
    try {
      const tasksResp = await safetyService.listTasks(projectId, { limit: 50 });
      setTasks(tasksResp || { items: [], total: 0 });
    } catch (e) {
      toast.error('שגיאה ברענון רשימת המשימות');
    }
  };

  const reloadWorkers = async () => {
    try {
      const [workersResp, scoreResp] = await Promise.all([
        safetyService.listWorkers(projectId, { limit: 50 }),
        safetyService.getScore(projectId, true).catch(() => null),
      ]);
      setWorkers(workersResp || { items: [], total: 0 });
      if (scoreResp) setScoreData(scoreResp);
    } catch (e) {
      toast.error('שגיאה ברענון רשימת העובדים');
    }
  };

  const reloadTrainings = async () => {
    try {
      const [trainingsResp, scoreResp] = await Promise.all([
        safetyService.listTrainings(projectId, { limit: 50 }),
        safetyService.getScore(projectId, true).catch(() => null),
      ]);
      setTrainings(trainingsResp || { items: [], total: 0 });
      if (scoreResp) setScoreData(scoreResp);
    } catch (e) {
      toast.error('שגיאה ברענון רשימת ההדרכות');
    }
  };

  const reloadIncidents = async () => {
    try {
      const [incidentsResp, scoreResp] = await Promise.all([
        safetyService.listIncidents(projectId, { limit: 50 }),
        safetyService.getScore(projectId, true).catch(() => null),
      ]);
      setIncidents(incidentsResp || { items: [], total: 0 });
      if (scoreResp) setScoreData(scoreResp);
    } catch (e) {
      toast.error('שגיאה ברענון רשימת האירועים');
    }
  };

  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 pb-16">
      <div className="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-2 sticky top-0 z-20">
        <button
          onClick={() => navigate(`/projects/${projectId}/control?workMode=structure`)}
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

        {isWriter && (
          <button
            type="button"
            onClick={() => setAddChooserOpen(true)}
            className="px-3 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 flex items-center gap-1 min-h-[44px]"
          >
            <Plus className="w-4 h-4" />
            הוסף
          </button>
        )}

        <SafetyExportMenu
          projectId={projectId}
          currentFilter={filter}
          hasActiveFilter={hasActiveFilter}
        />

        <button
          type="button"
          onClick={() => setFilterOpen(true)}
          className="px-3 py-2 text-sm rounded-lg border border-slate-200 hover:bg-slate-50 flex items-center gap-1 min-h-[44px]"
        >
          <Filter className="w-4 h-4" />
          סינון
          {activeFilterCount > 0 && (
            <span className="bg-blue-600 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center">
              {activeFilterCount}
            </span>
          )}
        </button>

        {cacheAge > 0 && (
          <p className="hidden sm:block text-[11px] text-slate-400 ml-1">
            עודכן לפני {Math.max(1, Math.round(cacheAge / 60))} דק׳
          </p>
        )}
      </div>

      <div className="max-w-6xl mx-auto px-4 py-5 space-y-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} dir="rtl" className="space-y-6">
          <Card className="p-0 overflow-hidden bg-white shadow-sm">
            <TabsList className="w-full justify-start rounded-none border-b bg-slate-50 p-0 h-auto overflow-x-auto flex">
              <TabsTrigger
                value="overview"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                סקירה
              </TabsTrigger>
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
              <TabsTrigger
                value="trainings"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                הדרכות ({trainings.total})
              </TabsTrigger>
              <TabsTrigger
                value="incidents"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                אירועים ({incidents.total})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="documents" className="p-0 m-0">
              <DocumentsList
                items={docItems}
                selectedIds={selectedIds}
                onToggle={toggleOne}
                onSelectAll={toggleSelectAll}
                allSelected={allSelected}
                hasActiveFilter={hasActiveFilter}
                onClearFilter={clearFilter}
                isWriter={isWriter}
                onEdit={(d) => setDocForm({ open: true, record: d })}
                onOpenDetail={(d) => setDetailDoc(d)}
              />
            </TabsContent>
            <TabsContent value="tasks" className="p-0 m-0">
              <TasksList
                items={tasks.items}
                isWriter={isWriter}
                onEdit={(t) => setTaskForm({ open: true, record: t })}
              />
            </TabsContent>
            <TabsContent value="workers" className="p-0 m-0">
              <WorkersList
                items={workers.items}
                isWriter={isWriter}
                onEdit={(w) => setWorkerForm({ open: true, record: w })}
                onOpenCard={(w) => setWorkerCard(w)}
              />
            </TabsContent>
            <TabsContent value="trainings" className="p-0 m-0">
              <TrainingsList
                items={trainings.items}
                workers={workers.items}
                isWriter={isWriter}
                onEdit={(t) => setTrainingForm({ open: true, record: t })}
              />
            </TabsContent>
            <TabsContent value="incidents" className="p-0 m-0">
              <IncidentsList
                items={incidents.items}
                workers={workers.items}
                isWriter={isWriter}
                onEdit={(i) => setIncidentForm({ open: true, record: i })}
              />
            </TabsContent>
          </Card>

          <TabsContent value="overview" className="p-0 m-0 space-y-6">
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
          </TabsContent>
        </Tabs>
      </div>

      <SafetyFilterSheet
        open={filterOpen}
        onOpenChange={setFilterOpen}
        value={filter}
        onApply={(next) => { setFilter(next); setFilterOpen(false); }}
        onClear={clearFilter}
        companies={companies}
        users={users}
      />

      <SafetyDocumentForm
        projectId={projectId}
        document={docForm.record}
        open={docForm.open}
        onClose={() => setDocForm({ open: false, record: null })}
        onSaved={reloadDocuments}
      />

      <SafetyDocumentDetail
        doc={detailDoc}
        open={!!detailDoc}
        onClose={() => setDetailDoc(null)}
        isWriter={isWriter}
        companies={companies}
        onEdit={(d) => { setDetailDoc(null); setDocForm({ open: true, record: d }); }}
      />

      <SafetyWorkerForm
        projectId={projectId}
        worker={workerForm.record}
        open={workerForm.open}
        onClose={() => setWorkerForm({ open: false, record: null })}
        onSaved={(w) => {
          const wasEdit = !!workerForm.record;
          reloadWorkers();
          if (!wasEdit && w?.id) {
            setWorkerChain({ workerId: w.id, workerName: w.full_name || '', count: 0 });
          }
        }}
      />

      <SafetyTaskForm
        projectId={projectId}
        task={taskForm.record}
        open={taskForm.open}
        onClose={() => setTaskForm({ open: false, record: null })}
        onSaved={reloadTasks}
        myRole={project?.my_role}
      />

      <SafetyTrainingForm
        projectId={projectId}
        training={trainingForm.record}
        open={trainingForm.open}
        onClose={() => { setTrainingForm({ open: false, record: null }); setTrainingCardLock(null); }}
        onSaved={() => {
          setTrainingCardLock(null);
          reloadTrainings();
          if (!trainingForm.record && workerChain) {
            setWorkerChain((prev) => (prev ? { ...prev, count: prev.count + 1 } : prev));
          }
        }}
        workers={workers.items}
        lockedWorker={(!trainingForm.record && trainingCardLock)
          ? { id: trainingCardLock.id, name: trainingCardLock.full_name }
          : (!trainingForm.record && workerChain)
            ? { id: workerChain.workerId, name: workerChain.workerName }
            : null}
      />

      <SafetyIncidentForm
        projectId={projectId}
        incident={incidentForm.record}
        open={incidentForm.open}
        onClose={() => setIncidentForm({ open: false, record: null })}
        onSaved={reloadIncidents}
        workers={workers.items}
      />

      <SafetyWorkerCard
        projectId={projectId}
        worker={workerCard}
        open={!!workerCard}
        onClose={() => setWorkerCard(null)}
        isWriter={isWriter}
        companies={companies}
        onEditWorker={(w) => { setWorkerCard(null); setWorkerForm({ open: true, record: w }); }}
        onAddTraining={(w) => {
          setWorkerCard(null);
          setWorkerChain(null);
          setTrainingCardLock(w);
          setTrainingForm({ open: true, record: null });
        }}
      />

      {activeTab === 'documents' && selectedIds.size > 0 && (
        <SafetyBulkActionBar
          count={selectedIds.size}
          onDelete={() => setBulkConfirmOpen(true)}
          onClear={() => setSelectedIds(new Set())}
          deleting={bulkDeleting}
        />
      )}

      <AlertDialog open={bulkConfirmOpen} onOpenChange={setBulkConfirmOpen}>
        <AlertDialogContent dir="rtl">
          <AlertDialogHeader>
            <AlertDialogTitle>מחיקת ליקויים</AlertDialogTitle>
            <AlertDialogDescription>
              האם למחוק {selectedIds.size} ליקויים נבחרים? לא ניתן לבטל את הפעולה.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>ביטול</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleBulkDelete}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              מחק
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        open={!!workerChain && !trainingForm.open}
        onOpenChange={() => {}}
        modal={false}
      >
        <DialogContent
          dir="rtl"
          className="max-w-sm w-[calc(100%-2rem)] [&>button]:hidden"
          onInteractOutside={(e) => e.preventDefault()}
          onPointerDownOutside={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle className="text-right">
              {workerChain?.count === 0
                ? `להוסיף הדרכות לעובד ${workerChain?.workerName || ''}?`
                : 'נוספה הדרכה ✓ להוסיף הדרכה נוספת?'}
            </DialogTitle>
          </DialogHeader>
          <DialogFooter className="flex flex-row-reverse gap-2 sm:justify-start">
            <Button
              type="button"
              className="min-h-[44px]"
              onClick={() => setTrainingForm({ open: true, record: null })}
            >
              הוסף הדרכה
            </Button>
            <Button
              type="button"
              variant="outline"
              className="min-h-[44px]"
              onClick={() => setWorkerChain(null)}
            >
              לא עכשיו
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={addChooserOpen} onOpenChange={() => {}} modal={false}>
        <DialogContent
          dir="rtl"
          className="max-w-sm w-[calc(100%-2rem)] [&>button]:hidden"
          onInteractOutside={(e) => e.preventDefault()}
          onPointerDownOutside={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle className="text-right">מה להוסיף?</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Button
              type="button"
              variant="outline"
              className="w-full justify-start gap-3 min-h-[48px]"
              onClick={() => { setAddChooserOpen(false); setDocForm({ open: true, record: null }); }}
            >
              <ShieldAlert className="w-4 h-4" />
              ליקוי
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full justify-start gap-3 min-h-[48px]"
              onClick={() => { setAddChooserOpen(false); setTaskForm({ open: true, record: null }); }}
            >
              <Clock className="w-4 h-4" />
              משימה
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full justify-start gap-3 min-h-[48px]"
              onClick={() => { setAddChooserOpen(false); setWorkerForm({ open: true, record: null }); }}
            >
              <Users className="w-4 h-4" />
              עובד
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full justify-start gap-3 min-h-[48px]"
              onClick={() => { setAddChooserOpen(false); setTrainingForm({ open: true, record: null }); }}
            >
              <GraduationCap className="w-4 h-4" />
              הדרכה
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full justify-start gap-3 min-h-[48px]"
              onClick={() => { setAddChooserOpen(false); setIncidentForm({ open: true, record: null }); }}
            >
              <AlertCircle className="w-4 h-4" />
              אירוע
            </Button>
          </div>
          <DialogFooter className="flex flex-row-reverse gap-2 sm:justify-start">
            <Button
              type="button"
              variant="outline"
              className="min-h-[44px]"
              onClick={() => setAddChooserOpen(false)}
            >
              ביטול
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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

// Row thumbnail — first display url, falling back to a neutral placeholder both
// when there is no photo and when the (per-GET, expiry-prone) url fails to load,
// so a stale preview never shows a broken-image glyph.
function DocThumb({ url }) {
  const [broken, setBroken] = useState(false);
  if (url && !broken) {
    return (
      <img
        src={url}
        alt=""
        onError={() => setBroken(true)}
        className="w-11 h-11 rounded-lg object-cover border border-slate-200 shrink-0"
      />
    );
  }
  return (
    <div className="w-11 h-11 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0">
      <Camera className="w-4 h-4 text-slate-300" />
    </div>
  );
}

function DocumentsList({
  items, selectedIds, onToggle, onSelectAll, allSelected,
  hasActiveFilter, onClearFilter, isWriter, onEdit, onOpenDetail,
}) {
  if (!items?.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-slate-400">
        <ShieldAlert className="w-10 h-10 mb-2" />
        <p className="text-sm font-medium">
          {hasActiveFilter ? 'לא נמצאו ליקויים המתאימים לסינון' : 'אין ליקויים פתוחים'}
        </p>
        {hasActiveFilter && (
          <button
            type="button"
            onClick={onClearFilter}
            className="mt-3 text-sm text-blue-600 hover:underline"
          >
            נקה סינון
          </button>
        )}
      </div>
    );
  }
  return (
    <>
      <div className="px-4 py-2 border-b border-slate-100 bg-slate-50 flex items-center gap-3">
        <input
          type="checkbox"
          aria-label="בחר הכל"
          checked={allSelected}
          onChange={onSelectAll}
          className="w-5 h-5 cursor-pointer accent-blue-600"
        />
        <span className="text-xs text-slate-600">בחר הכל</span>
        {selectedIds.size > 0 && (
          <span className="text-xs text-slate-500 mr-auto">
            נבחרו {selectedIds.size} מתוך {items.length}
          </span>
        )}
      </div>
      <ul className="divide-y divide-slate-100">
        {items.map((d) => (
          <li
            key={d.id}
            role="button"
            onClick={() => onOpenDetail(d)}
            className="px-4 py-3 flex items-start gap-3 hover:bg-slate-50 cursor-pointer"
          >
            <input
              type="checkbox"
              aria-label={`בחר ליקוי ${d.title || ''}`}
              checked={selectedIds.has(d.id)}
              onChange={(e) => { e.stopPropagation(); onToggle(d.id); }}
              onClick={(e) => e.stopPropagation()}
              className="w-5 h-5 mt-0.5 cursor-pointer accent-blue-600 shrink-0"
            />
            <DocThumb url={d.photo_display_urls?.[0]} />
            <Badge className={SEVERITY_COLOR[d.severity] || 'bg-slate-100 text-slate-700'}>
              {SEVERITY_HE[d.severity] || '—'}
            </Badge>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-slate-900 truncate">{d.title}</p>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <Badge className="bg-slate-100 text-slate-700 font-normal">
                  {DOC_STATUS_HE[d.status] || d.status}
                </Badge>
                <span className="text-xs text-slate-500 truncate">{d.location || 'ללא מיקום'}</span>
              </div>
            </div>
            <time className="text-xs text-slate-400 shrink-0">
              {(d.found_at || '').slice(0, 10)}
            </time>
            {isWriter && (
              <button
                type="button"
                aria-label="ערוך ליקוי"
                onClick={(e) => { e.stopPropagation(); onEdit(d); }}
                className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-500 shrink-0"
              >
                <Pencil className="w-4 h-4" />
              </button>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

function TasksList({ items, isWriter, onEdit }) {
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
              {tk.description && (
                <p className="text-xs text-slate-500 truncate mt-0.5">{tk.description}</p>
              )}
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <Badge className="bg-slate-100 text-slate-700 font-normal">
                  {TASK_STATUS_HE[tk.status] || tk.status}
                </Badge>
                {tk.due_at && (
                  <span className="text-xs text-slate-500">יעד {tk.due_at.slice(0, 10)}</span>
                )}
              </div>
            </div>
            {overdue && <Badge className="bg-red-100 text-red-800 shrink-0">באיחור</Badge>}
            {isWriter && (
              <button
                type="button"
                aria-label="ערוך משימה"
                onClick={(e) => { e.stopPropagation(); onEdit(tk); }}
                className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-500 shrink-0"
              >
                <Pencil className="w-4 h-4" />
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function WorkersList({ items, isWriter, onEdit, onOpenCard }) {
  if (!items?.length) return <EmptyState icon={Users} text="אין עובדים רשומים" />;
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((w) => (
        <li
          key={w.id}
          role="button"
          onClick={() => onOpenCard(w)}
          className="px-4 py-3 flex items-center gap-3 hover:bg-slate-50 cursor-pointer">
          <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center shrink-0">
            <Hammer className="w-5 h-5 text-slate-500" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-slate-900 truncate">{w.full_name}</p>
            <p className="text-xs text-slate-500 truncate">
              {w.profession || 'ללא מקצוע'}{w.phone && ` · ${w.phone}`}
            </p>
          </div>
          {isWriter && (
            <button
              type="button"
              aria-label="ערוך עובד"
              onClick={(e) => { e.stopPropagation(); onEdit(w); }}
              className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-500 shrink-0"
            >
              <Pencil className="w-4 h-4" />
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

function TrainingsList({ items, workers, isWriter, onEdit }) {
  if (!items?.length) return <EmptyState icon={GraduationCap} text="אין הדרכות רשומות" />;
  const nameById = new Map((workers || []).map((w) => [w.id, w.full_name]));
  const today = new Date().toISOString().slice(0, 10);
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((tr) => {
        const expired = tr.expires_at && tr.expires_at.slice(0, 10) < today;
        return (
          <li key={tr.id} className="px-4 py-3 flex items-start gap-3 hover:bg-slate-50">
            <div className="flex-1 min-w-0">
              <p className="font-medium text-slate-900 truncate">{tr.training_type}</p>
              <p className="text-xs text-slate-500 truncate mt-0.5">
                {nameById.get(tr.worker_id) || '—'}
                {tr.instructor_name && ` · מדריך: ${tr.instructor_name}`}
              </p>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <span className="text-xs text-slate-500">{(tr.trained_at || '').slice(0, 10)}</span>
                {tr.expires_at && (
                  <span className="text-xs text-slate-500">בתוקף עד {tr.expires_at.slice(0, 10)}</span>
                )}
                {expired && <Badge className="bg-red-100 text-red-800">פג תוקף</Badge>}
                {tr.certificate_display_url && (
                  <a
                    href={tr.certificate_display_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex items-center gap-1 text-xs text-purple-700 hover:underline"
                  >
                    <FileText className="w-3.5 h-3.5" /> תעודה
                  </a>
                )}
              </div>
            </div>
            {isWriter && (
              <button
                type="button"
                aria-label="ערוך הדרכה"
                onClick={(e) => { e.stopPropagation(); onEdit(tr); }}
                className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-500 shrink-0"
              >
                <Pencil className="w-4 h-4" />
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function IncidentsList({ items, workers, isWriter, onEdit }) {
  if (!items?.length) return <EmptyState icon={AlertCircle} text="אין אירועי בטיחות רשומים" />;
  const nameById = new Map((workers || []).map((w) => [w.id, w.full_name]));
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((inc) => (
        <li key={inc.id} className="px-4 py-3 flex items-start gap-3 hover:bg-slate-50">
          <DocThumb url={inc.photo_display_urls?.[0]} />
          <Badge className={SEVERITY_COLOR[inc.severity] || 'bg-slate-100 text-slate-700'}>
            {SEVERITY_HE[inc.severity] || '—'}
          </Badge>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-slate-900 truncate">
              {INCIDENT_TYPE_HE[inc.incident_type] || inc.incident_type}
            </p>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="text-xs text-slate-500">{(inc.occurred_at || '').slice(0, 10)}</span>
              {inc.location && <span className="text-xs text-slate-500">{inc.location}</span>}
              {inc.injured_worker_id && (
                <span className="text-xs text-slate-500">נפגע: {nameById.get(inc.injured_worker_id) || '—'}</span>
              )}
              <Badge className="bg-slate-100 text-slate-700 font-normal">
                {INCIDENT_STATUS_HE[inc.status] || inc.status}
              </Badge>
              {inc.reported_to_authority && <Badge className="bg-amber-100 text-amber-800">דווח לרשות</Badge>}
            </div>
          </div>
          {isWriter && (
            <button
              type="button"
              aria-label="ערוך אירוע"
              onClick={(e) => { e.stopPropagation(); onEdit(inc); }}
              className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-500 shrink-0"
            >
              <Pencil className="w-4 h-4" />
            </button>
          )}
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
