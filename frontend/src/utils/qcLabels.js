const QC_FLOOR_STATUS_LABELS = {
  not_started: 'לא התחיל',
  in_progress: 'בביצוע',
  pending_review: 'ממתין לאישור',
  submitted: 'ממתין לאישור',
  approved: 'אושר',
  rejected: 'נדחה',
};

const QC_STAGE_STATUS_LABELS = {
  draft: 'בביצוע',
  ready: 'מוכן',
  pending_review: 'ממתין לאישור',
  approved: 'אושר',
  rejected: 'נדחה',
  reopened: 'נפתח מחדש',
};

export function qcFloorStatusLabel(status) {
  return QC_FLOOR_STATUS_LABELS[status] || 'לא התחיל';
}

export function qcStageStatusLabel(status) {
  return QC_STAGE_STATUS_LABELS[status] || 'בביצוע';
}
