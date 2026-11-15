import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { unitService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { formatUnitLabel } from '../utils/formatters';
import { t } from '../i18n';
import UnitTypeEditModal, { TAG_MAP } from '../components/UnitTypeEditModal';
import StatCard from '../components/StatCard';
import PageHeader, { PAGE_HEADER_ACTION_CLASS } from '../components/PageHeader';
import {
  ArrowRight, Loader2, Building2, Layers, DoorOpen,
  ClipboardList, FileText, Home, Pencil
} from 'lucide-react';
import { Card } from '../components/ui/card';

const UnitHomePage = () => {
  const { projectId, unitId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [unitData, setUnitData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editingUnit, setEditingUnit] = useState(null);

  const loadUnit = useCallback(async () => {
    try {
      setLoading(true);
      const data = await unitService.get(unitId);
      setUnitData(data);
    } catch (err) {
      toast.error(t('unitHome', 'loadError'));
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [unitId]);

  useEffect(() => { loadUnit(); }, [loadUnit]);

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
        <p className="text-slate-500">{t('unitHome', 'notFound')}</p>
        <button onClick={() => navigate(`/projects/${projectId}/tasks`)} className="text-amber-600 hover:text-amber-700 font-medium">
          {t('unitHome', 'back')}
        </button>
      </div>
    );
  }

  const { unit, floor, building, project, kpi } = unitData;
  const effectiveLabel = unit.effective_label || unit.unit_no || '';

  const cards = [
    {
      key: 'defects',
      icon: ClipboardList,
      label: t('unitHome', 'defects'),
      description: t('unitHome', 'defectsDesc'),
      color: 'bg-red-50 border-red-200 hover:border-red-300',
      iconColor: 'text-red-500',
      badge: kpi ? (kpi.open + kpi.in_progress) : null,
      badgeColor: 'bg-red-500',
      onClick: () => navigate(`/projects/${projectId}/units/${unitId}/defects`, { state: { from: 'unit-home' } }),
    },
    {
      key: 'plans',
      icon: FileText,
      label: t('unitHome', 'plans'),
      description: t('unitHome', 'plansDesc'),
      color: 'bg-blue-50 border-blue-200 hover:border-blue-300',
      iconColor: 'text-blue-500',
      onClick: () => navigate(`/projects/${projectId}/units/${unitId}/plans`),
    },
    {
      key: 'handover',
      icon: Home,
      label: t('handover', 'tabTitle'),
      description: t('handover', 'tabDesc'),
      color: 'bg-purple-50 border-purple-200 hover:border-purple-300',
      iconColor: 'text-purple-500',
      onClick: () => navigate(`/projects/${projectId}/units/${unitId}/handover`),
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <PageHeader
        title={formatUnitLabel(effectiveLabel)}
        titleExtra={TAG_MAP[unit.unit_type_tag] ? (
          <span className="flex-shrink-0 text-xs px-2 py-0.5 rounded-full font-medium bg-white/20 text-white">
            {TAG_MAP[unit.unit_type_tag].label}
          </span>
        ) : null}
        crumbs={[project?.name, building?.name, floor?.name]}
        below={unit.unit_note ? (
          <p className="text-xs text-white/60 mt-0.5 truncate">{unit.unit_note}</p>
        ) : null}
        maxWidth="max-w-lg"
        onBack={() => {
          const role = user?.role;
          if (role === 'contractor') {
            navigate('/projects');
          } else if (role === 'viewer') {
            navigate(`/projects/${projectId}/tasks`);
          } else if (building?.id) {
            // BATCH unit-back-nav-fix (2026-05-25) — Bug 4: a unit
            // lives inside a building, so the back arrow returns
            // to that building's page rather than the project
            // structure tab.
            navigate(`/projects/${projectId}/buildings/${building.id}`);
          } else {
            navigate(`/projects/${projectId}/control?workMode=structure`);
          }
        }}
        actions={
          <button
            type="button"
            onClick={() => setEditingUnit(unit)}
            aria-label="עריכת פרטי הדירה"
            title="עריכת פרטי הדירה"
            className={PAGE_HEADER_ACTION_CLASS}
          >
            <Pencil className="w-5 h-5" />
          </button>
        }
      />

      <div className="max-w-lg mx-auto px-4 mt-3">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
          <div className="grid grid-cols-3 divide-x divide-slate-100" dir="ltr">
            <StatCard label={t('unitHome', 'kpiOpen')} value={kpi?.open ?? 0} />
            <StatCard label={t('unitHome', 'kpiInProgress')} value={kpi?.in_progress ?? 0} />
            <StatCard label={t('unitHome', 'kpiClosed')} value={kpi?.closed ?? 0} />
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 mt-6 space-y-3">
        <h2 className="text-sm font-semibold text-slate-500 px-1">{t('unitHome', 'sections')}</h2>
        {cards.map(card => (
          <Card
            key={card.key}
            className={`p-4 cursor-pointer transition-all active:scale-[0.98] border ${card.color}`}
            onClick={card.onClick}
          >
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${card.color.split(' ')[0]}`}>
                <card.icon className={`w-6 h-6 ${card.iconColor}`} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-slate-800">{card.label}</h3>
                  {card.badge != null && card.badge > 0 && (
                    <span className={`text-[10px] text-white px-2 py-0.5 rounded-full font-bold ${card.badgeColor}`}>
                      {card.badge}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">{card.description}</p>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-300 rotate-180 flex-shrink-0" />
            </div>
          </Card>
        ))}
      </div>

      {editingUnit && (
        <UnitTypeEditModal
          unit={editingUnit}
          onClose={() => setEditingUnit(null)}
          onSaved={({ unit_type_tag, unit_note }) => {
            setUnitData(prev => ({
              ...prev,
              unit: { ...prev.unit, unit_type_tag, unit_note },
            }));
          }}
        />
      )}
    </div>
  );
};

export default UnitHomePage;
