import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { handoverService } from '../services/api';
import { toast } from 'sonner';
import { t } from '../i18n';
import {
  ArrowRight, Loader2, CheckCircle2, AlertTriangle, CircleDot,
  MinusCircle, Circle, Bug, ExternalLink, CheckCheck, Camera, ChevronLeft
} from 'lucide-react';
import HandoverItemModal from '../components/handover/HandoverItemModal';

const STATUS_CONFIG = {
  ok: { icon: CheckCircle2, color: 'text-green-500', bg: 'bg-green-50', ring: 'border-green-400', fill: 'bg-green-400' },
  partial: { icon: CircleDot, color: 'text-amber-500', bg: 'bg-amber-50', ring: 'border-amber-400', fill: 'bg-amber-400' },
  defective: { icon: AlertTriangle, color: 'text-red-500', bg: 'bg-red-50', ring: 'border-red-400', fill: 'bg-red-400' },
  not_relevant: { icon: MinusCircle, color: 'text-slate-400', bg: 'bg-slate-50', ring: 'border-slate-300', fill: 'bg-slate-300' },
  not_checked: { icon: Circle, color: 'text-slate-300', bg: 'bg-white', ring: 'border-slate-200', fill: 'bg-white' },
};

const StatusCircle = ({ status }) => {
  const cfg = STATUS_CONFIG[status || 'not_checked'] || STATUS_CONFIG.not_checked;
  const Icon = cfg.icon;
  return (
    <div className={`w-9 h-9 rounded-full border-2 ${cfg.ring} flex items-center justify-center flex-shrink-0 ${cfg.bg}`}>
      <Icon className={`w-4 h-4 ${cfg.color}`} />
    </div>
  );
};

const HandoverSectionPage = () => {
  const { projectId, unitId, protocolId, sectionId } = useParams();
  const navigate = useNavigate();

  const [protocol, setProtocol] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState(null);
  const [markingAll, setMarkingAll] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [activeTrade, setActiveTrade] = useState(null);
  const celebratedRef = useRef(false);
  const prevCheckedRef = useRef(null);

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

  const section = protocol?.sections?.find(s => s.section_id === sectionId);
  const isSigned = protocol?.locked === true;
  const items = useMemo(() => section?.items || [], [section]);
  const notCheckedItems = items.filter(i => !i.status || i.status === 'not_checked');
  const checkedCount = items.filter(i => i.status && i.status !== 'not_checked').length;
  const totalCount = items.length;

  const trades = useMemo(() => {
    const tradeSet = new Set();
    items.forEach(i => { if (i.trade) tradeSet.add(i.trade); });
    return Array.from(tradeSet);
  }, [items]);

  const filteredItems = activeTrade ? items.filter(i => i.trade === activeTrade) : items;

  useEffect(() => {
    if (prevCheckedRef.current !== null && !celebratedRef.current) {
      if (checkedCount === totalCount && totalCount > 0 && prevCheckedRef.current < totalCount) {
        celebratedRef.current = true;
        toast.success('🎉 כל הפריטים נבדקו!', { duration: 2000 });
        setTimeout(() => {
          navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}`);
        }, 1500);
      }
    }
    prevCheckedRef.current = checkedCount;
  }, [checkedCount, totalCount, navigate, projectId, unitId, protocolId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
      </div>
    );
  }

  if (!section) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4" dir="rtl">
        <p className="text-slate-500">{t('handover', 'loadError')}</p>
        <button onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}`)}
          className="text-purple-600 hover:text-purple-700 font-medium">
          {t('handover', 'backToProtocol')}
        </button>
      </div>
    );
  }

  const handleMarkAllOk = async () => {
    setShowConfirm(false);
    if (notCheckedItems.length === 0 || isSigned) return;
    try {
      setMarkingAll(true);
      for (const item of notCheckedItems) {
        await handoverService.updateItem(projectId, protocolId, sectionId, item.item_id, { status: 'ok' });
      }
      toast.success(t('handover', 'markAllOkDone'));
      await loadProtocol();
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
      await loadProtocol();
    } finally {
      setMarkingAll(false);
    }
  };

  const handleItemUpdated = () => { loadProtocol(); };

  const currentItem = selectedItem ? items.find(i => i.item_id === selectedItem) : null;
  const progressPct = totalCount > 0 ? (checkedCount / totalCount) * 100 : 0;

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="sticky top-0 z-30">
        <div className="bg-gradient-to-bl from-[#1e1b4b] to-[#312e81] text-white">
          <div className="max-w-lg mx-auto px-4 py-3">
            <div className="flex items-center gap-3">
              <button onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}`)}
                className="p-1.5 hover:bg-white/10 rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center">
                <ArrowRight className="w-5 h-5" />
              </button>
              <div className="flex-1 min-w-0">
                <h1 className="text-lg font-extrabold truncate">{section.name}</h1>
                <p className="text-indigo-300 text-xs">{checkedCount}/{totalCount} נבדקו</p>
              </div>
              {!isSigned && notCheckedItems.length > 0 && (
                <button
                  onClick={() => showConfirm ? handleMarkAllOk() : setShowConfirm(true)}
                  disabled={markingAll}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-medium
                    transition-colors disabled:opacity-50 min-h-[44px]"
                >
                  {markingAll ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCheck className="w-3.5 h-3.5" />}
                  {showConfirm ? 'אישור' : `סמן הכל ✓ (${notCheckedItems.length})`}
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="bg-white border-b border-slate-200">
          <div className="max-w-lg mx-auto">
            <div className="h-1 bg-slate-100">
              <div
                className="h-full rounded-l-full transition-all duration-500 ease-out"
                style={{
                  width: `${progressPct}%`,
                  background: progressPct >= 100 ? '#22c55e' : 'linear-gradient(to left, #a78bfa, #7c3aed)'
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {showConfirm && !markingAll && (
        <div className="max-w-lg mx-auto px-4 mt-2">
          <div className="bg-green-50 border border-green-200 rounded-xl p-3 flex items-center justify-between">
            <span className="text-sm text-green-800 font-medium">
              {t('handover', 'markAllOkConfirm').replace('{count}', notCheckedItems.length)}
            </span>
            <div className="flex gap-2">
              <button onClick={handleMarkAllOk} disabled={markingAll}
                className="px-3 py-1.5 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600 disabled:opacity-50">
                אישור
              </button>
              <button onClick={() => setShowConfirm(false)}
                className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-sm font-medium hover:bg-slate-200">
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}

      {trades.length > 1 && (
        <div className="max-w-lg mx-auto mt-2">
          <div className="flex gap-1.5 px-4 overflow-x-auto no-scrollbar py-1">
            <button
              onClick={() => setActiveTrade(null)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors min-h-[36px]
                ${!activeTrade ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            >
              הכל ({items.length})
            </button>
            {trades.map(trade => (
              <button
                key={trade}
                onClick={() => setActiveTrade(activeTrade === trade ? null : trade)}
                className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors min-h-[36px]
                  ${activeTrade === trade ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
              >
                {trade} ({items.filter(i => i.trade === trade).length})
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="max-w-lg mx-auto px-4 mt-2 space-y-1 pb-8">
        {filteredItems.map(item => {
          const status = item.status || 'not_checked';
          const hasDefect = !!item.defect_id;
          const hasPhotos = !!(item.photos && item.photos.length > 0);
          const hasNotes = !!item.notes;

          const rowBg = {
            ok: 'bg-green-50/50 border-green-200',
            partial: 'bg-amber-50/50 border-amber-200',
            defective: 'bg-red-50/50 border-red-200',
            not_relevant: 'bg-slate-50 border-slate-200',
            not_checked: 'bg-white border-slate-200',
          }[status] || 'bg-white border-slate-200';

          return (
            <button
              key={item.item_id}
              onClick={() => setSelectedItem(item.item_id)}
              className={`w-full flex items-center gap-2.5 p-2.5 rounded-xl border transition-all active:scale-[0.98]
                hover:shadow-sm ${rowBg} min-h-[52px]`}
            >
              <StatusCircle status={status} />
              <div className="flex-1 min-w-0 text-right">
                <span className="text-sm font-semibold text-slate-800 truncate block">{item.name}</span>
                <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                  {item.trade && (
                    <span className="text-[10px] text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{item.trade}</span>
                  )}
                  {hasDefect && (
                    <span
                      onClick={(e) => { e.stopPropagation(); navigate(`/tasks/${item.defect_id}`); }}
                      className="text-[10px] text-red-600 bg-red-100 px-1.5 py-0.5 rounded font-medium flex items-center gap-0.5 cursor-pointer"
                    >
                      <Bug className="w-2.5 h-2.5" />ליקוי
                    </span>
                  )}
                  {hasPhotos && <Camera className="w-3 h-3 text-slate-400" />}
                  {hasNotes && <span className="text-[10px] text-slate-400">💬</span>}
                </div>
              </div>
              <ChevronLeft className="w-4 h-4 text-slate-300 flex-shrink-0" />
            </button>
          );
        })}
      </div>

      <HandoverItemModal
        open={!!selectedItem}
        onClose={() => setSelectedItem(null)}
        item={currentItem}
        sectionId={sectionId}
        sectionName={section.name}
        projectId={projectId}
        protocolId={protocolId}
        isSigned={isSigned}
        onItemUpdated={handleItemUpdated}
        allItems={items}
        onSelectItem={setSelectedItem}
      />
    </div>
  );
};

export default HandoverSectionPage;
