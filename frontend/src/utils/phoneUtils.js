const UNICODE_DIRECTIONAL = /[\u200e\u200f\u200b\u200c\u200d\u2028\u2029\u202a-\u202e\u2066-\u2069\ufeff]/g;

export const canonicalE164 = (phone) => {
  if (!phone || typeof phone !== 'string') return '';
  const cleaned = phone.replace(UNICODE_DIRECTIONAL, '').replace(/[-\s()\.\u00a0]/g, '');
  if (!cleaned) return '';

  if (cleaned.startsWith('+972') && cleaned.length === 13) return cleaned;
  if (cleaned.startsWith('972') && cleaned.length === 12) return '+' + cleaned;
  if (cleaned.startsWith('05') && cleaned.length === 10) return '+972' + cleaned.slice(1);
  if (cleaned.startsWith('5') && cleaned.length === 9) return '+972' + cleaned;

  if (cleaned.startsWith('+')) return cleaned;
  return '+' + cleaned;
};

export const isValidIsraeliMobile = (e164) => {
  return /^\+972[5][0-9]\d{7}$/.test(e164);
};
