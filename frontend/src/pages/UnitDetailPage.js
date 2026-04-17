import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { unitService, taskService, projectCompanyService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { formatUnitLabel } from '../utils/formatters';
import NewDefectModal from '../components/NewDefectModal';
import StatCard from '../components/StatCard';
import StatusPill from '../components/StatusPill';
import CategoryPill from '../components/CategoryPill';
import Breadcrumbs from '../components/Breadcrumbs';
import TaskCardSkeleton from '../components/TaskCardSkeleton';
import {
  ArrowRight, Loader2, Plus, Filter, Building2, Layers, DoorOpen,
  CheckCircle2, ChevronDown, X
} from 'lucide-react';
import { tCategory } from '../i18n';

const STATUS_LABELS = {
  open: { label: 'פתוח', color: 'bg-red-100 text-red-700' },
  assigned: { label: 'שויך', color: 'bg-orange-100 text-orange-700' },
  in_progress: { label: 'בביצוע', color: 'bg-blue-100 text-blue-700' },
  waiting_verify: { label: 'ממתין לאימות', color: 'bg-purple-100 text-purple-700' },
  closed: { label: 'סגור', color: 'bg-green-100 text-green-700' },
  reopened: { label: 'נפתח מחדש', color: 'bg-amber-100 text-amber-700' },
};

const PRIORITY_CONFIG = {
  low: { label: 'נמוך', color: 'text-slate-500' },
  medium: { label: 'בינוני', color: 'text-blue-600' },
  high: { label: 'גבוה', color: 'text-amber-600' },
  critical: { label: 'קריטי', color: 'text-red-600' },
};

const STATUS_FILTER_OPTIONS = [
  { value: '', label: 'הכל' },
  { value: 'open', label: 'פתוח' },
  { value: 'assigned', label: 'שויך' },
  { value: 'in_progress', label: 'בביצוע' },
  { value: 'waiting_verify', label: 'ממתין לאימות' },
  { value: 'closed', label: 'סגור' },
  { value: 'reopened', label: 'נפתח מחדש' },
];

const CATEGORY_FILTER_OPTIONS = [
  { value: '', label: 'הכל' },
  ...['electrical','plumbing','hvac','painting','flooring','carpentry','masonry','windows','doors','general','bathroom_cabinets','finishes','structural','aluminum','metalwork','glazing','carpentry_kitchen'].map(k => ({ value: k, label: tCategory(k) })),
];

const UnitDetailPage = () => {
  const { projectId, unitId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [unitData, setUnitData] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [showDefectModal, setShowDefectModal] = useState(false);

  const canCreateDefect = user && user.role === 'project_manager';

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
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (categoryFilter) params.category = categoryFilter;
      const data = await unitService.getTasks(unitId, params);
      setTasks(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error('שגיאה בטעינת ליקויים');
      console.error(err);
    } finally {
      setTasksLoading(false);
    }
  }, [unitId, statusFilter, categoryFilter]);

  useEffect(() => { loadUnit(); }, [loadUnit]);
  useEffect(() => { loadTasks(); }, [loadTasks]);

  const handleDefectSuccess = (taskId) => {
    setShowDefectModal(false);
    loadUnit();
    loadTasks();
    toast.success('הליקוי נוצר בהצלחה!');
  };

  if (loading) {
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
        <button onClick={() => navigate(`/projects/${projectId}/control`)} className="text-amber-600 hover:text-amber-700 font-medium">
          חזרה
        </button>
      </div>
    );
  }

  const { unit, floor, building, project, kpi } = unitData;
  const effectiveLabel = unit.effective_label || unit.unit_no || '';

  const activeFilters = (statusFilter ? 1 : 0) + (categoryFilter ? 1 : 0);

  return (
    <div className="min-h-screen bg-slate-50 pb-24" dir="rtl">
      <div className="bg-slate-50">
        <div className="max-w-lg mx-auto bg-gradient-to-l from-amber-500 to-amber-600 text-white rounded-b-2xl px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/projects/${projectId}/units/${unitId}`)}
              className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-bold truncate">{formatUnitLabel(effectiveLabel)}</h1>
              <Breadcrumbs
                items={[project?.name, building?.name, floor?.name]}
                className="text-amber-100"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 -mt-2">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
          <div className="grid grid-cols-3 divide-x divide-slate-100" dir="ltr">
            <StatCard label="פתוחות" value={kpi.open} />
            <StatCard label="בטיפול" value={kpi.in_progress} />
            <StatCard label="סגורות" value={kpi.closed} />
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 mt-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-700">ליקויים ({tasks.length})</h2>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border transition-colors ${
              activeFilters > 0
                ? 'bg-amber-50 border-amber-300 text-amber-700'
                : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Filter className="w-3.5 h-3.5" />
            <span>סינון</span>
            {activeFilters > 0 && (
              <span className="bg-amber-500 text-white text-[10px] w-4 h-4 rounded-full flex items-center justify-center">
                {activeFilters}
              </span>
            )}
          </button>
        </div>

        {showFilters && (
          <div className="bg-white rounded-xl border border-slate-200 p-3 mb-3 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">פילטרים</span>
              {activeFilters > 0 && (
                <button
                  onClick={() => { setStatusFilter(''); setCategoryFilter(''); }}
                  className="text-xs text-amber-600 hover:text-amber-700 flex items-center gap-1"
                >
                  <X className="w-3 h-3" />
                  נקה הכל
                </button>
              )}
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">סטטוס</label>
              <div className="flex flex-wrap gap-1.5">
                {STATUS_FILTER_OPTIONS.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => setStatusFilter(opt.value)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                      statusFilter === opt.value
                        ? 'bg-amber-500 text-white border-amber-500'
                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">קטגוריה</label>
              <div className="flex flex-wrap gap-1.5">
                {CATEGORY_FILTER_OPTIONS.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => setCategoryFilter(opt.value)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                      categoryFilter === opt.value
                        ? 'bg-amber-500 text-white border-amber-500'
                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {tasksLoading ? (
          <div className="space-y-2">
            <TaskCardSkeleton />
            <TaskCardSkeleton />
            <TaskCardSkeleton />
          </div>
        ) : tasks.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
            <div className="text-slate-400 mb-2">
              <CheckCircle2 className="w-10 h-10 mx-auto" />
            </div>
            <p className="text-sm text-slate-500">
              {activeFilters > 0 ? 'אין ליקויים התואמים לפילטר' : 'אין ליקויים לדירה זו'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {tasks.map(task => {
              const statusInfo = STATUS_LABELS[task.status] || STATUS_LABELS.open;
              const priorityInfo = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
              return (
                <button
                  key={task.id}
                  onClick={() => navigate(`/tasks/${task.id}`, { state: { returnTo: `/projects/${projectId}/units/${unitId}` } })}
                  className="w-full bg-white rounded-xl border border-slate-200 p-3.5 text-right cursor-pointer hover:shadow-md transition-shadow active:bg-slate-50"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-semibold text-slate-800 truncate">{task.title}</h3>
                      {task.description && (
                        <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{task.description}</p>
                      )}
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <StatusPill status={task.status} label={statusInfo.label} />
                        <CategoryPill>{tCategory(task.category)}</CategoryPill>
                        <span className={`text-[10px] font-medium ${priorityInfo.color}`}>
                          {priorityInfo.label}
                        </span>
                        {task.source && task.source.startsWith('handover_') && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-amber-100 text-amber-700 border border-amber-200">
                            מסירה
                          </span>
                        )}
                      </div>
                    </div>
                    <ChevronDown className="w-4 h-4 text-slate-300 -rotate-90 flex-shrink-0 mt-1" />
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {canCreateDefect && (
        <div className="fixed bottom-0 inset-x-0 bg-white/95 backdrop-blur border-t border-slate-200 p-3 z-40">
          <div className="max-w-lg mx-auto">
            <button
              onClick={() => setShowDefectModal(true)}
              className="w-full bg-amber-500 hover:bg-amber-600 text-white font-bold py-3 px-6 rounded-xl flex items-center justify-center gap-2 shadow-lg transition-colors active:bg-amber-700"
            >
              <Plus className="w-5 h-5" />
              ליקוי חדש לדירה
            </button>
          </div>
        </div>
      )}

      {showDefectModal && (
        <NewDefectModal
          isOpen={showDefectModal}
          onClose={() => setShowDefectModal(false)}
          onSuccess={handleDefectSuccess}
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

export default UnitDetailPage;
