import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { handoverService } from '../services/api';
import { toast } from 'sonner';
import { t } from '../i18n';
import {
  ArrowRight, Loader2, ChevronDown, ChevronUp, ShieldCheck,
  Home, Users, Gauge, Package, FileText, Scale, PenLine,
  AlertTriangle, Lock
} from 'lucide-react';
import { Card } from '../components/ui/card';

const ENGINE_SECTIONS = [
  { key: 'property', label: t('handover', 'propertyDetails'), icon: Home, visibleTypes: ['initial', 'final'] },
  { key: 'tenants', label: t('handover', 'tenants'), icon: Users, visibleTypes: ['initial', 'final'] },
  { key: 'meters', label: t('handover', 'meters'), icon: Gauge, visibleTypes: ['final'] },
  { key: 'delivered', label: t('handover', 'deliveredItems'), icon: Package, visibleTypes: ['final'] },
  { key: 'notes', label: t('handover', 'generalNotes'), icon: FileText, visibleTypes: ['initial', 'final'] },
  { key: 'legal', label: t('handover', 'legalText'), icon: Scale, visibleTypes: ['initial', 'final'] },
  { key: 'signatures', label: t('handover', 'signatures'), icon: PenLine, visibleTypes: ['initial', 'final'] },
];

const STATUS_BADGE = {
  draft: { label: t('handover', 'draft'), color: 'bg-slate-100 text-slate-600' },
  in_progress: { label: t('handover', 'inProgress'), color: 'bg-blue-100 text-blue-700' },
  signed: { label: t('handover', 'signed'), color: 'bg-green-100 text-green-700' },
};

const ProgressRing = ({ checked, total, size = 36, strokeWidth = 3 }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = total > 0 ? checked / total : 0;
  const offset = circumference * (1 - pct);

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="rotate-[-90deg]">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e2e8f0" strokeWidth={strokeWidth} />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={pct >= 1 ? '#22c55e' : '#3b82f6'} strokeWidth={strokeWidth}
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" />
      </svg>
      <span className="absolute text-[9px] font-bold text-slate-600">
        {total > 0 ? Math.round(pct * 100) : 0}%
      </span>
    </div>
  );
};

const HandoverProtocolPage = () => {
  const { projectId, unitId, protocolId } = useParams();
  const navigate = useNavigate();

  const [protocol, setProtocol] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedEngine, setExpandedEngine] = useState(null);

  const loadProtocol = useCallback(async () => {
    try {
      setLoading(true);
      const data = await handoverService.getProtocol(projectId, protocolId);
      setProtocol(data);
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'loadError'));
    } finally {
      setLoading(false);
    }
  }, [projectId, protocolId]);

  useEffect(() => { loadProtocol(); }, [loadProtocol]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  if (!protocol) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4" dir="rtl">
        <p className="text-slate-500">{t('handover', 'loadError')}</p>
        <button
          onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover`)}
          className="text-purple-600 hover:text-purple-700 font-medium"
        >
          {t('handover', 'backToHandover')}
        </button>
      </div>
    );
  }

  const isSigned = protocol.status === 'signed';
  const statusInfo = STATUS_BADGE[protocol.status] || STATUS_BADGE.draft;
  const typeLabel = protocol.type === 'initial'
    ? t('handover', 'initialProtocol')
    : t('handover', 'finalProtocol');

  const templateSections = protocol.sections || [];
  const totalItems = templateSections.reduce((sum, s) => sum + (s.items?.length || 0), 0);
  const checkedItems = templateSections.reduce(
    (sum, s) => sum + (s.items?.filter(i => i.status && i.status !== 'not_checked').length || 0), 0
  );
  const defectCount = templateSections.reduce(
    (sum, s) => sum + (s.items?.filter(i => i.defect_id).length || 0), 0
  );

  const sectionStats = (section) => {
    const items = section.items || [];
    const total = items.length;
    const checked = items.filter(i => i.status && i.status !== 'not_checked').length;
    const defects = items.filter(i => i.defect_id).length;
    return { total, checked, defects };
  };

  const visibleEngineSections = ENGINE_SECTIONS.filter(es => es.visibleTypes.includes(protocol.type));

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className={`bg-gradient-to-l ${isSigned ? 'from-green-600 to-green-700' : 'from-purple-600 to-purple-700'} text-white`}>
        <div className="max-w-lg mx-auto px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover`)}
              className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold">{typeLabel}</h1>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                  isSigned ? 'bg-white/20 text-white' : 'bg-white/20 text-white'
                }`}>
                  {statusInfo.label}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-purple-200 text-xs">
                {protocol.snapshot?.unit_name && <span>{protocol.snapshot.unit_name}</span>}
                {protocol.snapshot?.building_name && <><span>›</span><span>{protocol.snapshot.building_name}</span></>}
              </div>
            </div>
            {isSigned && <Lock className="w-5 h-5 text-green-200" />}
          </div>
        </div>
      </div>

      {isSigned && (
        <div className="max-w-lg mx-auto px-4 mt-3">
          <div className="bg-green-50 border border-green-200 rounded-xl p-3 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-green-600 flex-shrink-0" />
            <span className="text-sm text-green-700 font-medium">{t('handover', 'readOnly')}</span>
            {protocol.signed_at && (
              <span className="text-xs text-green-600 mr-auto">
                {t('handover', 'signedOn')} {new Date(protocol.signed_at).toLocaleDateString('he-IL')}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="max-w-lg mx-auto px-4 mt-4">
        <Card className="p-4 border border-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-slate-500">{t('handover', 'progress')}</div>
              <div className="text-2xl font-bold text-slate-800">{checkedItems} / {totalItems}</div>
              <div className="text-xs text-slate-500">{t('handover', 'checkedItems')}</div>
            </div>
            <ProgressRing checked={checkedItems} total={totalItems} size={56} strokeWidth={4} />
          </div>
          {defectCount > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-100 flex items-center gap-2 text-red-600 text-sm">
              <AlertTriangle className="w-4 h-4" />
              <span>{defectCount} {t('handover', 'defects')}</span>
            </div>
          )}
        </Card>
      </div>

      <div className="max-w-lg mx-auto px-4 mt-6 space-y-2">
        <h2 className="text-sm font-semibold text-slate-500 px-1">{t('handover', 'protocolView')}</h2>

        {visibleEngineSections.map(es => (
          <Card key={es.key} className="border border-slate-200 overflow-hidden">
            <button
              onClick={() => setExpandedEngine(expandedEngine === es.key ? null : es.key)}
              className="w-full p-3 flex items-center gap-3 text-right hover:bg-slate-50 transition-colors"
            >
              <div className="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center flex-shrink-0">
                <es.icon className="w-4 h-4 text-purple-500" />
              </div>
              <span className="flex-1 text-sm font-medium text-slate-700">{es.label}</span>
              {expandedEngine === es.key ? (
                <ChevronUp className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              )}
            </button>
            {expandedEngine === es.key && (
              <div className="px-3 pb-3 pt-1 border-t border-slate-100">
                <p className="text-xs text-slate-400 italic">{t('handover', 'sectionPlaceholder')}</p>
              </div>
            )}
          </Card>
        ))}
      </div>

      <div className="max-w-lg mx-auto px-4 mt-6 space-y-2 pb-8">
        <h2 className="text-sm font-semibold text-slate-500 px-1">
          {t('handover', 'items')} ({templateSections.length})
        </h2>

        {templateSections.length === 0 && (
          <p className="text-sm text-slate-400 text-center py-6">{t('handover', 'noSections')}</p>
        )}

        {templateSections.map(section => {
          const stats = sectionStats(section);
          return (
            <Card
              key={section.section_id}
              className={`p-3 border transition-all cursor-pointer active:scale-[0.98] ${
                isSigned ? 'border-green-200 bg-green-50/30' : 'border-slate-200 hover:border-blue-300'
              }`}
              onClick={() => {
                navigate(
                  `/projects/${projectId}/units/${unitId}/handover/${protocolId}/sections/${section.section_id}`
                );
              }}
            >
              <div className="flex items-center gap-3">
                <ProgressRing checked={stats.checked} total={stats.total} />
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-bold text-slate-800 truncate">{section.name}</h3>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-xs text-slate-500">
                      {stats.checked}/{stats.total} {t('handover', 'checkedItems')}
                    </span>
                    {stats.defects > 0 && (
                      <span className="text-xs text-red-600 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        {stats.defects}
                      </span>
                    )}
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-300 rotate-180 flex-shrink-0" />
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
};

export default HandoverProtocolPage;
