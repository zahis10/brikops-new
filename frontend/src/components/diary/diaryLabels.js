// Work Diary (יומן עבודה) — Hebrew label maps. Batch diary-d2.
// Mirrors the safetyLabels.js convention: plain exported consts, no logic.

// Stored on the entry as { desc, source: 'manual' } (weather is always manual).
export const WEATHER_OPTIONS = [
  'בהיר',
  'מעונן חלקית',
  'מעונן',
  'גשם',
  'רוח חזקה',
  'שרב',
];

export const STATUS_HE = {
  draft: 'טיוטה',
  signed: 'חתום',
};

export const NO_WORK_REASONS = ['שבת', 'חג', 'גשם', 'אחר'];

export const SECTION_TITLES = {
  work_description: 'תיאור עבודות',
  workers_by_company: 'עובדים באתר',
  subcontractors: 'קבלני משנה',
  equipment_list: 'ציוד באתר',
  materials_received: 'חומרים שהגיעו',
  weather: 'מזג אוויר',
  incidents_summary: 'אירועי בטיחות',
  tours_summary: 'סיורים',
  trainings_summary: 'הדרכות',
  defect_counts: 'ליקויים',
  inspector_visit: 'ביקורת מפקח',
  special_instructions: 'הוראות מיוחדות',
  photos: 'תמונות מהיום',
  addendums: 'תוספות',
};

// The locked transparency reservation (concept decision 6) — shown under every
// derived row/section so the user knows the data is a suggestion, not a gate.
export const DERIVED_HINT = 'נגזר מרישום הבטיחות · עדכן אם שונה';
