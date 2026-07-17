import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowRight, AlertTriangle, Clock, GraduationCap, AlertCircle,
  Users, TrendingUp, ShieldAlert, Wrench, Filter, Plus, Pencil, Camera, FileText, ClipboardList,
  ChevronLeft, Bell, BookOpen, Eye, Download, QrCode, Send,
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
import { Switch } from '../components/ui/switch';
import { safetyService, projectService, projectCompanyService, userService } from '../services/api';
import { downloadBlob, shareText } from '../utils/fileDownload';
import SafetyScoreGauge from '../components/safety/SafetyScoreGauge';
import SafetyKpiCard from '../components/safety/SafetyKpiCard';
import SafetyFilterSheet, {
  countActiveFilters, EMPTY_FILTER,
  EMPTY_FILTER_WORKERS, EMPTY_FILTER_TASKS, EMPTY_FILTER_TRAININGS, EMPTY_FILTER_INCIDENTS,
  EMPTY_FILTER_OBSERVATIONS,
} from '../components/safety/SafetyFilterSheet';
import SafetyExportMenu from '../components/safety/SafetyExportMenu';
import SafetyBulkActionBar from '../components/safety/SafetyBulkActionBar';
import SafetyWorkerForm from '../components/safety/SafetyWorkerForm';
import SafetyDocumentForm from '../components/safety/SafetyDocumentForm';
import SafetyDocumentDetail from '../components/safety/SafetyDocumentDetail';
import SafetyTaskForm from '../components/safety/SafetyTaskForm';
import SafetyTrainingForm from '../components/safety/SafetyTrainingForm';
import SafetyIncidentForm from '../components/safety/SafetyIncidentForm';
import SafetyWorkerCard from '../components/safety/SafetyWorkerCard';
import SafetyTourCreateDialog from '../components/safety/SafetyTourCreateDialog';
import SafetyTourRunner from '../components/safety/SafetyTourRunner';
import SafetyEquipmentTab from '../components/safety/SafetyEquipmentTab';
import SafetyEquipmentForm from '../components/safety/SafetyEquipmentForm';
import SafetySignaturePad from '../components/safety/SafetySignaturePad';
import SafetyInductionConduct from '../components/safety/SafetyInductionConduct';
import InductionTemplateEditor from '../components/safety/InductionTemplateEditor';
import InductionEvidenceModal from '../components/safety/InductionEvidenceModal';
import { downloadInductionCertificatePdf } from '../utils/inductionCertificate';
import {
  CATEGORY_HE, SEVERITY_HE, DOC_STATUS_HE, TASK_STATUS_HE, INCIDENT_TYPE_HE, INCIDENT_STATUS_HE,
  TOUR_TYPE_HE, TOUR_STATUS_HE,
} from '../components/safety/safetyLabels';

// Writers = the two project roles the safety backend accepts for create/edit
// (safety_router.py SAFETY_WRITERS). The "+"/edit affordances gate on these.
const SAFETY_WRITERS = ['project_manager', 'management_team'];
// ind2-fix4: the induction training type — must match backend INDUCTION_TRAINING_TYPE.
const INDUCTION_TYPE = 'הדרכת אתר';
const VALID_TABS = ['overview', 'documents', 'observations', 'tours', 'tasks', 'workers', 'trainings', 'incidents', 'equipment'];
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
  const [obsDocs, setObsDocs] = useState({ items: [], total: 0 });
  const [tasks, setTasks] = useState({ items: [], total: 0 });
  const [workers, setWorkers] = useState({ items: [], total: 0 });
  const [trainings, setTrainings] = useState({ items: [], total: 0 });
  const [incidents, setIncidents] = useState({ items: [], total: 0 });
  const [flagOff, setFlagOff] = useState(false);
  const [forbidden, setForbidden] = useState(false);
  // Batch safety-w1-alerts — personal WhatsApp expiry-alert opt-out
  // (users.reminder_preferences.safety_expiry via the EXISTING prefs API).
  const [expiryAlertPref, setExpiryAlertPref] = useState(null);
  const [expiryPrefSaving, setExpiryPrefSaving] = useState(false);
  // Batch safety-ind1 — server-resolved editor permission (D3 option b):
  // the "תוכן הדרכת אתר" card gates on GET can_edit, never on FE role maps.
  const [inductionCanEdit, setInductionCanEdit] = useState(false);
  // ind2-fix3 D2: readers (GET succeeded) see the card too — read-only.
  const [inductionCanRead, setInductionCanRead] = useState(false);
  const [inductionEditorOpen, setInductionEditorOpen] = useState(false);
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
  // Adaptive per-tab filters (documents keeps its own `filter` above).
  const [auxFilters, setAuxFilters] = useState({
    observations: EMPTY_FILTER_OBSERVATIONS,
    workers: EMPTY_FILTER_WORKERS,
    tasks: EMPTY_FILTER_TASKS,
    trainings: EMPTY_FILTER_TRAININGS,
    incidents: EMPTY_FILTER_INCIDENTS,
  });
  // Separate view state per aux tab so the global lists (source of truth for the
  // form/card worker & company pickers) are never overwritten by a filtered fetch.
  const [filteredObs, setFilteredObs] = useState(null);
  const [filteredWorkers, setFilteredWorkers] = useState(null);
  const [filteredTasks, setFilteredTasks] = useState(null);
  const [filteredTrainings, setFilteredTrainings] = useState(null);
  const [filteredIncidents, setFilteredIncidents] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [companies, setCompanies] = useState([]);
  const [users, setUsers] = useState([]);

  // Batch safety-p2-1 — create/edit modal state (one pair per entity).
  const [docForm, setDocForm] = useState({ open: false, record: null, kind: 'defect' });
  const [workerForm, setWorkerForm] = useState({ open: false, record: null });
  const [taskForm, setTaskForm] = useState({ open: false, record: null });
  const [trainingForm, setTrainingForm] = useState({ open: false, record: null, renewFrom: null });
  const [incidentForm, setIncidentForm] = useState({ open: false, record: null });
  const [addChooserOpen, setAddChooserOpen] = useState(false);
  // qrg-guest B-FE-2 — issue-dialog open state (button lives in the header)
  const [guestIssueOpen, setGuestIssueOpen] = useState(false);
  const [equipForm, setEquipForm] = useState({ open: false });
  const [workerChain, setWorkerChain] = useState(null);
  const [workerCard, setWorkerCard] = useState(null);
  const [trainingCardLock, setTrainingCardLock] = useState(null);
  const [trainingSignFor, setTrainingSignFor] = useState(null);
  const [inductionFor, setInductionFor] = useState(null); // batch safety-ind2
  const [reInductConfirm, setReInductConfirm] = useState(null); // ind2-fix4 E2
  const [evidenceFor, setEvidenceFor] = useState(null); // ind2-fix4 E4
  // ind3-fix2 F2: training row to highlight/scroll-to after navigating from
  // the worker card. Cleared once the user leaves the trainings tab.
  const [focusTrainingId, setFocusTrainingId] = useState(null);
  const [trainingSigning, setTrainingSigning] = useState(false);
  // Batch safety-p2-1d — read-only detail modal (row tap opens it).
  const [detailDoc, setDetailDoc] = useState(null);
  // Batch safety-p2-4b — safety tours (list + create dialog + checklist runner).
  const [tours, setTours] = useState({ items: [], total: 0 });
  const [tourRunner, setTourRunner] = useState(null);
  const [tourCreateOpen, setTourCreateOpen] = useState(false);
  // Batch safety-p3b — equipment (ציוד). Page owns ONLY the summary (tab
  // counter + category counters); item lists are fetched inside the tab.
  const [equipSummary, setEquipSummary] = useState({ items: [], total: 0 });

  // Skip the filter useEffect's initial run — main useEffect's Promise.all
  // already fetched documents. The ref flips to false after the first real run.
  const filterFetchFirstRun = useRef(true);

  // Batch safety-tabs-overflow — mobile tab-strip affordance. The 9-tab strip
  // overflows left (RTL) on phones with no visual cue; tabsOverflow drives a
  // gradient+chevron indicator shown only while more tabs remain.
  const tabsListRef = useRef(null);
  const [tabsOverflow, setTabsOverflow] = useState(false);

  useEffect(() => {
    const updateTabsOverflow = () => {
      const el = tabsListRef.current;
      if (!el) return;
      const hasOverflow = el.scrollWidth > el.clientWidth + 4;
      // RTL: Chrome/WebKit report scrollLeft as 0 → negative when scrolling.
      // Math.abs() normalizes; "at end" = scrolled the full overflow distance.
      const atEnd = Math.abs(el.scrollLeft) >= el.scrollWidth - el.clientWidth - 4;
      setTabsOverflow(hasOverflow && !atEnd);
    };
    updateTabsOverflow();
    const el = tabsListRef.current;
    if (!el) return undefined;
    el.addEventListener('scroll', updateTabsOverflow, { passive: true });
    window.addEventListener('resize', updateTabsOverflow);
    return () => {
      el.removeEventListener('scroll', updateTabsOverflow);
      window.removeEventListener('resize', updateTabsOverflow);
    };
  }, [loading, flagOff, forbidden]); // re-attach after skeleton → real render

  // Auto-scroll the active trigger into view — covers deep links (?tab=...),
  // BACK restore, and programmatic setActiveTab from KPI cards. Instant (no
  // smooth) so it never fights the user's own scroll.
  useEffect(() => {
    const el = tabsListRef.current;
    if (!el) return;
    const active = el.querySelector('[data-state="active"]');
    if (active && typeof active.scrollIntoView === 'function') {
      active.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }
  }, [activeTab, loading]);

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

        const [scoreResp, docsResp, obsResp, tasksResp, workersResp, trainingsResp, incidentsResp, toursResp, equipResp] = await Promise.all([
          safetyService.getScore(projectId).catch((e) => ({ __err: e })),
          safetyService.listDocuments(projectId, { limit: 50, kind: 'defect' }).catch((e) => ({ __err: e })),
          safetyService.listDocuments(projectId, { limit: 50, kind: 'observation' }).catch((e) => ({ __err: e })),
          safetyService.listTasks(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listWorkers(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listTrainings(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listIncidents(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listTours(projectId, { limit: 100 }).catch((e) => ({ __err: e })),
          safetyService.getEquipmentSummary(projectId).catch((e) => ({ __err: e })),
        ]);
        if (cancelled) return;

        const responses = [scoreResp, docsResp, obsResp, tasksResp, workersResp, trainingsResp, incidentsResp, toursResp, equipResp];
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
        setObsDocs(obsResp || { items: [], total: 0 });
        setTasks(tasksResp || { items: [], total: 0 });
        setWorkers(workersResp || { items: [], total: 0 });
        setTrainings(trainingsResp || { items: [], total: 0 });
        setIncidents(incidentsResp || { items: [], total: 0 });
        setTours(toursResp || { items: [], total: 0 });
        setEquipSummary(equipResp || { items: [], total: 0 });
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
        const params = { limit: 50, kind: 'defect' };
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

  // ind3-fix2 F2: drop the training highlight once the user leaves the tab.
  useEffect(() => {
    if (activeTab !== 'trainings' && focusTrainingId) setFocusTrainingId(null);
  }, [activeTab, focusTrainingId]);

  // Clear selection whenever the filter changes or the active tab leaves documents.
  useEffect(() => { setSelectedIds(new Set()); }, [filter]);
  useEffect(() => {
    if (activeTab !== 'documents') setSelectedIds(new Set());
  }, [activeTab]);

  // Aux per-tab filter refetch (workers/tasks/trainings/incidents). Mirrors the
  // documents effect but writes to a SEPARATE view state; when a tab's filter is
  // empty the view is cleared (null) and the tab falls back to the global list.
  // LIST-ONLY (no score refetch), fail-soft.
  useEffect(() => {
    if (!projectId || loading || flagOff || forbidden) return;
    if (activeTab === 'documents' || activeTab === 'overview' || activeTab === 'tours' || activeTab === 'equipment') return;
    const setFiltered = {
      observations: setFilteredObs,
      workers: setFilteredWorkers,
      tasks: setFilteredTasks,
      trainings: setFilteredTrainings,
      incidents: setFilteredIncidents,
    }[activeTab];
    if (!setFiltered) return;
    const f = auxFilters[activeTab] || {};
    if (countActiveFilters(f) === 0) { setFiltered(null); return; }

    const params = { limit: 50 };
    if (activeTab === 'observations') {
      params.kind = 'observation';
      if (f.category) params.category = f.category;
      if (f.date_from) params.date_from = f.date_from;
      if (f.date_to) params.date_to = f.date_to;
    } else if (activeTab === 'workers') {
      if (f.profession) params.profession = f.profession;
      if (f.company_id) params.company_id = f.company_id;
    } else if (activeTab === 'tasks') {
      if (f.overdue === 'overdue') params.overdue = true;   // overdue wins; omit status
      else if (f.status) params.status = f.status;
      if (f.severity) params.severity = f.severity;
      if (f.assignee_id) params.assignee_id = f.assignee_id;
      if (f.company_id) params.company_id = f.company_id;
    } else if (activeTab === 'trainings') {
      if (f.training_type) params.training_type = f.training_type;
      if (f.worker_id) params.worker_id = f.worker_id;
      if (f.expiry === 'expired') params.expires_before = new Date().toISOString().slice(0, 10);
    } else if (activeTab === 'incidents') {
      if (f.incident_type) params.incident_type = f.incident_type;
      if (f.severity) params.severity = f.severity;
      if (f.reported != null) params.reported_to_authority = f.reported;  // 'true'/'false' → bool
      if (f.injured_worker_id) params.injured_worker_id = f.injured_worker_id;
      if (f.date_from) params.date_from = f.date_from;
      if (f.date_to) params.date_to = f.date_to;
    }

    let cancelled = false;
    (async () => {
      try {
        let resp;
        if (activeTab === 'observations') resp = await safetyService.listDocuments(projectId, params);
        else if (activeTab === 'workers') resp = await safetyService.listWorkers(projectId, params);
        else if (activeTab === 'tasks') resp = await safetyService.listTasks(projectId, params);
        else if (activeTab === 'trainings') resp = await safetyService.listTrainings(projectId, params);
        else if (activeTab === 'incidents') resp = await safetyService.listIncidents(projectId, params);
        if (cancelled || !resp) return;
        setFiltered(resp);
      } catch (e) {
        if (!cancelled) toast.error('שגיאה בטעינת רשימה מסוננת');
      }
    })();
    return () => { cancelled = true; };
  }, [projectId, activeTab, auxFilters, loading, flagOff, forbidden]);

  // Batch safety-w1-alerts — load the personal expiry-alert preference once
  // the project (and thus the viewer's role) is known. MUST live ABOVE the
  // early returns below to keep React hook order stable across renders.
  // Batch safety-ind1 (5b): the alerts card's audience is now the roles the
  // expiry cron actually targets — project_manager + owner (management_team
  // dropped). The pref-load effect follows the SAME condition, otherwise the
  // pref never loads for owners and the card stays hidden (pref === null).
  const alertsAudience = ['project_manager', 'owner'].includes(project?.my_role);
  useEffect(() => {
    if (!alertsAudience) return;
    userService.getReminderPreferences()
      .then((prefs) => setExpiryAlertPref(prefs?.safety_expiry?.enabled !== false))
      .catch(() => {});
  }, [alertsAudience]);

  // Batch safety-ind1 — resolve can_edit server-side (D3 option b). Single
  // GET on mount; 403 (contractor/viewer without org rights) → stays false.
  // MUST live ABOVE the early returns to keep hook order stable.
  useEffect(() => {
    let cancelled = false;
    // ind2-fix3: reset on every project change — a stale true from a
    // previous project must never leak the card into a 403 project.
    setInductionCanRead(false);
    setInductionCanEdit(false);
    safetyService.getInductionTemplate(projectId)
      .then((data) => {
        if (cancelled) return;
        setInductionCanRead(true);
        setInductionCanEdit(data?.can_edit === true);
      })
      .catch(() => {
        if (cancelled) return;
        setInductionCanRead(false);
        setInductionCanEdit(false);
      });
    return () => { cancelled = true; };
  }, [projectId]);

  const toggleExpiryAlerts = async (enabled) => {
    const prev = expiryAlertPref;
    setExpiryAlertPref(enabled);
    setExpiryPrefSaving(true);
    try {
      const result = await userService.updateReminderPreferences({ safety_expiry: { enabled } });
      setExpiryAlertPref(result?.safety_expiry?.enabled !== false);
      toast.success(enabled ? 'התראות פגי תוקף הופעלו' : 'התראות פגי תוקף כובו');
    } catch (err) {
      setExpiryAlertPref(prev);
      toast.error(err.response?.data?.detail || 'שמירת ההעדפה נכשלה');
    } finally {
      setExpiryPrefSaving(false);
    }
  };

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

  // Adaptive filter: current tab's filter value + count, and the list each aux
  // tab shows (filtered view when a filter is active, else the global list).
  const isDocTab = activeTab === 'documents';
  const activeFilterValue = isDocTab ? filter : (auxFilters[activeTab] || {});
  const activeFilterCountTab = isDocTab
    ? activeFilterCount
    : countActiveFilters(auxFilters[activeTab] || {});
  const observationsView = (countActiveFilters(auxFilters.observations) > 0 && filteredObs) ? filteredObs : obsDocs;
  const workersView = (countActiveFilters(auxFilters.workers) > 0 && filteredWorkers) ? filteredWorkers : workers;
  const tasksView = (countActiveFilters(auxFilters.tasks) > 0 && filteredTasks) ? filteredTasks : tasks;
  const trainingsView = (countActiveFilters(auxFilters.trainings) > 0 && filteredTrainings) ? filteredTrainings : trainings;
  const incidentsView = (countActiveFilters(auxFilters.incidents) > 0 && filteredIncidents) ? filteredIncidents : incidents;

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
    const params = { limit: 50, kind: 'defect' };
    Object.entries(filter).forEach(([k, v]) => {
      if (v != null && v !== '') params[k] = v;
    });
    return params;
  };

  const buildObsParams = () => {
    const params = { limit: 50, kind: 'observation' };
    const f = auxFilters.observations || {};
    if (f.category) params.category = f.category;
    if (f.date_from) params.date_from = f.date_from;
    if (f.date_to) params.date_to = f.date_to;
    return params;
  };

  // A document save can be a defect OR an observation, so refresh BOTH lists (+
  // the score, which only defects move). Observations never affect the score but
  // refetching the global obs list keeps the תיעוד tab in sync after an edit.
  const reloadDocuments = async () => {
    try {
      const [docsResp, obsResp, scoreResp] = await Promise.all([
        safetyService.listDocuments(projectId, buildDocParams()),
        safetyService.listDocuments(projectId, { limit: 50, kind: 'observation' }).catch(() => null),
        safetyService.getScore(projectId, true).catch(() => null),
      ]);
      setDocs(docsResp || { items: [], total: 0 });
      if (obsResp) setObsDocs(obsResp);
      if (scoreResp) setScoreData(scoreResp);
      // Keep the filtered obs view fresh when a תיעוד filter is active.
      if (countActiveFilters(auxFilters.observations) > 0) {
        safetyService.listDocuments(projectId, buildObsParams())
          .then((r) => setFilteredObs(r || { items: [], total: 0 }))
          .catch(() => {});
      }
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

  const reloadTours = async () => {
    try {
      const toursResp = await safetyService.listTours(projectId, { limit: 100 });
      setTours(toursResp || { items: [], total: 0 });
    } catch (e) {
      toast.error('שגיאה ברענון רשימת הסיורים');
    }
  };

  const reloadEquipmentSummary = async () => {
    try {
      const resp = await safetyService.getEquipmentSummary(projectId);
      setEquipSummary(resp || { items: [], total: 0 });
    } catch (e) {
      toast.error('שגיאה ברענון נתוני ציוד');
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

        {/* qrg-guest — one-day guest pass issuing (workers tab only) */}
        {isWriter && activeTab === 'workers' && (
          <button
            type="button"
            onClick={() => setGuestIssueOpen(true)}
            className="px-3 py-2 text-sm rounded-lg bg-amber-500 text-white hover:bg-amber-600 flex items-center gap-1 min-h-[44px]"
          >
            <QrCode className="w-4 h-4" />
            הנפק קוד אורח
          </button>
        )}

        <SafetyExportMenu
          projectId={projectId}
          currentFilter={filter}
          hasActiveFilter={hasActiveFilter}
        />

        {activeTab !== 'overview' && activeTab !== 'tours' && activeTab !== 'equipment' && (
          <button
            type="button"
            onClick={() => setFilterOpen(true)}
            className="px-3 py-2 text-sm rounded-lg border border-slate-200 hover:bg-slate-50 flex items-center gap-1 min-h-[44px]"
          >
            <Filter className="w-4 h-4" />
            סינון
            {activeFilterCountTab > 0 && (
              <span className="bg-blue-600 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center">
                {activeFilterCountTab}
              </span>
            )}
          </button>
        )}

        {cacheAge > 0 && (
          <p className="hidden sm:block text-[11px] text-slate-400 ml-1">
            עודכן לפני {Math.max(1, Math.round(cacheAge / 60))} דק׳
          </p>
        )}
      </div>

      <div className="max-w-6xl mx-auto px-4 py-5 space-y-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} dir="rtl" className="space-y-6">
          <Card className="p-0 overflow-hidden bg-white shadow-sm">
            <div className="relative">
            <TabsList ref={tabsListRef} className="w-full justify-start rounded-none border-b bg-slate-50 p-0 h-auto overflow-x-auto flex">
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
                value="observations"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                תיעוד ({observationsView.total})
              </TabsTrigger>
              <TabsTrigger
                value="tours"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                סיורים ({tours.total})
              </TabsTrigger>
              <TabsTrigger
                value="tasks"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                משימות ({tasksView.total})
              </TabsTrigger>
              <TabsTrigger
                value="workers"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                עובדים ({workersView.total})
              </TabsTrigger>
              <TabsTrigger
                value="trainings"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                הדרכות ({trainingsView.group_total ?? trainingsView.total})
              </TabsTrigger>
              <TabsTrigger
                value="incidents"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                אירועים ({incidentsView.total})
              </TabsTrigger>
              <TabsTrigger
                value="equipment"
                className="rounded-none data-[state=active]:bg-white data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-blue-500 px-5 py-3"
              >
                ציוד ({equipSummary.total})
              </TabsTrigger>
            </TabsList>
            {tabsOverflow && (
              <div className="pointer-events-none absolute inset-y-0 left-0 w-10 flex items-center justify-start bg-gradient-to-r from-slate-50 via-slate-50/80 to-transparent">
                <ChevronLeft className="w-4 h-4 text-slate-400" />
              </div>
            )}
            </div>

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
                onEdit={(d) => setDocForm({ open: true, record: d, kind: 'defect' })}
                onOpenDetail={(d) => setDetailDoc(d)}
              />
            </TabsContent>
            <TabsContent value="observations" className="p-0 m-0">
              <ObservationsList
                items={observationsView.items}
                hasActiveFilter={countActiveFilters(auxFilters.observations) > 0}
                onClearFilter={() => setAuxFilters((m) => ({ ...m, observations: EMPTY_FILTER_OBSERVATIONS }))}
                isWriter={isWriter}
                onEdit={(d) => setDocForm({ open: true, record: d, kind: 'observation' })}
                onOpenDetail={(d) => setDetailDoc(d)}
              />
              {/* qrg1 — entry-gate scan log (writers only), self-fetching */}
              {isWriter && activeTab === 'observations' && (
                <GateScansSection projectId={projectId} />
              )}
            </TabsContent>
            <TabsContent value="tours" className="p-0 m-0">
              <ToursList
                items={tours.items}
                isWriter={isWriter}
                onOpen={(tr) => setTourRunner(tr)}
                onCreate={() => setTourCreateOpen(true)}
              />
            </TabsContent>
            <TabsContent value="tasks" className="p-0 m-0">
              <TasksList
                items={tasksView.items}
                isWriter={isWriter}
                onEdit={(t) => setTaskForm({ open: true, record: t })}
              />
            </TabsContent>
            <TabsContent value="workers" className="p-0 m-0">
              <WorkersList
                items={workersView.items}
                isWriter={isWriter}
                onEdit={(w) => setWorkerForm({ open: true, record: w })}
                onOpenCard={(w) => setWorkerCard(w)}
                onInduct={(w) => {
                  // ind2-fix4 E2: valid induction → confirm before re-conduct
                  const today = new Date().toISOString().slice(0, 10);
                  if (w.induction_valid_until && w.induction_valid_until.slice(0, 10) >= today) {
                    setReInductConfirm(w);
                  } else {
                    setInductionFor(w);
                  }
                }}
              />
              {/* qrg-guest — issued guest passes (writers only), self-fetching */}
              {isWriter && activeTab === 'workers' && (
                <GuestPassSection
                  projectId={projectId}
                  projectName={project?.name || ''}
                  issueOpen={guestIssueOpen}
                  onIssueOpenChange={setGuestIssueOpen}
                />
              )}
            </TabsContent>
            <TabsContent value="trainings" className="p-0 m-0">
              <TrainingsList
                items={trainingsView.items}
                workers={workers.items}
                isWriter={isWriter}
                highlightId={focusTrainingId}
                onEdit={(t) => setTrainingForm({ open: true, record: t, renewFrom: null })}
                onRenew={(t) => setTrainingForm({ open: true, record: null, renewFrom: t })}
                onSign={(t) => setTrainingSignFor(t)}
                onViewEvidence={(t) => setEvidenceFor(t)}
                onDownloadCertificate={async (t) => {
                  try {
                    await downloadInductionCertificatePdf(
                      projectId, t.id,
                      (workers.items || []).find((x) => x.id === t.worker_id)?.full_name);
                  } catch (e) {
                    toast.error('הורדת התעודה נכשלה');
                  }
                }}
                onReconduct={(t) => {
                  const w = (workers.items || []).find((x) => x.id === t.worker_id);
                  // Fallback: the workers page is capped — a minimal worker
                  // object (id only) still lets the ceremony run; the backend
                  // validates the worker id on conduct.
                  setInductionFor(w || { id: t.worker_id, full_name: t.worker_name || '' });
                }}
              />
            </TabsContent>
            <TabsContent value="incidents" className="p-0 m-0">
              <IncidentsList
                items={incidentsView.items}
                workers={workers.items}
                isWriter={isWriter}
                onEdit={(i) => setIncidentForm({ open: true, record: i })}
              />
            </TabsContent>
            <TabsContent value="equipment" className="p-0 m-0">
              <SafetyEquipmentTab
                projectId={projectId}
                isWriter={isWriter}
                summary={equipSummary}
                onChanged={reloadEquipmentSummary}
              />
            </TabsContent>
          </Card>

          <TabsContent value="overview" className="p-0 m-0 space-y-6">
            {alertsAudience && expiryAlertPref !== null && (
              <Card className="p-4 bg-white shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
                      <Bell className="w-4 h-4 text-blue-600" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900">קבלת התראות וואטסאפ על פגי תוקף</p>
                      <p className="text-xs text-slate-500">תזכורת אישית 30/14/7/0 ימים לפני פקיעת הדרכות ובדיקות ציוד</p>
                    </div>
                  </div>
                  <Switch
                    checked={expiryAlertPref}
                    onCheckedChange={toggleExpiryAlerts}
                    disabled={expiryPrefSaving}
                    dir="ltr"
                  />
                </div>
              </Card>
            )}
            {inductionCanRead && (
              <Card
                className="p-4 bg-white shadow-sm cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => setInductionEditorOpen(true)}
                data-testid="induction-template-card"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center shrink-0">
                      <BookOpen className="w-4 h-4 text-emerald-600" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900">תוכן הדרכת אתר</p>
                      <p className="text-xs text-slate-500">התוכן שעובדים קוראים וחותמים עליו בקליטה</p>
                    </div>
                  </div>
                  <ChevronLeft className="w-4 h-4 text-slate-400 shrink-0" />
                </div>
              </Card>
            )}
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
        tab={activeTab}
        value={activeFilterValue}
        onApply={(next) => {
          if (isDocTab) setFilter(next);
          else setAuxFilters((m) => ({ ...m, [activeTab]: next }));
          setFilterOpen(false);
        }}
        onClear={() => {
          if (isDocTab) {
            setFilter(EMPTY_FILTER);
          } else {
            const empties = {
              observations: EMPTY_FILTER_OBSERVATIONS,
              workers: EMPTY_FILTER_WORKERS, tasks: EMPTY_FILTER_TASKS,
              trainings: EMPTY_FILTER_TRAININGS, incidents: EMPTY_FILTER_INCIDENTS,
            };
            setAuxFilters((m) => ({ ...m, [activeTab]: empties[activeTab] }));
          }
          setFilterOpen(false);
        }}
        companies={companies}
        users={users}
        workers={workers.items}
      />

      <SafetyDocumentForm
        projectId={projectId}
        document={docForm.record}
        kind={docForm.kind}
        open={docForm.open}
        onClose={() => setDocForm({ open: false, record: null, kind: 'defect' })}
        onSaved={reloadDocuments}
      />

      <SafetyDocumentDetail
        doc={detailDoc}
        open={!!detailDoc}
        onClose={() => setDetailDoc(null)}
        isWriter={isWriter}
        companies={companies}
        onEdit={(d) => { setDetailDoc(null); setDocForm({ open: true, record: d, kind: d.kind || 'defect' }); }}
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
        renewFrom={trainingForm.renewFrom}
        open={trainingForm.open}
        onClose={() => { setTrainingForm({ open: false, record: null, renewFrom: null }); setTrainingCardLock(null); }}
        onSaved={(saved) => {
          const wasRenewal = !!trainingForm.renewFrom;
          setTrainingCardLock(null);
          reloadTrainings();
          if (!trainingForm.record && !wasRenewal && workerChain) {
            setWorkerChain((prev) => (prev ? { ...prev, count: prev.count + 1 } : prev));
          }
          if (wasRenewal && saved?.id) setTrainingSignFor(saved);
        }}
        workers={workers.items}
        lockedWorker={(!trainingForm.record && !trainingForm.renewFrom && trainingCardLock)
          ? { id: trainingCardLock.id, name: trainingCardLock.full_name }
          : (!trainingForm.record && !trainingForm.renewFrom && workerChain)
            ? { id: workerChain.workerId, name: workerChain.workerName }
            : null}
      />

      <SafetyInductionConduct
        projectId={projectId}
        worker={inductionFor}
        open={!!inductionFor}
        onClose={() => setInductionFor(null)}
        onConducted={() => { reloadTrainings(); reloadWorkers(); }}
      />

      {/* ind2-fix4 E2: confirm before re-conducting a still-valid induction */}
      <AlertDialog open={!!reInductConfirm} onOpenChange={(o) => { if (!o) setReInductConfirm(null); }}>
        <AlertDialogContent dir="rtl">
          <AlertDialogHeader>
            <AlertDialogTitle>הדרכת אתר בתוקף</AlertDialogTitle>
            <AlertDialogDescription>
              לעובד יש הדרכת אתר בתוקף עד {reInductConfirm?.induction_valid_until?.slice(0, 10)}. להעביר הדרכה מחדש?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>ביטול</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                const w = reInductConfirm;
                setReInductConfirm(null);
                setInductionFor(w);
              }}
            >
              העבר מחדש
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ind2-fix4 E4: read-only evidence of a signed induction */}
      <InductionEvidenceModal
        projectId={projectId}
        training={evidenceFor}
        workers={workers.items}
        open={!!evidenceFor}
        onClose={() => setEvidenceFor(null)}
      />

      <SafetySignaturePad
        open={!!trainingSignFor}
        onClose={() => { if (!trainingSigning) setTrainingSignFor(null); }}
        slotLabel={`חתימת העובד — ${workers.items?.find((w) => w.id === trainingSignFor?.worker_id)?.full_name || ''}`}
        defaultName={workers.items?.find((w) => w.id === trainingSignFor?.worker_id)?.full_name || ''}
        saving={trainingSigning}
        onSave={async ({ signerName, signatureType, typedName, blob }) => {
          setTrainingSigning(true);
          try {
            await safetyService.signTraining(projectId, trainingSignFor.id, { signerName, signatureType, typedName, blob });
            toast.success('החתימה נשמרה');
            setTrainingSignFor(null);
            reloadTrainings();
          } catch (e) {
            const d = e?.response?.data?.detail;
            toast.error(typeof d === 'string' ? d : 'שגיאה בשמירת החתימה');
          } finally {
            setTrainingSigning(false);
          }
        }}
      />

      <SafetyIncidentForm
        projectId={projectId}
        incident={incidentForm.record}
        open={incidentForm.open}
        onClose={() => setIncidentForm({ open: false, record: null })}
        onSaved={reloadIncidents}
        workers={workers.items}
      />

      <SafetyEquipmentForm
        projectId={projectId}
        item={null}
        presetCategory={null}
        open={equipForm.open}
        onClose={() => setEquipForm({ open: false })}
        onSaved={(saved) => {
          reloadEquipmentSummary();
          const next = new URLSearchParams(searchParams);
          next.set('tab', 'equipment');
          if (saved?.category) next.set('equipCat', saved.category);
          setSearchParams(next);
        }}
      />

      <SafetyWorkerCard
        projectId={projectId}
        projectName={project?.name || ''}
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
          setTrainingForm({ open: true, record: null, renewFrom: null });
        }}
        /* ind3-fix2 F2: training rows in the worker card navigate — */
        onOpenEvidence={(t) => { setWorkerCard(null); setEvidenceFor(t); }}
        onOpenTraining={(t) => {
          setWorkerCard(null);
          setFocusTrainingId(t.id);
          setActiveTab('trainings');
        }}
        /* qrg1 — block toggled in the card → refresh the list chip */
        onBlockChanged={() => reloadWorkers()}
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
              onClick={() => setTrainingForm({ open: true, record: null, renewFrom: null })}
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
              onClick={() => { setAddChooserOpen(false); setDocForm({ open: true, record: null, kind: 'defect' }); }}
            >
              <ShieldAlert className="w-4 h-4" />
              ליקוי
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full justify-start gap-3 min-h-[48px]"
              onClick={() => { setAddChooserOpen(false); setDocForm({ open: true, record: null, kind: 'observation' }); }}
            >
              <FileText className="w-4 h-4" />
              תיעוד
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
              onClick={() => { setAddChooserOpen(false); setTrainingForm({ open: true, record: null, renewFrom: null }); }}
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
            <Button
              type="button"
              variant="outline"
              className="w-full justify-start gap-3 min-h-[48px]"
              onClick={() => { setAddChooserOpen(false); setTourCreateOpen(true); }}
            >
              <ClipboardList className="w-4 h-4" />
              סיור
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full justify-start gap-3 min-h-[48px]"
              onClick={() => { setAddChooserOpen(false); setEquipForm({ open: true }); }}
            >
              <Wrench className="w-4 h-4" />
              פריט ציוד
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

      <SafetyTourCreateDialog
        projectId={projectId}
        open={tourCreateOpen}
        onClose={() => setTourCreateOpen(false)}
        onCreated={(tour) => {
          setTourCreateOpen(false);
          reloadTours();
          setTourRunner(tour);   // jump straight into the checklist
        }}
      />

      <SafetyTourRunner
        projectId={projectId}
        tour={tourRunner}
        open={!!tourRunner}
        isWriter={isWriter}
        onChanged={(tr) => setTours((prev) => ({
          ...prev,
          items: (prev.items || []).map((x) => (x.id === tr.id ? tr : x)),
        }))}
        onClose={() => { setTourRunner(null); reloadTours(); reloadDocuments(); }}
      />

      <InductionTemplateEditor
        projectId={projectId}
        canEdit={inductionCanEdit}
        open={inductionEditorOpen}
        onOpenChange={setInductionEditorOpen}
      />
    </div>
  );
}

function ToursList({ items = [], isWriter, onOpen, onCreate }) {
  const TOUR_STATUS_BADGE = {
    draft: 'bg-slate-100 text-slate-700',
    pending_signature: 'bg-amber-100 text-amber-800',
    signed: 'bg-green-100 text-green-800',
  };

  // Cemento-style month grouping (spec 6g). With 2-3 tours/day a flat list
  // hits 60-90 rows/month — group by "YYYY-MM" (server already sorts DESC).
  const groups = {};                       // key "YYYY-MM" → tours[]
  for (const tr of items) {
    const key = (tr.tour_date || '').slice(0, 7) || 'unknown';
    (groups[key] = groups[key] || []).push(tr);
  }
  const monthLabel = (key) => {
    const [y, m] = key.split('-').map(Number);
    if (!y || !m) return 'ללא תאריך';
    return new Date(y, m - 1, 1).toLocaleDateString('he-IL', { month: 'long', year: 'numeric' });
  };
  const monthKeys = Object.keys(groups).sort().reverse();   // newest month first

  // Card markup unchanged from the flat list — only the wrapping changed.
  const renderCard = (tr) => {
    const title = tr.tour_type === 'custom' ? (tr.custom_name || 'סיור מותאם') : (TOUR_TYPE_HE[tr.tour_type] || 'סיור');
    const total = (tr.items || []).length;
    const answered = (tr.items || []).filter((it) => it.result != null).length;
    return (
      <button
        key={tr.id}
        type="button"
        onClick={() => onOpen(tr)}
        className="w-full text-right rounded-xl border border-slate-200 bg-white p-4 hover:bg-slate-50 transition-colors flex items-start justify-between gap-3"
      >
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-800 truncate">{title}</p>
          <p className="text-xs text-slate-500 mt-0.5">{tr.tour_date} · נענו {answered}/{total}</p>
        </div>
        <span className={`shrink-0 text-[11px] font-medium rounded-full px-2 py-0.5 ${TOUR_STATUS_BADGE[tr.status] || TOUR_STATUS_BADGE.draft}`}>
          {TOUR_STATUS_HE[tr.status] || tr.status}
        </span>
      </button>
    );
  };

  return (
    <div className="p-4 space-y-4">
      {isWriter && (
        <button
          type="button"
          onClick={onCreate}
          className="w-full min-h-[48px] rounded-xl border-2 border-dashed border-blue-300 bg-blue-50 text-blue-700 font-medium text-sm hover:bg-blue-100 flex items-center justify-center gap-2"
        >
          <Plus className="w-4 h-4" /> סיור חדש
        </button>
      )}
      {items.length === 0 ? (
        <div className="text-center py-12 text-slate-400 text-sm">אין סיורים עדיין</div>
      ) : (
        monthKeys.map((key) => {
          const grp = groups[key];
          // The color IS the status (like Cemento) → chip shows only the number.
          const pendingN = grp.filter((t) => t.status === 'pending_signature').length;
          const draftN = grp.filter((t) => t.status === 'draft').length;
          const signedN = grp.filter((t) => t.status === 'signed').length;
          return (
            <div key={key} className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-slate-700">{monthLabel(key)}</span>
                {pendingN > 0 && (
                  <span className="text-[11px] font-medium rounded-full px-2 py-0.5 bg-amber-100 text-amber-800">{pendingN}</span>
                )}
                {draftN > 0 && (
                  <span className="text-[11px] font-medium rounded-full px-2 py-0.5 bg-slate-100 text-slate-600">{draftN}</span>
                )}
                {signedN > 0 && (
                  <span className="text-[11px] font-medium rounded-full px-2 py-0.5 bg-green-100 text-green-800">{signedN}</span>
                )}
              </div>
              <div className="space-y-3">
                {grp.map(renderCard)}
              </div>
            </div>
          );
        })
      )}
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

// תיעוד (observation) list — mirrors DocumentsList chrome minus the severity/
// status badges, the bulk-select checkboxes and the "select all" header (an
// observation is a photo-first record with no lifecycle). Row tap opens the
// shared read-only detail modal; a green "תיעוד" chip marks the kind.
function ObservationsList({
  items, hasActiveFilter, onClearFilter, isWriter, onEdit, onOpenDetail,
}) {
  if (!items?.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-slate-400">
        <FileText className="w-10 h-10 mb-2" />
        <p className="text-sm font-medium">
          {hasActiveFilter ? 'לא נמצא תיעוד המתאים לסינון' : 'אין תיעוד'}
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
    <ul className="divide-y divide-slate-100">
      {items.map((d) => (
        <li
          key={d.id}
          role="button"
          onClick={() => onOpenDetail(d)}
          className="px-4 py-3 flex items-start gap-3 hover:bg-slate-50 cursor-pointer"
        >
          <DocThumb url={d.photo_display_urls?.[0]} />
          <Badge className="bg-green-100 text-green-800 shrink-0">תיעוד</Badge>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-slate-900 truncate">{d.title}</p>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <Badge className="bg-slate-100 text-slate-700 font-normal">
                {CATEGORY_HE[d.category] || d.category}
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
              aria-label="ערוך תיעוד"
              onClick={(e) => { e.stopPropagation(); onEdit(d); }}
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

// qrg1 — entry-gate scan log ("סריקות כניסה"). Self-fetching, writers only.
// Rendered under the תיעוד tab; newest first; verdict chip per row.
const SCAN_RESULT_HE = {
  green: { label: 'מאושר', cls: 'bg-green-100 text-green-800' },
  red: { label: 'אין כניסה', cls: 'bg-red-100 text-red-800' },
  invalid: { label: 'קוד לא תקף', cls: 'bg-slate-200 text-slate-600' },
};

// qrg1-fix1 B3d — local-date helpers for the preset range chips.
const localDateStr = (d) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};
const SCAN_RANGE_PRESETS = [
  { key: 'today', label: 'היום' },
  { key: '7d', label: '7 ימים' },
  { key: 'month', label: 'החודש' },
  { key: 'all', label: 'הכל' },
];
const scanRangeToDates = (key) => {
  const now = new Date();
  if (key === 'today') { const d = localDateStr(now); return { date_from: d, date_to: d }; }
  if (key === '7d') {
    const from = new Date(now); from.setDate(from.getDate() - 6);
    return { date_from: localDateStr(from), date_to: localDateStr(now) };
  }
  if (key === 'month') {
    return { date_from: localDateStr(new Date(now.getFullYear(), now.getMonth(), 1)), date_to: localDateStr(now) };
  }
  return {};
};

function GateScansSection({ projectId }) {
  const [scans, setScans] = useState({ items: [], total: 0, summary: null, loading: true });
  // Filters: worker select + result select + date-range preset chips.
  const [scanWorkers, setScanWorkers] = useState([]);
  const [workerFilter, setWorkerFilter] = useState('');
  const [resultFilter, setResultFilter] = useState('');
  const [rangeFilter, setRangeFilter] = useState('all');

  // Worker options — fetched once, fail-soft.
  useEffect(() => {
    let cancelled = false;
    safetyService.listWorkers(projectId, { limit: 200 })
      .then((res) => { if (!cancelled) setScanWorkers(res?.items || []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;
    setScans((prev) => ({ ...prev, loading: true }));
    const params = { limit: 50 };
    if (workerFilter) params.worker_id = workerFilter;
    if (resultFilter) params.result = resultFilter;
    Object.assign(params, scanRangeToDates(rangeFilter));
    safetyService.listGateScans(projectId, params)
      .then((res) => {
        if (!cancelled) setScans({ items: res.items || [], total: res.total || 0, summary: res.summary || null, loading: false });
      })
      .catch(() => { if (!cancelled) setScans({ items: [], total: 0, summary: null, loading: false }); });
    return () => { cancelled = true; };
  }, [projectId, workerFilter, resultFilter, rangeFilter]);

  const summary = scans.summary;

  return (
    <div className="border-t border-slate-200">
      <div className="px-4 py-3 flex items-center gap-2 bg-slate-50">
        <QrCode className="w-4 h-4 text-slate-500" />
        <p className="text-sm font-semibold text-slate-700">סריקות כניסה ({scans.total})</p>
      </div>
      {/* qrg1-fix1 B3d — compact RTL filter row + counts strip */}
      <div className="px-4 py-2 space-y-2 border-b border-slate-100">
        <div className="flex gap-2 flex-wrap">
          <select
            value={workerFilter}
            onChange={(e) => setWorkerFilter(e.target.value)}
            aria-label="סינון לפי עובד"
            className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-700 max-w-[46%]"
          >
            <option value="">כל העובדים</option>
            {scanWorkers.map((w) => (
              <option key={w.id} value={w.id}>{w.full_name}</option>
            ))}
          </select>
          <select
            value={resultFilter}
            onChange={(e) => setResultFilter(e.target.value)}
            aria-label="סינון לפי תוצאה"
            className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-700"
          >
            <option value="">הכל</option>
            <option value="green">מאושר</option>
            <option value="red">אין כניסה</option>
            <option value="invalid">לא תקף</option>
          </select>
        </div>
        <div className="flex gap-1.5">
          {SCAN_RANGE_PRESETS.map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => setRangeFilter(p.key)}
              aria-pressed={rangeFilter === p.key}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                rangeFilter === p.key ? 'bg-blue-500 text-white' : 'bg-slate-100 text-slate-600'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {summary && (
          <p className="text-xs text-slate-500">
            סה"כ {summary.total} · מאושר {summary.green} · אין כניסה {summary.red} · לא תקף {summary.invalid}
          </p>
        )}
      </div>
      {scans.loading ? (
        <p className="px-4 py-4 text-sm text-slate-400">טוען…</p>
      ) : !scans.items.length ? (
        <p className="px-4 py-4 text-sm text-slate-400">אין סריקות עדיין</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {scans.items.map((s) => {
            const r = SCAN_RESULT_HE[s.result] || SCAN_RESULT_HE.invalid;
            return (
              <li key={s.id} className="px-4 py-2.5 flex items-center gap-3">
                <Badge className={`${r.cls} shrink-0`}>{r.label}</Badge>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 truncate">
                    {s.is_guest ? (s.guest_name || '—') : (s.worker_name || '—')}
                  </p>
                </div>
                {/* qrg-guest — tag guest rows */}
                {s.is_guest && (
                  <Badge className="bg-amber-100 text-amber-800 shrink-0">אורח</Badge>
                )}
                <time className="text-xs text-slate-400 shrink-0" dir="ltr">
                  {(s.ts || '').slice(0, 16).replace('T', ' ')}
                </time>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

// qrg-guest B-FE-2 — issue dialog + compact issued-passes list (workers tab).
// The QR share/print reuses the worker-card pattern (downloadBlob + print view).
const GUEST_STATUS_CHIP = (p) => {
  if (p.status === 'revoked') return { label: 'בוטל', cls: 'bg-slate-200 text-slate-600' };
  if (p.signed) return { label: 'נחתם', cls: 'bg-green-100 text-green-800' };
  return { label: 'ממתין לחתימה', cls: 'bg-amber-100 text-amber-800' };
};

// qrg-share-fix S2 — the Hebrew guest entry-code message. {link} is the
// gate_url (spec wording — do not edit).
const guestEntryMessage = (guestName, projectName, validOn, link) =>
  `שלום ${guestName}, זהו קוד הכניסה שלך לאתר ${projectName} לתאריך ${validOn}. ` +
  `יש להיכנס לקישור, לקרוא את תדריך הבטיחות ולחתום לפני ההגעה לאתר: ${link}`;

function GuestPassSection({ projectId, projectName, issueOpen, onIssueOpenChange }) {
  const [passes, setPasses] = useState({ items: [], total: 0, loading: true });
  const [form, setForm] = useState({ name: '', company: '', date: '' });
  const [saving, setSaving] = useState(false);
  const [issued, setIssued] = useState(null); // last created pass (QR view)
  const [qrBusy, setQrBusy] = useState(false);

  const reload = React.useCallback(() => {
    safetyService.listGuestPasses(projectId, { limit: 50 })
      .then((res) => setPasses({ items: res.items || [], total: res.total || 0, loading: false }))
      .catch(() => setPasses({ items: [], total: 0, loading: false }));
  }, [projectId]);

  useEffect(() => { reload(); }, [reload]);

  useEffect(() => {
    if (issueOpen) {
      setForm({ name: '', company: '', date: new Date().toISOString().slice(0, 10) });
      setIssued(null);
    }
  }, [issueOpen]);

  const submit = async () => {
    if (form.name.trim().length < 2) { toast.error('יש להזין שם אורח'); return; }
    if (!form.company.trim()) { toast.error('יש להזין חברה/תפקיד'); return; }
    setSaving(true);
    try {
      const res = await safetyService.createGuestPass(projectId, {
        guest_name: form.name.trim(),
        guest_company: form.company.trim(),
        valid_on: form.date,
      });
      setIssued(res);
      reload();
      toast.success('קוד האורח הונפק');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'הנפקת קוד האורח נכשלה');
    } finally {
      setSaving(false);
    }
  };

  // qrg-share-fix S4b — primary share is a Hebrew MESSAGE with the gate
  // link (issue response + list items both carry gate_url). Print keeps
  // the QR image (unchanged below).
  const sendCode = async (pass) => {
    if (qrBusy) return;
    setQrBusy(true);
    try {
      if (!pass?.gate_url) throw new Error('missing gate_url');
      const msg = guestEntryMessage(
        pass.guest_name || '', projectName || '', pass.valid_on || '', pass.gate_url,
      );
      const out = await shareText(msg);
      if (out?.copied) toast.success('ההודעה הועתקה — הדבק ושלח');
    } catch (e) {
      toast.error('שליחת קוד האורח נכשלה');
    } finally {
      setQrBusy(false);
    }
  };

  const printQr = async (pass) => {
    if (qrBusy) return;
    setQrBusy(true);
    try {
      const blob = await safetyService.getGuestQrPng(projectId, pass.id);
      const url = window.URL.createObjectURL(blob);
      const w = window.open('', '_blank');
      if (!w) { toast.error('חלון ההדפסה נחסם על ידי הדפדפן'); return; }
      w.document.write(`
        <html dir="rtl"><head><title>קוד אורח</title></head>
        <body style="text-align:center;font-family:sans-serif;padding:24px">
          <h2 style="margin-bottom:4px">${(pass.guest_name || '').replace(/</g, '&lt;')}</h2>
          <p style="color:#555;margin-top:0">קוד אורח ליום ${(pass.valid_on || '').replace(/</g, '&lt;')} — BrikOps</p>
          <img src="${url}" style="width:320px;height:320px" onload="window.print()" />
        </body></html>`);
      w.document.close();
    } catch (e) {
      toast.error('פתיחת תצוגת ההדפסה נכשלה');
    } finally {
      setQrBusy(false);
    }
  };

  const revoke = async (pass) => {
    // eslint-disable-next-line no-alert
    if (!window.confirm('לבטל את קוד האורח? עמוד הסריקה יציג "קוד לא תקף".')) return;
    try {
      await safetyService.revokeGuestPass(projectId, pass.id);
      toast.success('קוד האורח בוטל');
      reload();
    } catch (e) {
      toast.error('ביטול קוד האורח נכשל');
    }
  };

  return (
    <div className="border-t border-slate-200">
      <div className="px-4 py-3 flex items-center gap-2 bg-slate-50">
        <QrCode className="w-4 h-4 text-slate-500" />
        <p className="text-sm font-semibold text-slate-700">קודי אורחים ({passes.total})</p>
      </div>
      {passes.loading ? (
        <p className="px-4 py-4 text-sm text-slate-400">טוען…</p>
      ) : !passes.items.length ? (
        <p className="px-4 py-4 text-sm text-slate-400">לא הונפקו קודי אורח עדיין</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {passes.items.map((p) => {
            const chip = GUEST_STATUS_CHIP(p);
            return (
              <li key={p.id} className="px-4 py-2.5 flex items-center gap-3">
                <Badge className={`${chip.cls} shrink-0`}>{chip.label}</Badge>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 truncate">
                    {p.guest_name} · {p.guest_company}
                  </p>
                  <p className="text-xs text-slate-500" dir="ltr">{p.valid_on}</p>
                </div>
                {p.status === 'active' && (
                  <>
                    <button
                      type="button"
                      aria-label="שלח קוד"
                      onClick={() => sendCode(p)}
                      className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-500 shrink-0"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => revoke(p)}
                      className="text-xs text-red-600 font-medium px-2 py-1 rounded-lg hover:bg-red-50 shrink-0"
                    >
                      ביטול
                    </button>
                  </>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <Dialog open={issueOpen} onOpenChange={(o) => { if (!saving) onIssueOpenChange(o); }}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader className="text-right">
            <DialogTitle className="text-base font-bold text-slate-800">
              {issued ? 'קוד אורח הונפק' : 'הנפקת קוד אורח ליום'}
            </DialogTitle>
          </DialogHeader>
          {issued ? (
            <div className="space-y-4 text-center">
              {issued.qr_display_url && (
                <img
                  src={issued.qr_display_url}
                  alt="QR"
                  className="w-48 h-48 mx-auto border border-slate-200 rounded-xl"
                />
              )}
              <p className="text-sm text-slate-700 font-medium">
                {issued.guest_name} · {issued.guest_company}
              </p>
              <p className="text-xs text-slate-500">מאושר ליום {issued.valid_on} — לאחר חתימת תדריך המבקרים</p>
              <div className="flex gap-2">
                <Button className="flex-1" disabled={qrBusy} onClick={() => sendCode(issued)}>
                  <Send className="w-4 h-4 ml-1" />
                  שלח קוד
                </Button>
                <Button variant="outline" className="flex-1" disabled={qrBusy} onClick={() => printQr(issued)}>
                  הדפסה
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">שם האורח</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  dir="rtl"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-300"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">חברה / תפקיד</label>
                <input
                  type="text"
                  value={form.company}
                  onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))}
                  dir="rtl"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-300"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">תאריך הביקור</label>
                <input
                  type="date"
                  value={form.date}
                  onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-300"
                />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            {issued ? (
              <Button variant="outline" onClick={() => onIssueOpenChange(false)}>סגור</Button>
            ) : (
              <>
                <Button variant="outline" disabled={saving} onClick={() => onIssueOpenChange(false)}>ביטול</Button>
                <Button disabled={saving} onClick={submit} className="bg-amber-500 hover:bg-amber-600">
                  הנפק קוד
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
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

const workerInitials = (name) => (name || '').trim().split(/\s+/).slice(0, 2)
  .map((w) => w[0]).join('').toUpperCase() || '?';

// Row thumbnail: 40px round photo, fail-soft to initials on load error.
function WorkerThumb({ worker }) {
  const [broken, setBroken] = useState(false);
  if (worker.photo_display_url && !broken) {
    return (
      <img
        src={worker.photo_display_url}
        alt={worker.full_name}
        className="w-10 h-10 rounded-full object-cover bg-slate-100 shrink-0"
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 text-sm font-semibold shrink-0">
      {workerInitials(worker.full_name)}
    </div>
  );
}

function WorkersList({ items, isWriter, onEdit, onOpenCard, onInduct }) {
  if (!items?.length) return <EmptyState icon={Users} text="אין עובדים רשומים" />;
  const today = new Date().toISOString().slice(0, 10);
  // ind2-fix4 E2: three visual states from induction_valid_until
  const inductBtn = (w) => {
    const until = w.induction_valid_until ? w.induction_valid_until.slice(0, 10) : null;
    if (until && until >= today) {
      const [y, m, d] = until.split('-');
      return {
        label: `הודרך · עד ${d}/${m}/${y.slice(2)}`,
        title: 'הדרכת אתר בתוקף — לחיצה תפתח העברה מחדש (עם אישור)',
        cls: 'px-2 py-1.5 rounded-lg hover:bg-emerald-100 text-emerald-700 bg-emerald-50 border border-emerald-100 shrink-0 flex items-center gap-1 max-w-[130px]',
      };
    }
    if (until) {
      return {
        label: 'פג תוקף · העבר מחדש',
        title: 'הדרכת האתר פגה — העבר מחדש',
        cls: 'px-2 py-1.5 rounded-lg hover:bg-amber-100 text-amber-700 bg-amber-50 border border-amber-100 shrink-0 flex items-center gap-1 max-w-[150px]',
      };
    }
    return {
      label: 'הדרכת אתר',
      title: 'בצע הדרכת אתר',
      cls: 'px-2 py-1.5 rounded-lg hover:bg-purple-100 text-purple-700 bg-purple-50 border border-purple-100 shrink-0 flex items-center gap-1 max-w-[110px]',
    };
  };
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((w) => (
        <li
          key={w.id}
          role="button"
          onClick={() => onOpenCard(w)}
          className="px-4 py-3 flex items-center gap-3 hover:bg-slate-50 cursor-pointer">
          <WorkerThumb worker={w} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="font-medium text-slate-900 truncate">{w.full_name}</p>
              {w.blocked?.is_blocked && (
                <Badge className="bg-red-100 text-red-800 shrink-0">חסום</Badge>
              )}
            </div>
            <p className="text-xs text-slate-500 truncate">
              {w.profession || 'ללא מקצוע'}{w.phone && ` · ${w.phone}`}
            </p>
          </div>
          {isWriter && (
            <>
              {/* ind2-fix1 E4 / ind2-fix4 E2: labeled 3-state induction control */}
              {(() => {
                const b = inductBtn(w);
                return (
                  <button
                    type="button"
                    aria-label={b.title}
                    title={b.title}
                    onClick={(e) => { e.stopPropagation(); onInduct(w); }}
                    className={b.cls}
                  >
                    <GraduationCap className="w-4 h-4 shrink-0" />
                    <span className="text-xs font-medium truncate">{b.label}</span>
                  </button>
                );
              })()}
              <button
                type="button"
                aria-label="ערוך עובד"
                onClick={(e) => { e.stopPropagation(); onEdit(w); }}
                className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-500 shrink-0"
              >
                <Pencil className="w-4 h-4" />
              </button>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}

function TrainingsList({ items, workers, isWriter, highlightId, onEdit, onRenew, onSign, onViewEvidence, onReconduct, onDownloadCertificate }) {
  const [expandedKeys, setExpandedKeys] = useState(() => new Set());
  // ind3-fix2 F2: when navigated from the worker card — auto-expand the group
  // holding the target row (it may be an older record) and scroll it into view.
  const highlightRef = useRef(null);
  useEffect(() => {
    if (!highlightId || !items?.length) return;
    const target = items.find((t) => t.id === highlightId);
    if (target) {
      setExpandedKeys((prev) => {
        const key = `${target.worker_id}|${target.training_type}`;
        if (prev.has(key)) return prev;
        const next = new Set(prev);
        next.add(key);
        return next;
      });
    }
    const raf = requestAnimationFrame(() => {
      highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    return () => cancelAnimationFrame(raf);
  }, [highlightId, items]);
  const toggle = (key) => () => setExpandedKeys((prev) => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });
  if (!items?.length) return <EmptyState icon={GraduationCap} text="אין הדרכות רשומות" />;
  const nameById = new Map((workers || []).map((w) => [w.id, w.full_name]));
  const today = new Date().toISOString().slice(0, 10);

  // Group by worker+type. Server returns trained_at DESC, so the first record
  // seen per key is the newest; the rest collapse under an expander. Defensive
  // swap (no full re-sort) in case items arrive unsorted.
  const groups = [];
  const byKey = new Map();
  (items || []).forEach((tr) => {
    const key = `${tr.worker_id}|${tr.training_type}`;
    const g = byKey.get(key);
    if (!g) {
      const ng = { key, latest: tr, older: [] };
      byKey.set(key, ng);
      groups.push(ng);
    } else {
      const a = (tr.trained_at || '').slice(0, 10);
      const b = (g.latest.trained_at || '').slice(0, 10);
      if (a > b) { g.older.push(g.latest); g.latest = tr; }
      else { g.older.push(tr); }
    }
  });

  const renderRow = (tr, { isOld }) => {
    const expired = tr.expires_at && tr.expires_at.slice(0, 10) < today;
    // ind2-fix4 E4+E5c: induction rows — evidence view instead of
    // חידוש/החתמה; re-conduct goes through the full ceremony.
    const isInduction = (tr.training_type || '').trim() === INDUCTION_TYPE;
    return (
      <li
        key={tr.id}
        ref={tr.id === highlightId ? highlightRef : undefined}
        className={`px-4 py-3 flex items-start gap-3 hover:bg-slate-50${isOld ? ' opacity-60 bg-slate-50' : ''}${tr.id === highlightId ? ' ring-2 ring-inset ring-purple-400 bg-purple-50/50' : ''}`}
      >
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
        <div className="flex items-center gap-1 shrink-0">
          {/* ind3 E5 — certificate PDF on SIGNED induction rows */}
          {isInduction && tr.worker_signature && (
            <button
              type="button"
              aria-label="הורדת תעודת הדרכת אתר"
              title="הורדת תעודת הדרכת אתר"
              onClick={(e) => { e.stopPropagation(); onDownloadCertificate && onDownloadCertificate(tr); }}
              className="px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 inline-flex items-center gap-1"
            >
              <Download className="w-3.5 h-3.5" /> תעודה
            </button>
          )}
          {tr.worker_signature ? (
            isInduction ? (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); onViewEvidence && onViewEvidence(tr); }}
                className="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 inline-flex items-center gap-1"
                title="צפייה בראיות ההדרכה"
              >
                <Eye className="w-3.5 h-3.5" /> צפייה
              </button>
            ) : tr.worker_signature.signature_display_url ? (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); window.open(tr.worker_signature.signature_display_url, '_blank', 'noopener'); }}
                className="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800"
              >
                חתום
              </button>
            ) : (
              <span
                title={tr.worker_signature.typed_name || tr.worker_signature.name || ''}
                className="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800"
              >
                חתום
              </span>
            )
          ) : (isWriter && !isInduction && (
            <Button
              type="button"
              variant="outline"
              className="h-8 px-3 text-xs"
              onClick={(e) => { e.stopPropagation(); onSign(tr); }}
            >
              החתמה
            </Button>
          ))}
          {isWriter && !isOld && (
            isInduction ? (
              <Button
                type="button"
                variant="outline"
                className="h-8 px-3 text-xs"
                onClick={(e) => { e.stopPropagation(); onReconduct && onReconduct(tr); }}
              >
                העבר מחדש
              </Button>
            ) : (
              <Button
                type="button"
                variant="outline"
                className="h-8 px-3 text-xs"
                onClick={(e) => { e.stopPropagation(); onRenew(tr); }}
              >
                חידוש
              </Button>
            )
          )}
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
        </div>
      </li>
    );
  };

  return (
    <ul className="divide-y divide-slate-100">
      {groups.map((g) => (
        <React.Fragment key={g.key}>
          {renderRow(g.latest, { isOld: false })}
          {g.older.length > 0 && (
            <li className="px-4 py-1">
              <button
                type="button"
                onClick={toggle(g.key)}
                className="text-xs text-slate-500 hover:text-slate-700"
              >
                {expandedKeys.has(g.key) ? 'הסתר קודמות' : `הצג קודמות (${g.older.length})`}
              </button>
            </li>
          )}
          {expandedKeys.has(g.key) && g.older.map((tr) => renderRow(tr, { isOld: true }))}
        </React.Fragment>
      ))}
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
