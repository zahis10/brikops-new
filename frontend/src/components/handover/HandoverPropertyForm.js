import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { Loader2 } from 'lucide-react';

const HARDCODED_FIELDS = [
  { key: 'rooms', label: t('handover', 'rooms'), type: 'number' },
  { key: 'storage_num', label: t('handover', 'storageNum'), type: 'number' },
  { key: 'parking_num', label: t('handover', 'parkingNum'), type: 'number' },
  { key: 'model', label: t('handover', 'model'), type: 'text' },
  { key: 'area', label: t('handover', 'area'), type: 'number' },
  { key: 'balcony_area', label: t('handover', 'balconyArea'), type: 'number' },
  { key: 'parking_area', label: t('handover', 'parkingArea'), type: 'number' },
  { key: 'laundry_area', label: t('handover', 'laundryArea'), type: 'number' },
];

const HandoverPropertyForm = ({ protocol, projectId, isSigned, onUpdated }) => {
  const [values, setValues] = useState({});
  const [saving, setSaving] = useState(false);

  const fields = useMemo(() => {
    const schema = protocol?.property_fields_schema;
    if (schema && Array.isArray(schema) && schema.length > 0) {
      return schema.map(f => ({ key: f.key, label: f.label, type: 'text' }));
    }
    return HARDCODED_FIELDS;
  }, [protocol?.property_fields_schema]);

  useEffect(() => {
    setValues(protocol?.property_details || {});
  }, [protocol]);

  const handleSave = useCallback(async () => {
    if (isSigned || saving) return;
    try {
      setSaving(true);
      await handoverService.updateProtocol(projectId, protocol.id, {
        property_details: values,
      });
      toast.success(t('handover', 'saved'));
      onUpdated?.();
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  }, [values, isSigned, saving, projectId, protocol?.id, onUpdated]);

  return (
    <div className="space-y-3 p-1">
      <div className="grid grid-cols-2 gap-3">
        {fields.map(f => (
          <div key={f.key} className="space-y-1">
            <label className="text-xs font-medium text-slate-600">{f.label}</label>
            <input
              type={f.type}
              value={values[f.key] ?? ''}
              onChange={(e) => setValues(prev => ({
                ...prev,
                [f.key]: f.type === 'number' ? (e.target.value === '' ? null : Number(e.target.value)) : e.target.value,
              }))}
              disabled={isSigned}
              className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-sm
                focus:outline-none focus:ring-2 focus:ring-purple-300
                disabled:bg-slate-50 disabled:text-slate-500"
              dir="rtl"
            />
          </div>
        ))}
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

export default HandoverPropertyForm;
