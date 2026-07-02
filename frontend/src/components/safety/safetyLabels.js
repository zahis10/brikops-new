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

// Safety task status (schemas.py SafetyTaskStatus / safety_pdf.py TASK_STATUS_HE).
export const TASK_STATUS_HE = { open: 'פתוח', in_progress: 'בביצוע', completed: 'הושלם', cancelled: 'בוטל' };

// Safety incident type (schemas.py SafetyIncidentType / safety_pdf.py).
export const INCIDENT_TYPE_HE = { near_miss: 'כמעט-תאונה', injury: 'פציעה', property_damage: 'נזק לרכוש' };

// Safety incident status (display-only; server owns transitions).
export const INCIDENT_STATUS_HE = { draft: 'טיוטה', reported: 'דווח', closed: 'סגור' };
