import React, { useState, useEffect, useCallback, useRef } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { Loader2, Camera } from 'lucide-react';

const MeterCard = ({ type, label, icon, borderColor, meters, isSigned, projectId, protocolId, onChange, onPhotoUploaded }) => {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const photoUrl = meters[type]?.display_url || null;

  const handlePhoto = async (e) => {
    const file = e.target.files?.[0];
    if (!file || isSigned) return;
    try {
      setUploading(true);
      const result = await handoverService.uploadMeterPhoto(projectId, protocolId, type, file);
      onPhotoUploaded?.(type, result);
      toast.success('תמונה הועלתה');
    } catch (err) {
      console.error(err);
      toast.error('שגיאה בהעלאת תמונה');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  return (
    <div className="border border-slate-200 rounded-lg p-3 space-y-2">
      <span className="text-xs font-semibold text-slate-500">{icon} {label}</span>
      <input
        type="number"
        value={meters[type]?.reading ?? ''}
        onChange={(e) => onChange(type, 'reading', e.target.value)}
        disabled={isSigned}
        className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-sm
          focus:outline-none focus:ring-2 focus:ring-purple-300
          disabled:bg-slate-50 disabled:text-slate-500"
        dir="ltr"
      />

      {photoUrl && (
        <div className="relative inline-block">
          <img src={photoUrl} alt={label} className="w-24 h-18 object-cover rounded-lg border border-slate-200" />
        </div>
      )}

      {!isSigned && (
        <div>
          <input ref={fileRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handlePhoto} />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-colors
              ${borderColor} hover:bg-slate-50 disabled:opacity-50`}
          >
            {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Camera className="w-3.5 h-3.5" />}
            {uploading ? 'מעלה...' : photoUrl ? 'החלף תמונה' : 'צלם מונה'}
          </button>
        </div>
      )}
    </div>
  );
};

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

  const handlePhotoUploaded = useCallback((type, result) => {
    setMeters(prev => ({
      ...prev,
      [type]: { ...prev[type], photo_url: result.photo_url, display_url: result.display_url },
    }));
    onUpdated?.();
  }, [onUpdated]);

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
      <MeterCard
        type="water" label={t('handover', 'waterReading')} icon="💧"
        borderColor="border-sky-300 text-sky-600"
        meters={meters} isSigned={isSigned}
        projectId={projectId} protocolId={protocol?.id}
        onChange={handleChange} onPhotoUploaded={handlePhotoUploaded}
      />
      <MeterCard
        type="electricity" label={t('handover', 'electricityReading')} icon="⚡"
        borderColor="border-amber-300 text-amber-600"
        meters={meters} isSigned={isSigned}
        projectId={projectId} protocolId={protocol?.id}
        onChange={handleChange} onPhotoUploaded={handlePhotoUploaded}
      />

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
