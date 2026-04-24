export const CATEGORY_TO_BUCKET = {
  electrical: 'electrical',
  plumbing: 'plumbing',
  painting: 'painting',
  carpentry: 'carpentry_kitchen',
  carpentry_kitchen: 'carpentry_kitchen',
  bathroom_cabinets: 'bathroom_cabinets',
  finishes: 'finishes',
  structural: 'structural',
  masonry: 'structural',
  aluminum: 'aluminum',
  metalwork: 'metalwork',
  flooring: 'flooring',
  hvac: 'hvac',
  glazing: 'glazing',
  windows: 'glazing',
  doors: 'doors',
  general: 'general',
};

export const BUCKET_LABELS = {
  electrical: 'חשמלאי',
  plumbing: 'אינסטלטור',
  painting: 'צבעי',
  carpentry_kitchen: 'נגרות/מטבח',
  bathroom_cabinets: 'ארונות אמבטיה',
  finishes: 'גמרים',
  structural: 'שלד',
  aluminum: 'אלומיניום',
  metalwork: 'מסגרות',
  flooring: 'ריצוף',
  hvac: 'מיזוג',
  glazing: 'חלונות/זכוכית',
  doors: 'דלתות',
  general: 'כללי',
};

export function getBucketForTrade(keyOrCategory) {
  if (!keyOrCategory) return null;
  const k = String(keyOrCategory).trim();
  if (!k) return null;
  return CATEGORY_TO_BUCKET[k] || k;
}

export function getBucketLabel(bucket) {
  if (!bucket) return '';
  return BUCKET_LABELS[bucket] || bucket;
}

export function isSameTradeBucket(a, b) {
  const ba = getBucketForTrade(a);
  const bb = getBucketForTrade(b);
  return !!ba && !!bb && ba === bb;
}
