import React, { useState, useCallback } from 'react';
import { Capacitor } from '@capacitor/core';
import { Contacts } from '@capacitor-community/contacts';
import { toast } from 'sonner';

function normalizePhone(raw) {
  if (!raw) return '';
  let p = String(raw).replace(/[^\d+]/g, '');
  if (p.startsWith('+972')) p = '0' + p.slice(4);
  else if (p.startsWith('972')) p = '0' + p.slice(3);
  else if (p.startsWith('+')) p = p.slice(1);
  return p;
}

export default function ContactPickerButton({ onPhonePicked, disabled = false, className = '' }) {
  const [busy, setBusy] = useState(false);

  const handlePick = useCallback(async () => {
    if (disabled || busy) return;
    setBusy(true);
    try {
      const perm = await Contacts.requestPermissions();
      if (perm.contacts !== 'granted' && perm.contacts !== 'limited') {
        toast.error('אין הרשאה לאנשי קשר. ניתן להפעיל ב-Settings.');
        return;
      }
      const result = await Contacts.pickContact({
        projection: { phones: true, name: true },
      });
      const phones = result?.contact?.phones || [];
      if (phones.length === 0) {
        toast.warning('לאיש הקשר שנבחר אין מספר טלפון');
        return;
      }
      const phone = normalizePhone(phones[0].number);
      if (phone && typeof onPhonePicked === 'function') {
        onPhonePicked(phone);
      }
    } catch (err) {
      console.warn('[ContactPicker] error:', err);
    } finally {
      setBusy(false);
    }
  }, [disabled, busy, onPhonePicked]);

  if (!Capacitor.isNativePlatform()) return null;

  return (
    <button
      type="button"
      onClick={handlePick}
      disabled={disabled || busy}
      className={`px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white hover:bg-slate-50 disabled:opacity-50 ${className}`}
      aria-label="בחר מאנשי קשר"
    >
      📇 בחר מאנשי קשר
    </button>
  );
}
