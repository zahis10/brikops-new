import React, { useState, useEffect, useCallback } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { Loader2, Plus, Trash2 } from 'lucide-react';

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

  const handleAdd = () => {
    setItems(prev => [...prev, { name: '', quantity: null, notes: '' }]);
  };

  const handleRemove = (idx) => {
    setItems(prev => prev.filter((_, i) => i !== idx));
  };

  const handleSave = useCallback(async () => {
    if (isSigned || saving) return;
    const hasEmpty = items.some(i => !i.name?.trim());
    if (hasEmpty) {
      toast.error('שם פריט לא יכול להיות ריק');
      return;
    }
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
          {isSigned ? (
            <span className="text-xs font-medium text-slate-700 flex-1 min-w-0 truncate">{item.name}</span>
          ) : (
            <input
              value={item.name || ''}
              onChange={(e) => handleChange(idx, 'name', e.target.value)}
              placeholder="שם הפריט"
              className="text-xs font-medium text-slate-700 flex-1 min-w-0 px-2 py-1 border border-transparent rounded
                hover:border-slate-200 focus:border-slate-300 focus:outline-none focus:ring-2 focus:ring-purple-300
                bg-transparent focus:bg-white transition-colors"
              dir="rtl"
            />
          )}
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
            {!isSigned && (
              <button
                onClick={() => handleRemove(idx)}
                className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                title="הסר פריט"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      ))}
      {!isSigned && (
        <div className="flex items-center gap-2">
          <button
            onClick={handleAdd}
            className="flex items-center gap-1.5 text-sm text-purple-600 hover:text-purple-800 font-medium px-3 py-1.5 border border-purple-200 rounded-lg hover:bg-purple-50"
          >
            <Plus className="w-3.5 h-3.5" />
            הוסף פריט
          </button>
        </div>
      )}
      {!isSigned && (
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
