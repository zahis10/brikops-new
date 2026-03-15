import React, { useState, useEffect, useCallback } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { Loader2 } from 'lucide-react';

const HandoverMeterForm = ({ protocol, projectId, isSigned, onUpdated }) => {
  const [meters, setMeters] = useState({ water: { reading: null, photo_url: null }, electricity: { reading: null, photo_url: null } });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (protocol?.meters) {
      setMeters(protocol.meters);
    }
  }, [protocol]);

  const handleChange = (type, field, value) => {
    setMeters(prev => ({
      ...prev,
      [type]: { ...prev[type], [field]: value === '' ? null : (field === 'reading' ? Number(value) : value) },
    }));
  };

  const handleSave = useCallback(async () => {
    if (isSigned || saving) return;
    try {
      setSaving(true);
      await handoverService.updateProtocol(projectId, protocol.id, { meters });
      toast.success(t('handover', 'saved'));
      onUpdated?.();
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  }, [meters, isSigned, saving, projectId, protocol?.id, onUpdated]);

  return (
    <div className="space-y-3 p-1">
      <div className="border border-slate-200 rounded-lg p-3 space-y-2">
        <span className="text-xs font-semibold text-slate-500">{t('handover', 'waterReading')}</span>
        <input
          type="number"
          value={meters.water?.reading ?? ''}
          onChange={(e) => handleChange('water', 'reading', e.target.value)}
          disabled={isSigned}
          className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-sm
            focus:outline-none focus:ring-2 focus:ring-purple-300
            disabled:bg-slate-50 disabled:text-slate-500"
          dir="ltr"
        />
      </div>

      <div className="border border-slate-200 rounded-lg p-3 space-y-2">
        <span className="text-xs font-semibold text-slate-500">{t('handover', 'electricityReading')}</span>
        <input
          type="number"
          value={meters.electricity?.reading ?? ''}
          onChange={(e) => handleChange('electricity', 'reading', e.target.value)}
          disabled={isSigned}
          className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-sm
            focus:outline-none focus:ring-2 focus:ring-purple-300
            disabled:bg-slate-50 disabled:text-slate-500"
          dir="ltr"
        />
      </div>

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

export default HandoverMeterForm;
