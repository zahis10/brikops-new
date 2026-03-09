import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { unitService, configService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { formatUnitLabel } from '../utils/formatters';
import { tCategory } from '../i18n';
import NewDefectModal from '../components/NewDefectModal';
import {
  ArrowRight, Loader2, AlertTriangle, CheckCircle2, Clock,
  ChevronDown, ChevronUp, ShieldAlert, Image as ImageIcon, Plus
} from 'lucide-react';

const STATUS_LABELS = {
  open: { label: 'פתוח', color: 'bg-red-100 text-red-700', key: 'open' },
  assigned: { label: 'שויך', color: 'bg-orange-100 text-orange-700', key: 'open' },
  in_progress: { label: 'בביצוע', color: 'bg-blue-100 text-blue-700', key: 'in_progress' },
  pending_contractor_proof: { label: 'ממתין להוכחת קבלן', color: 'bg-orange-100 text-orange-700', key: 'in_progress' },
  pending_manager_approval: { label: 'ממתין לאישור מנהל', color: 'bg-indigo-100 text-indigo-700', key: 'in_progress' },
  returned_to_contractor: { label: 'הוחזר לקבלן', color: 'bg-rose-100 text-rose-700', key: 'in_progress' },
  waiting_verify: { label: 'ממתין לאימות', color: 'bg-purple-100 text-purple-700', key: 'in_progress' },
  closed: { label: 'סגור', color: 'bg-green-100 text-green-700', key: 'closed' },
  reopened: { label: 'נפתח מחדש', color: 'bg-amber-100 text-amber-700', key: 'open' },
};

const FILTER_CHIPS = [
  { key: 'all', label: 'הכל' },
  { key: 'open', label: 'פתוחים' },
  { key: 'in_progress', label: 'בטיפול' },
  { key: 'closed', label: 'סגורים' },
];

const PRIORITY_CONFIG = {
  low: { label: 'נמוך', color: 'text-slate-500' },
  medium: { label: 'בינוני', color: 'text-blue-600' },
  high: { label: 'גבוה', color: 'text-amber-600' },
  critical: { label: 'קריטי', color: 'text-red-600' },
};

const ApartmentDashboardPage = () => {
  const { projectId, unitId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [unitData, setUnitData] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [activeFilter, setActiveFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [summaryOpen, setSummaryOpen] = useState(true);
  const [blockingOpen, setBlockingOpen] = useState(false);
  const [flagChecked, setFlagChecked] = useState(false);
  const [showDefectModal, setShowDefectModal] = useState(false);
  const canCreateDefect = user && user.role === 'project_manager';

  useEffect(() => {
    configService.getFeatures().then(data => {
      if (!data?.feature_flags?.defects_v2) {
        navigate(`/projects/${projectId}/units/${unitId}/tasks`, { replace: true });
      } else {
        setFlagChecked(true);
      }
    }).catch(() => {
      navigate(`/projects/${projectId}/units/${unitId}/tasks`, { replace: true });
    });
  }, [projectId, unitId, navigate]);

  const loadUnit = useCallback(async () => {
    try {
      setLoading(true);
      const data = await unitService.get(unitId);
      setUnitData(data);
    } catch (err) {
      toast.error('שגיאה בטעינת פרטי דירה');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [unitId]);

  const loadTasks = useCallback(async () => {
    try {
      setTasksLoading(true);
      const data = await unitService.getTasks(unitId);
      setTasks(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error('שגיאה בטעינת ליקויים');
      console.error(err);
    } finally {
      setTasksLoading(false);
    }
  }, [unitId]);

  useEffect(() => {
    if (flagChecked) {
      loadUnit();
      loadTasks();
    }
  }, [flagChecked, loadUnit, loadTasks]);

  useEffect(() => {
    if (categoryFilter !== 'all') {
      const exists = tasks.some(t => t.category === categoryFilter);
      if (!exists) setCategoryFilter('all');
    }
  }, [tasks, categoryFilter]);

  if (!flagChecked || loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  if (!unitData) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4" dir="rtl">
        <p className="text-slate-500">דירה לא נמצאה</p>
        <button onClick={() => navigate(-1)} className="text-amber-600 hover:text-amber-700 font-medium">
          חזרה
        </button>
      </div>
    );
  }

  const { unit, floor, building, project, kpi } = unitData;
  const effectiveLabel = unit.effective_label || unit.unit_no || '';

  const openCount = (kpi?.open ?? 0) + (kpi?.reopened ?? 0);
  const inProgressCount = (kpi?.in_progress ?? 0) + (kpi?.waiting_verify ?? 0);
  const closedCount = kpi?.closed ?? 0;
  const totalCount = openCount + inProgressCount + closedCount;

  const blockingTasks = tasks.filter(t => t.priority === 'critical' || t.priority === 'high');
  const blockingCount = blockingTasks.length;

  const getSeverityBadge = () => {
    if (totalCount === 0) return { label: 'תקין', color: 'bg-green-100 text-green-700' };
    const ratio = openCount / totalCount;
    if (ratio >= 0.5) return { label: 'חמור', color: 'bg-red-100 text-red-700' };
    if (ratio >= 0.2) return { label: 'דורש טיפול', color: 'bg-amber-100 text-amber-700' };
    return { label: 'מצב טוב', color: 'bg-green-100 text-green-700' };
  };

  const severity = getSeverityBadge();

  const categoryFilteredTasks = categoryFilter === 'all'
    ? tasks
    : tasks.filter(t => t.category === categoryFilter);

  const filterCounts = {
    all: categoryFilteredTasks.length,
    open: categoryFilteredTasks.filter(t => {
      const sl = STATUS_LABELS[t.status];
      return sl?.key === 'open';
    }).length,
    in_progress: categoryFilteredTasks.filter(t => {
      const sl = STATUS_LABELS[t.status];
      return sl?.key === 'in_progress';
    }).length,
    closed: categoryFilteredTasks.filter(t => {
      const sl = STATUS_LABELS[t.status];
      return sl?.key === 'closed';
    }).length,
  };

  const categoryChips = (() => {
    const cats = {};
    tasks.forEach(t => {
      if (t.category) cats[t.category] = (cats[t.category] || 0) + 1;
    });
    return Object.entries(cats)
      .sort((a, b) => b[1] - a[1])
      .map(([key, count]) => ({ key, label: tCategory(key), count }));
  })();

  const filteredTasks = activeFilter === 'all'
    ? categoryFilteredTasks
    : categoryFilteredTasks.filter(t => {
        const sl = STATUS_LABELS[t.status];
        return sl?.key === activeFilter;
      });

  return (
    <div className={`min-h-screen bg-slate-50 ${canCreateDefect ? 'pb-24' : 'pb-6'}`} dir="rtl">
      <div className="bg-gradient-to-l from-amber-500 to-amber-600 text-white">
        <div className="max-w-lg mx-auto px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                if (building?.id) {
                  navigate(`/projects/${projectId}/buildings/${building.id}/defects`);
                } else {
                  navigate(-1);
                }
              }}
              className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold truncate">{formatUnitLabel(effectiveLabel)}</h1>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${severity.color}`}>
                  {severity.label}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-amber-100 text-xs">
                {project && <span>{project.name}</span>}
                {building && <><span>›</span><span>{building.name}</span></>}
                {floor && <><span>›</span><span>{floor.name}</span></>}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 -mt-2">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <button
            onClick={() => setSummaryOpen(!summaryOpen)}
            className="w-full flex items-center justify-between p-3 text-right"
          >
            <span className="text-sm font-semibold text-slate-700">סיכום מהיר</span>
            {summaryOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
          {summaryOpen && (
            <div className="px-4 pb-4">
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="space-y-1">
                  <div className="flex items-center justify-center gap-1 text-red-500">
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <div className="text-2xl font-bold text-slate-800">{openCount}</div>
                  <div className="text-xs text-slate-500">פתוחות</div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center justify-center gap-1 text-blue-500">
                    <Clock className="w-4 h-4" />
                  </div>
                  <div className="text-2xl font-bold text-slate-800">{inProgressCount}</div>
                  <div className="text-xs text-slate-500">בטיפול</div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center justify-center gap-1 text-green-500">
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                  <div className="text-2xl font-bold text-slate-800">{closedCount}</div>
                  <div className="text-xs text-slate-500">סגורות</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {blockingCount > 0 && (
        <div className="max-w-lg mx-auto px-4 mt-3">
          <div className="bg-white rounded-xl shadow-sm border border-red-200 overflow-hidden">
            <button
              onClick={() => setBlockingOpen(!blockingOpen)}
              className="w-full flex items-center justify-between p-3 text-right"
            >
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-red-500" />
                <span className="text-sm font-semibold text-red-700">חוסמי מסירה</span>
                <span className="text-[10px] bg-red-500 text-white px-2 py-0.5 rounded-full font-bold">{blockingCount}</span>
              </div>
              {blockingOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
            </button>
            {blockingOpen && (
              <div className="px-3 pb-3 space-y-2">
                {blockingTasks.map(task => {
                  const statusInfo = STATUS_LABELS[task.status] || STATUS_LABELS.open;
                  return (
                    <button
                      key={task.id}
                      onClick={() => navigate(`/tasks/${task.id}`)}
                      className="w-full bg-red-50 rounded-lg p-2.5 text-right hover:bg-red-100 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-slate-800 truncate">{task.title}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium whitespace-nowrap ${statusInfo.color}`}>
                          {statusInfo.label}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="max-w-lg mx-auto px-4 mt-4 space-y-2">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {FILTER_CHIPS.map(chip => (
            <button
              key={chip.key}
              onClick={() => setActiveFilter(chip.key)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                activeFilter === chip.key
                  ? 'bg-amber-500 text-white shadow-sm'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              {chip.label} ({filterCounts[chip.key] ?? 0})
            </button>
          ))}
        </div>
        {categoryChips.length > 1 && (
          <div className="flex gap-2 overflow-x-auto pb-1">
            <button
              onClick={() => setCategoryFilter('all')}
              className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                categoryFilter === 'all'
                  ? 'bg-slate-700 text-white shadow-sm'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              כל התחומים ({tasks.length})
            </button>
            {categoryChips.map(chip => (
              <button
                key={chip.key}
                onClick={() => setCategoryFilter(chip.key)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                  categoryFilter === chip.key
                    ? 'bg-slate-700 text-white shadow-sm'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                }`}
              >
                {chip.label} ({chip.count})
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="max-w-lg mx-auto px-4 mt-3">
        {tasksLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
            <div className="text-slate-400 mb-2">
              <CheckCircle2 className="w-10 h-10 mx-auto" />
            </div>
            <p className="text-sm text-slate-500">
              {activeFilter !== 'all' ? 'אין ליקויים התואמים לסינון' : 'אין ליקויים לדירה זו'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredTasks.map(task => {
              const statusInfo = STATUS_LABELS[task.status] || STATUS_LABELS.open;
              const priorityInfo = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
              const hasImage = task.attachments?.length > 0 || task.image_url;
              const dateStr = task.created_at ? new Date(task.created_at).toLocaleDateString('he-IL') : '';

              return (
                <button
                  key={task.id}
                  onClick={() => navigate(`/tasks/${task.id}`)}
                  className="w-full bg-white rounded-xl border border-slate-200 p-3.5 text-right hover:shadow-md transition-shadow active:bg-slate-50"
                >
                  <div className="flex items-start gap-3">
                    {hasImage && (
                      <div className="w-12 h-12 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0 overflow-hidden">
                        {task.image_url ? (
                          <img src={task.image_url} alt="" className="w-full h-full object-cover" />
                        ) : (
                          <ImageIcon className="w-5 h-5 text-slate-300" />
                        )}
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="text-sm font-semibold text-slate-800 truncate">{task.title}</h3>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium whitespace-nowrap ${statusInfo.color}`}>
                          {statusInfo.label}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                        <span className="text-[10px] bg-slate-100 px-2 py-0.5 rounded text-slate-600">
                          {tCategory(task.category)}
                        </span>
                        <span className={`text-[10px] font-medium ${priorityInfo.color}`}>
                          {priorityInfo.label}
                        </span>
                        {task.location && (
                          <span className="text-[10px] text-slate-400">{task.location}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1.5 text-[10px] text-slate-400">
                        {dateStr && <span>{dateStr}</span>}
                        {task.assigned_to_name && <span>{task.assigned_to_name}</span>}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {canCreateDefect && (
        <div className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur border-t border-slate-200 p-3 z-40">
          <div className="max-w-lg mx-auto">
            <button
              onClick={() => setShowDefectModal(true)}
              className="w-full bg-amber-500 hover:bg-amber-600 text-white font-bold py-3 px-6 rounded-xl flex items-center justify-center gap-2 shadow-lg transition-colors active:bg-amber-700"
            >
              <Plus className="w-5 h-5" />
              פתח ליקוי
            </button>
          </div>
        </div>
      )}

      {showDefectModal && (
        <NewDefectModal
          isOpen={showDefectModal}
          onClose={() => setShowDefectModal(false)}
          onSuccess={() => {
            loadUnit();
            loadTasks();
          }}
          prefillData={{
            project_id: project?.id || projectId,
            building_id: building?.id || '',
            floor_id: floor?.id || '',
            unit_id: unitId,
            project_name: project?.name || '',
            building_name: building?.name || '',
            floor_name: floor?.name || '',
            unit_label: effectiveLabel,
          }}
        />
      )}
    </div>
  );
};

export default ApartmentDashboardPage;
