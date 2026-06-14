import React, { useState, useEffect, useCallback, useRef } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { Loader2, Camera } from 'lucide-react';
import { compressImage } from '../../utils/imageCompress';
import { FEATURES } from '../../config/features';
import { enqueueHandoverForm, getHandoverFormUpdate, enqueueMeterPhoto, getMeterPhoto } from '../../services/offlineOutbox';

// FIX 1 — display_url is session-local derived state (often a blob: object URL,
// valid ONLY in the document that created it). It must NEVER be persisted — not to
// the outbox, not to the server (get_protocol regenerates it per-GET from photo_url).
function _stripDisplayUrls(m) {
  const out = {};
  for (const t of ['water', 'electricity']) {
    if (m && m[t] && typeof m[t] === 'object') {
      const { display_url, ...rest } = m[t];
      out[t] = rest;
    } else if (m && m[t] !== undefined) {
      out[t] = m[t];
    }
  }
  return out;
}

const MeterCard = ({ type, label, icon, borderColor, meters, isSigned, projectId, protocolId, onChange, onPhotoUploaded, onPhotoQueued }) => {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const photoUrl = meters[type]?.display_url || null;

  const handlePhoto = async (e) => {
    const file = e.target.files?.[0];
    if (!file || isSigned) return;
    let compressed = null;
    try {
      setUploading(true);
      compressed = await compressImage(file);
      // BATCH 4c — meter photos are NOT PII (a utility dial). OFFLINE: queue the
      // compressed blob (latest-wins per meter) and preview locally. The blob drains
      // AFTER the form so the deterministic photo_url subfield write survives.
      if (FEATURES.OFFLINE_MODE && navigator.onLine === false) {
        await enqueueMeterPhoto(projectId, protocolId, type, compressed);
        onPhotoQueued?.(type, URL.createObjectURL(compressed));
        toast.success('נשמר במכשיר — יישלח כשתחזור הרשת');
        return;
      }
      const result = await handoverService.uploadMeterPhoto(projectId, protocolId, type, compressed);
      onPhotoUploaded?.(type, result);
      toast.success('תמונה הועלתה');
    } catch (err) {
      // REACTIVE: network-failed mid-upload (went offline) — queue instead of error.
      if (FEATURES.OFFLINE_MODE && compressed && (!err || !err.response)) {
        await enqueueMeterPhoto(projectId, protocolId, type, compressed);
        onPhotoQueued?.(type, URL.createObjectURL(compressed));
        toast.success('נשמר במכשיר — יישלח כשתחזור הרשת');
        return;
      }
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
  const [queued, setQueued] = useState(false);
  // BATCH 4c — track object URLs created for queued meter-photo previews so we can
  // revoke them on unmount / replacement (no leak — 3b discipline). Keyed by type.
  const objectUrlsRef = useRef({});

  const _trackObjectUrl = useCallback((type, url) => {
    const prev = objectUrlsRef.current[type];
    if (prev && prev !== url) { try { URL.revokeObjectURL(prev); } catch (_) { /* noop */ } }
    objectUrlsRef.current[type] = url;
  }, []);

  useEffect(() => {
    if (protocol?.meters) {
      setMeters(protocol.meters);
    }
    setQueued(false);
    // HYDRATE: meter readings captured offline outlive a reload (fail-soft).
    if (FEATURES.OFFLINE_MODE && protocol?.id) {
      getHandoverFormUpdate(protocol.id, 'meters').then((rec) => {
        if (rec && rec.value) {
          // FIX 1 — merge readings/photo_url from the queued record but PRESERVE the
          // live display_url (a fresh blob preview); never reinstate a dead blob URL.
          setMeters((prev) => {
            const v = _stripDisplayUrls(rec.value);
            return {
              water: { ...prev.water, ...(v.water || {}) },
              electricity: { ...prev.electricity, ...(v.electricity || {}) },
            };
          });
          setQueued(true);
        }
      }).catch(() => {});
      // BATCH 4c — hydrate queued meter photos (blob → object URL preview).
      ['water', 'electricity'].forEach((type) => {
        getMeterPhoto(protocol.id, type).then((rec) => {
          if (rec && rec.blob) {
            const url = URL.createObjectURL(rec.blob);
            _trackObjectUrl(type, url);
            setMeters((prev) => ({ ...prev, [type]: { ...prev[type], display_url: url } }));
            setQueued(true);
          }
        }).catch(() => {});
      });
    }
  }, [protocol, _trackObjectUrl]);

  // Revoke any queued-preview object URLs on unmount.
  useEffect(() => () => {
    Object.values(objectUrlsRef.current).forEach((u) => { try { URL.revokeObjectURL(u); } catch (_) { /* noop */ } });
  }, []);

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

  // BATCH 4c — meter photo queued offline. Set ONLY display_url for the local
  // preview; leave photo_url untouched (the server assigns it at sync, and the
  // photos-LAST drain order keeps that fresh value safe). Do NOT call onUpdated()
  // — a parent reload would re-fetch the cached protocol and drop the preview.
  const handlePhotoQueued = useCallback((type, objectUrl) => {
    _trackObjectUrl(type, objectUrl);
    setMeters(prev => ({
      ...prev,
      [type]: { ...prev[type], display_url: objectUrl },
    }));
    setQueued(true);
  }, [_trackObjectUrl]);

  const handleSave = useCallback(async () => {
    if (isSigned || saving) return;
    // FIX 1 — strip display_url from EVERY persisted payload (outbox + server). The
    // local `meters` state keeps it for the on-screen preview; it is never stored.
    const payload = _stripDisplayUrls(meters);
    // PROACTIVE offline capture → outbox. DO NOT call onUpdated() (parent reload
    // would re-fetch the cached protocol and reset meters via the effect).
    if (FEATURES.OFFLINE_MODE && navigator.onLine === false) {
      await enqueueHandoverForm(projectId, protocol.id, 'meters', payload);
      setQueued(true);
      toast.success('נשמר במכשיר — יישלח כשתחזור הרשת');
      return;
    }
    try {
      setSaving(true);
      await handoverService.updateProtocol(projectId, protocol.id, { meters: payload });
      toast.success(t('handover', 'saved'));
      onUpdated?.();
    } catch (err) {
      // REACTIVE: network-failed mid-save (offline) — capture instead of error.
      if (FEATURES.OFFLINE_MODE && (!err || !err.response)) {
        await enqueueHandoverForm(projectId, protocol.id, 'meters', payload);
        setQueued(true);
        toast.success('נשמר במכשיר — יישלח כשתחזור הרשת');
        return;
      }
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
        onChange={handleChange} onPhotoUploaded={handlePhotoUploaded} onPhotoQueued={handlePhotoQueued}
      />
      <MeterCard
        type="electricity" label={t('handover', 'electricityReading')} icon="⚡"
        borderColor="border-amber-300 text-amber-600"
        meters={meters} isSigned={isSigned}
        projectId={projectId} protocolId={protocol?.id}
        onChange={handleChange} onPhotoUploaded={handlePhotoUploaded} onPhotoQueued={handlePhotoQueued}
      />

      {!isSigned && (
        <>
          {queued && (
            <p className="text-[11px] text-amber-600 text-center">ממתין לשליחה</p>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full flex items-center justify-center gap-2 py-2 bg-purple-600 text-white rounded-lg
              text-sm font-medium hover:bg-purple-700 active:scale-[0.98] disabled:opacity-50"
          >
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {saving ? t('handover', 'saving') : t('handover', 'save')}
          </button>
        </>
      )}
    </div>
  );
};

export default HandoverMeterForm;
