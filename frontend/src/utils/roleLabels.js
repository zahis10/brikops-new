const ROLE_LABELS_HE = {
  owner: 'בעלים',
  admin: 'מנהל',
  project_manager: 'מנהל פרויקט',
  management_team: 'צוות ניהול',
  contractor: 'קבלן',
  super_admin: 'מנהל מערכת',
  viewer: 'צפייה בלבד',
};

export function getRoleLabel(role) {
  if (!role) return 'משתמש';
  return ROLE_LABELS_HE[role] || 'משתמש';
}

export const CONTRACTOR_ROLE = 'contractor';

export const SUB_ROLE_LABELS = {
  site_manager: 'מנהל אתר',
  execution_engineer: 'מהנדס ביצוע',
  safety_assistant: 'עוזר בטיחות',
  work_manager: 'מנהל עבודה',
  safety_officer: 'ממונה בטיחות',
};

export const subRoleLabel = (code) => SUB_ROLE_LABELS[code] || '';
