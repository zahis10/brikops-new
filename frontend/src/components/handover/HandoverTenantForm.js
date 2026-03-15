import React, { useState, useEffect, useCallback } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { Loader2, Plus, Trash2 } from 'lucide-react';

const EMPTY_TENANT = { name: '', id_number: '', phone: '', email: '', id_photo_url: null };

const HandoverTenantForm = ({ protocol, projectId, isSigned, onUpdated }) => {
  const [tenants, setTenants] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const t = protocol?.tenants || [];
    setTenants(t.length > 0 ? t : [{ ...EMPTY_TENANT }]);
  }, [protocol]);

  const handleFieldChange = (idx, field, value) => {
    setTenants(prev => prev.map((ten, i) =>
      i === idx ? { ...ten, [field]: value } : ten
    ));
  };

  const addTenant = () => {
    setTenants(prev => [...prev, { ...EMPTY_TENANT }]);
  };

  const removeTenant = (idx) => {
    if (tenants.length <= 1) return;
    setTenants(prev => prev.filter((_, i) => i !== idx));
  };

  const handleSave = useCallback(async () => {
    if (isSigned || saving) return;
    try {
      setSaving(true);
      await handoverService.updateProtocol(projectId, protocol.id, {
        tenants,
      });
      toast.success(t('handover', 'saved'));
      onUpdated?.();
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  }, [tenants, isSigned, saving, projectId, protocol?.id, onUpdated]);

  return (
    <div className="space-y-3 p-1">
      {tenants.map((tenant, idx) => (
        <div key={idx} className="border border-slate-200 rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">{t('handover', 'tenants')} {idx + 1}</span>
            {!isSigned && tenants.length > 1 && (
              <button
                onClick={() => removeTenant(idx)}
                className="text-red-400 hover:text-red-600 p-1"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label className="text-[10px] font-medium text-slate-500">{t('handover', 'tenantName')}</label>
              <input
                value={tenant.name || ''}
                onChange={(e) => handleFieldChange(idx, 'name', e.target.value)}
                disabled={isSigned}
                className="w-full px-2 py-1.5 border border-slate-200 rounded text-sm
                  focus:outline-none focus:ring-2 focus:ring-purple-300
                  disabled:bg-slate-50 disabled:text-slate-500"
                dir="rtl"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-medium text-slate-500">{t('handover', 'tenantId')}</label>
              <input
                value={tenant.id_number || ''}
                onChange={(e) => handleFieldChange(idx, 'id_number', e.target.value)}
                disabled={isSigned}
                className="w-full px-2 py-1.5 border border-slate-200 rounded text-sm
                  focus:outline-none focus:ring-2 focus:ring-purple-300
                  disabled:bg-slate-50 disabled:text-slate-500"
                dir="ltr"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-medium text-slate-500">{t('handover', 'tenantPhone')}</label>
              <input
                type="tel"
                value={tenant.phone || ''}
                onChange={(e) => handleFieldChange(idx, 'phone', e.target.value)}
                disabled={isSigned}
                className="w-full px-2 py-1.5 border border-slate-200 rounded text-sm
                  focus:outline-none focus:ring-2 focus:ring-purple-300
                  disabled:bg-slate-50 disabled:text-slate-500"
                dir="ltr"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-medium text-slate-500">{t('handover', 'tenantEmail')}</label>
              <input
                type="email"
                value={tenant.email || ''}
                onChange={(e) => handleFieldChange(idx, 'email', e.target.value)}
                disabled={isSigned}
                className="w-full px-2 py-1.5 border border-slate-200 rounded text-sm
                  focus:outline-none focus:ring-2 focus:ring-purple-300
                  disabled:bg-slate-50 disabled:text-slate-500"
                dir="ltr"
              />
            </div>
          </div>
        </div>
      ))}
      {!isSigned && (
        <div className="flex gap-2">
          <button
            onClick={addTenant}
            className="flex items-center gap-1.5 text-xs text-purple-600 hover:text-purple-800 font-medium px-2 py-1"
          >
            <Plus className="w-3.5 h-3.5" />
            {t('handover', 'addTenant')}
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 flex items-center justify-center gap-2 py-2 bg-purple-600 text-white rounded-lg
              text-sm font-medium hover:bg-purple-700 active:scale-[0.98] disabled:opacity-50"
          >
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {saving ? t('handover', 'saving') : t('handover', 'save')}
          </button>
        </div>
      )}
    </div>
  );
};

export default HandoverTenantForm;
