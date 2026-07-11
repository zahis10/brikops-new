// Work Diary (יומן עבודה) — Hebrew label maps. Batch diary-d2.
// Mirrors the safetyLabels.js convention: plain exported consts, no logic.

// d4b — FE copy of the backend's IL_WEATHER_CITIES (services/weather_il.py,
// the single source of truth). IMS city-forecast codes, Hebrew labels.
export const IL_WEATHER_CITIES = [
  { code: '520', label: 'אילת' },
  { code: '114', label: 'אשדוד' },
  { code: '513', label: 'באר שבע' },
  { code: '203', label: 'בית שאן' },
  { code: '115', label: 'חיפה' },
  { code: '202', label: 'טבריה' },
  { code: '510', label: 'ירושלים' },
  { code: '204', label: 'לוד' },
  { code: '106', label: 'מצפה רמון' },
  { code: '207', label: 'נצרת' },
  { code: '105', label: 'עין גדי' },
  { code: '209', label: 'עפולה' },
  { code: '507', label: 'צפת' },
  { code: '201', label: 'קצרין' },
  { code: '402', label: 'תל אביב - יפו' },
];

// Stored on the entry as { desc, source: 'manual' } when picked by hand;
// d4b adds a derived variant { desc: 'תחזית: …', source: 'derived' }.
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
