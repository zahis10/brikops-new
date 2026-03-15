import React, { useState, useEffect, useCallback } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { Loader2 } from 'lucide-react';

const HandoverDeliveredItems = ({ protocol, projectId, isSigned, onUpdated }) => {
  const [items, setItems] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setItems(protocol?.delivered_items || []);
  }, [protocol]);

  const handleChange = (idx, field, value) => {
    setItems(prev => prev.map((item, i) =>
      i === idx ? { ...item, [field]: field === 'quantity' ? (value === '' ? null : Number(value)) : value } : item
    ));
  };

  const handleSave = useCallback(async () => {
    if (isSigned || saving) return;
    try {
      setSaving(true);
      await handoverService.updateProtocol(projectId, protocol.id, {
        delivered_items: items,
      });
      toast.success(t('handover', 'saved'));
      onUpdated?.();
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  }, [items, isSigned, saving, projectId, protocol?.id, onUpdated]);

  return (
    <div className="space-y-2 p-1">
      {items.map((item, idx) => (
        <div key={idx} className="flex items-center gap-2 border border-slate-200 rounded-lg p-2">
          <span className="text-xs font-medium text-slate-700 flex-1 min-w-0 truncate">{item.name}</span>
          <div className="flex items-center gap-2 flex-shrink-0">
            <input
              type="number"
              value={item.quantity ?? ''}
              onChange={(e) => handleChange(idx, 'quantity', e.target.value)}
              disabled={isSigned}
              placeholder={t('handover', 'quantity')}
              className="w-16 px-2 py-1 border border-slate-200 rounded text-xs text-center
                focus:outline-none focus:ring-2 focus:ring-purple-300
                disabled:bg-slate-50 disabled:text-slate-500"
              dir="ltr"
            />
            <input
              value={item.notes || ''}
              onChange={(e) => handleChange(idx, 'notes', e.target.value)}
              disabled={isSigned}
              placeholder={t('handover', 'notes')}
              className="w-24 px-2 py-1 border border-slate-200 rounded text-xs
                focus:outline-none focus:ring-2 focus:ring-purple-300
                disabled:bg-slate-50 disabled:text-slate-500"
              dir="rtl"
            />
          </div>
        </div>
      ))}
      {!isSigned && items.length > 0 && (
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full flex items-center justify-center gap-2 py-2 bg-purple-600 text-white rounded-lg
            text-sm font-medium hover:bg-purple-700 active:scale-[0.98] disabled:opacity-50"
        >
          {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          {saving ? t('handover', 'saving') : t('handover', 'save')}
        </button>
      )}
    </div>
  );
};

export default HandoverDeliveredItems;
