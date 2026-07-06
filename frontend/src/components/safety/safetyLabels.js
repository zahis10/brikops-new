// Shared Hebrew label maps for the Safety module — single source of truth so the
// list badges (SafetyHomePage) and the create/edit forms never drift (CLAUDE.md).

// 10 regulatory safety categories (schemas.py SafetyCategory).
export const CATEGORY_HE = {
  scaffolding: 'פיגומים',
  heights: 'עבודה בגובה',
  electrical_safety: 'בטיחות חשמל',
  lifting: 'הרמה וציוד',
  excavation: 'חפירות',
  fire_safety: 'אש ובטיחות אש',
  ppe: 'ציוד מגן אישי',
  site_housekeeping: 'סדר וניקיון',
  hazardous_materials: 'חומרים מסוכנים',
  other: 'אחר',
};

// Severity 1-3 (schemas.py SafetySeverity).
export const SEVERITY_HE = { '1': 'נמוכה', '2': 'בינונית', '3': 'גבוהה' };

// Safety document status (schemas.py SafetyDocumentStatus).
export const DOC_STATUS_HE = { open: 'פתוח', in_progress: 'בביצוע', resolved: 'נפתר', verified: 'אומת' };

// Safety document kind (schemas.py SafetyDocumentKind) — defect vs observation.
export const KIND_HE = { defect: 'ליקוי', observation: 'תיעוד' };

// Safety task status (schemas.py SafetyTaskStatus / safety_pdf.py TASK_STATUS_HE).
export const TASK_STATUS_HE = { open: 'פתוח', in_progress: 'בביצוע', completed: 'הושלם', cancelled: 'בוטל' };

// Safety incident type (schemas.py SafetyIncidentType / safety_pdf.py).
export const INCIDENT_TYPE_HE = { near_miss: 'כמעט-תאונה', injury: 'פציעה', property_damage: 'נזק לרכוש' };

// Safety incident status (display-only; server owns transitions).
export const INCIDENT_STATUS_HE = { draft: 'טיוטה', reported: 'דווח', closed: 'סגור' };

// Safety tour type (schemas.py SafetyTourType) — batch safety-p2-4b.
export const TOUR_TYPE_HE = {
  officer_monthly: 'דוח ממונה בטיחות',
  assistant_morning: 'דוח עוזר בטיחות — בוקר',
  assistant_evening: 'דוח עוזר בטיחות — ערב',
  custom: 'סיור מותאם',
};

// Safety tour status (schemas.py SafetyTourStatus). signed = batch 4c.
export const TOUR_STATUS_HE = { draft: 'טיוטה', pending_signature: 'ממתין לחתימה', signed: 'חתום' };

// Equipment fitness (batch safety-p3b). Order mirrors schemas.py EQUIPMENT_CATEGORIES.
export const EQUIPMENT_CATEGORY_HE = {
  lifting_accessories: 'אביזרי הרמה',
  lifting_platform: 'במת הרמה',
  electrical_panel: 'לוח חשמל ראשי / משני',
  air_compressor: 'קולט אוויר',
  formwork: 'טפסות',
  forklift: 'מלגזה',
  temporary_power: 'מתקן חשמל ארעי',
  crane_regular: 'עגורן (לא עגורן צריח)',
  tower_crane: 'עגורן צריח',
  scaffolding: 'פיגומים',
};

export const EQUIPMENT_STATUS_HE = { active: 'פעיל', decommissioned: 'הוצא משימוש' };

// result of a PERFORMED check (safety_equipment_checks.result)
export const CHECK_RESULT_HE = { pass: 'תקין', conditional: 'מותנה', fail: 'נכשל' };

// computed state of a check TRACK (check_status[].state)
export const CHECK_STATE_HE = { valid: 'בתוקף', expired: 'פג תוקף', missing: 'לא בוצע' };
