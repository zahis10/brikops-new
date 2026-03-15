import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { handoverService } from '../services/api';
import { toast } from 'sonner';
import { t } from '../i18n';
import {
  ArrowRight, Loader2, CheckCircle2, AlertTriangle, CircleDot,
  MinusCircle, Circle, Bug, ExternalLink, CheckCheck
} from 'lucide-react';
import { Card } from '../components/ui/card';
import HandoverItemModal from '../components/handover/HandoverItemModal';

const STATUS_ICONS = {
  ok: { icon: CheckCircle2, color: 'text-green-500', bg: 'bg-green-50' },
  partial: { icon: CircleDot, color: 'text-amber-500', bg: 'bg-amber-50' },
  defective: { icon: AlertTriangle, color: 'text-red-500', bg: 'bg-red-50' },
  not_relevant: { icon: MinusCircle, color: 'text-slate-400', bg: 'bg-slate-50' },
  not_checked: { icon: Circle, color: 'text-slate-300', bg: 'bg-white' },
};

const HandoverSectionPage = () => {
  const { projectId, unitId, protocolId, sectionId } = useParams();
  const navigate = useNavigate();

  const [protocol, setProtocol] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState(null);
  const [markingAll, setMarkingAll] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

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

  const section = protocol?.sections?.find(s => s.section_id === sectionId);
  const isSigned = protocol?.locked === true;

  if (!section) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4" dir="rtl">
        <p className="text-slate-500">{t('handover', 'loadError')}</p>
        <button
          onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}`)}
          className="text-purple-600 hover:text-purple-700 font-medium"
        >
          {t('handover', 'backToProtocol')}
        </button>
      </div>
    );
  }

  const items = section.items || [];
  const notCheckedItems = items.filter(i => !i.status || i.status === 'not_checked');
  const checkedCount = items.filter(i => i.status && i.status !== 'not_checked').length;

  const handleMarkAllOk = async () => {
    setShowConfirm(false);
    if (notCheckedItems.length === 0 || isSigned) return;
    try {
      setMarkingAll(true);
      for (const item of notCheckedItems) {
        await handoverService.updateItem(projectId, protocolId, sectionId, item.item_id, {
          status: 'ok',
        });
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

  const handleItemUpdated = () => {
    loadProtocol();
  };

  const currentItem = selectedItem
    ? items.find(i => i.item_id === selectedItem)
    : null;

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className={`bg-gradient-to-l ${isSigned ? 'from-green-600 to-green-700' : 'from-purple-600 to-purple-700'} text-white`}>
        <div className="max-w-lg mx-auto px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}`)}
              className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-bold truncate">{section.name}</h1>
              <p className="text-purple-200 text-xs">
                {checkedCount}/{items.length} {t('handover', 'checkedItems')}
              </p>
            </div>
          </div>
        </div>
      </div>

      {!isSigned && notCheckedItems.length > 0 && (
        <div className="max-w-lg mx-auto px-4 mt-3">
          {showConfirm ? (
            <div className="bg-green-50 border border-green-200 rounded-xl p-3 space-y-2">
              <p className="text-sm text-green-800 font-medium text-center">
                {t('handover', 'markAllOkConfirm').replace('{count}', notCheckedItems.length)}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleMarkAllOk}
                  disabled={markingAll}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-green-500 text-white rounded-lg
                    text-sm font-medium hover:bg-green-600 disabled:opacity-50"
                >
                  {markingAll ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <CheckCheck className="w-3.5 h-3.5" />
                  )}
                  {t('handover', 'statusOk')}
                </button>
                <button
                  onClick={() => setShowConfirm(false)}
                  className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg text-sm font-medium hover:bg-slate-200"
                >
                  ביטול
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowConfirm(true)}
              disabled={markingAll}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-green-500 text-white rounded-xl
                text-sm font-medium hover:bg-green-600 active:scale-[0.98] disabled:opacity-50"
            >
              <CheckCheck className="w-4 h-4" />
              {t('handover', 'markAllOk')} ({notCheckedItems.length})
            </button>
          )}
        </div>
      )}

      <div className="max-w-lg mx-auto px-4 mt-3 space-y-1.5 pb-8">
        {items.map(item => {
          const statusInfo = STATUS_ICONS[item.status || 'not_checked'] || STATUS_ICONS.not_checked;
          const StatusIcon = statusInfo.icon;
          const hasDefect = !!item.defect_id;

          return (
            <Card
              key={item.item_id}
              className={`p-3 border transition-all cursor-pointer active:scale-[0.98] ${
                isSigned ? 'border-green-200 bg-green-50/30' : 'border-slate-200 hover:border-purple-300'
              }`}
              onClick={() => setSelectedItem(item.item_id)}
            >
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${statusInfo.bg}`}>
                  <StatusIcon className={`w-4 h-4 ${statusInfo.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium text-slate-800 truncate">{item.name}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">{item.trade}</span>
                    {hasDefect && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/tasks/${item.defect_id}`);
                        }}
                        className="flex items-center gap-0.5 text-[10px] text-red-600 bg-red-50 px-1.5 py-0.5 rounded font-medium"
                      >
                        <Bug className="w-2.5 h-2.5" />
                        {t('handover', 'viewDefect')}
                        <ExternalLink className="w-2.5 h-2.5" />
                      </button>
                    )}
                    {item.notes && (
                      <span className="text-[10px] text-slate-400">💬</span>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <HandoverItemModal
        open={!!selectedItem}
        onClose={() => setSelectedItem(null)}
        item={currentItem}
        sectionId={sectionId}
        projectId={projectId}
        protocolId={protocolId}
        isSigned={isSigned}
        onItemUpdated={handleItemUpdated}
      />
    </div>
  );
};

export default HandoverSectionPage;
