import React, { useState, useEffect } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { useNavigate } from 'react-router-dom';
import {
  Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerDescription,
} from '../ui/drawer';
import {
  CheckCircle2, AlertTriangle, CircleDot, MinusCircle, RotateCcw,
  Bug, ExternalLink, Loader2, X
} from 'lucide-react';

const STATUS_OPTIONS = [
  { value: 'ok', label: t('handover', 'statusOk'), icon: CheckCircle2, color: 'bg-green-100 text-green-700 border-green-300', activeColor: 'bg-green-500 text-white border-green-500' },
  { value: 'partial', label: t('handover', 'statusPartial'), icon: CircleDot, color: 'bg-amber-100 text-amber-700 border-amber-300', activeColor: 'bg-amber-500 text-white border-amber-500' },
  { value: 'defective', label: t('handover', 'statusDefective'), icon: AlertTriangle, color: 'bg-red-100 text-red-700 border-red-300', activeColor: 'bg-red-500 text-white border-red-500' },
  { value: 'not_relevant', label: t('handover', 'statusNotRelevant'), icon: MinusCircle, color: 'bg-slate-100 text-slate-600 border-slate-300', activeColor: 'bg-slate-500 text-white border-slate-500' },
  { value: 'not_checked', label: t('handover', 'statusReset'), icon: RotateCcw, color: 'bg-slate-50 text-slate-500 border-slate-200', activeColor: 'bg-slate-400 text-white border-slate-400' },
];

const HandoverItemModal = ({
  open, onClose, item, sectionId, projectId, protocolId, isSigned, onItemUpdated,
}) => {
  const navigate = useNavigate();
  const [status, setStatus] = useState(item?.status || 'not_checked');
  const [notes, setNotes] = useState(item?.notes || '');
  const [saving, setSaving] = useState(false);
  const [creatingDefect, setCreatingDefect] = useState(false);

  useEffect(() => {
    if (item) {
      setStatus(item.status || 'not_checked');
      setNotes(item.notes || '');
    }
  }, [item]);

  if (!item) return null;

  const hasDefect = !!item.defect_id;
  const showCreateDefect = !hasDefect && (status === 'defective' || status === 'partial');

  const handleStatusChange = async (newStatus) => {
    if (isSigned || saving) return;
    setStatus(newStatus);
    try {
      setSaving(true);
      await handoverService.updateItem(projectId, protocolId, sectionId, item.item_id, {
        status: newStatus,
      });
      onItemUpdated?.();
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  };

  const handleNotesSave = async () => {
    if (isSigned || saving) return;
    try {
      setSaving(true);
      await handoverService.updateItem(projectId, protocolId, sectionId, item.item_id, {
        notes,
      });
      toast.success(t('handover', 'itemUpdated'));
      onItemUpdated?.();
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  };

  const handleCreateDefect = async () => {
    if (isSigned || creatingDefect || hasDefect) return;
    try {
      setCreatingDefect(true);
      const result = await handoverService.createDefectFromItem(projectId, protocolId, item.item_id, {});
      toast.success(t('handover', 'defectCreated'));
      onItemUpdated?.();
      onClose();
      if (result?.task_id) {
        navigate(`/tasks/${result.task_id}`);
      }
    } catch (err) {
      if (err?.response?.status === 409) {
        toast.error(t('handover', 'defectExists'));
        onItemUpdated?.();
      } else {
        toast.error(t('handover', 'updateError'));
        console.error(err);
      }
    } finally {
      setCreatingDefect(false);
    }
  };

  return (
    <Drawer open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DrawerContent className="max-h-[85vh]" dir="rtl">
        <DrawerHeader className="text-right">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <DrawerTitle className="text-base font-bold text-slate-800 truncate">
                {item.name}
              </DrawerTitle>
              <DrawerDescription className="text-xs text-slate-500 mt-0.5">
                {item.trade}
              </DrawerDescription>
            </div>
            <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg">
              <X className="w-4 h-4 text-slate-400" />
            </button>
          </div>
        </DrawerHeader>

        <div className="px-4 pb-6 space-y-4 overflow-y-auto">
          {isSigned && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-2 text-center text-sm text-green-700 font-medium">
              {t('handover', 'readOnly')}
            </div>
          )}

          <div className="space-y-2">
            <div className="grid grid-cols-5 gap-1.5">
              {STATUS_OPTIONS.map(opt => {
                const isActive = status === opt.value;
                const Icon = opt.icon;
                return (
                  <button
                    key={opt.value}
                    disabled={isSigned || saving}
                    onClick={() => handleStatusChange(opt.value)}
                    className={`flex flex-col items-center gap-1 p-2 rounded-lg border transition-all text-center
                      ${isActive ? opt.activeColor : opt.color}
                      ${isSigned ? 'opacity-60 cursor-not-allowed' : 'active:scale-95'}`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="text-[10px] font-medium leading-tight">{opt.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {hasDefect && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <div className="flex items-center gap-2">
                <Bug className="w-4 h-4 text-red-500 flex-shrink-0" />
                <span className="text-sm font-medium text-red-700 flex-1">
                  {t('handover', 'defectExists')}
                </span>
                <button
                  onClick={() => { onClose(); navigate(`/tasks/${item.defect_id}`); }}
                  className="flex items-center gap-1 text-xs text-red-600 hover:text-red-800 font-medium"
                >
                  {t('handover', 'viewDefect')}
                  <ExternalLink className="w-3 h-3" />
                </button>
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">{t('handover', 'notes')}</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              onBlur={handleNotesSave}
              disabled={isSigned}
              placeholder={t('handover', 'notesPlaceholder')}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none h-20
                focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-400
                disabled:bg-slate-50 disabled:text-slate-500"
              dir="rtl"
            />
          </div>

          {showCreateDefect && !isSigned && (
            <button
              onClick={handleCreateDefect}
              disabled={creatingDefect}
              className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl font-medium transition-all
                active:scale-[0.98] disabled:opacity-50
                ${status === 'defective'
                  ? 'bg-red-500 text-white hover:bg-red-600'
                  : 'bg-amber-100 text-amber-800 hover:bg-amber-200 border border-amber-300'}`}
            >
              {creatingDefect ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Bug className="w-4 h-4" />
              )}
              {t('handover', 'createDefect')}
            </button>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
};

export default HandoverItemModal;
