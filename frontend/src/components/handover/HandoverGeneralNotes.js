import React, { useState, useEffect, useCallback } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { Loader2 } from 'lucide-react';

const FIELDS = [
  { key: 'apartment', label: t('handover', 'apartment') },
  { key: 'storage', label: t('handover', 'storage') },
  { key: 'parking', label: t('handover', 'parking') },
];

const HandoverGeneralNotes = ({ protocol, projectId, isSigned, onUpdated }) => {
  const [notes, setNotes] = useState({ apartment: '', storage: '', parking: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setNotes(protocol?.general_notes || { apartment: '', storage: '', parking: '' });
  }, [protocol]);

  const handleSave = useCallback(async () => {
    if (isSigned || saving) return;
    try {
      setSaving(true);
      await handoverService.updateProtocol(projectId, protocol.id, {
        general_notes: notes,
      });
      toast.success(t('handover', 'saved'));
      onUpdated?.();
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  }, [notes, isSigned, saving, projectId, protocol?.id, onUpdated]);

  return (
    <div className="space-y-3 p-1">
      {FIELDS.map(f => (
        <div key={f.key} className="space-y-1">
          <label className="text-xs font-medium text-slate-600">{f.label}</label>
          <textarea
            value={notes[f.key] || ''}
            onChange={(e) => setNotes(prev => ({ ...prev, [f.key]: e.target.value }))}
            disabled={isSigned}
            className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-sm resize-none h-16
              focus:outline-none focus:ring-2 focus:ring-purple-300
              disabled:bg-slate-50 disabled:text-slate-500"
            dir="rtl"
          />
        </div>
      ))}
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

export default HandoverGeneralNotes;
