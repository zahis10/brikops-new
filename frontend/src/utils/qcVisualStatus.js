export const getStageVisualStatus = (stage) => {
  if (!stage) return { barColor: 'bg-slate-200', pctColor: 'text-slate-400', borderColor: 'border-slate-200', badgeColor: 'bg-slate-100 text-slate-600', key: 'not_started' };
  const status = stage.computed_status;
  const hasFailedItems = (stage.fail_count || 0) > 0;
  const hasRejectedItems = stage.items?.some(i => !!i.reviewer_rejection);

  if (status === 'approved' && (hasFailedItems || hasRejectedItems)) {
    return { barColor: 'bg-amber-500', pctColor: 'text-amber-400', borderColor: 'border-amber-200', badgeColor: 'bg-amber-100 text-amber-700', key: 'inconsistent', label: 'מצב לא עקבי' };
  }
  if (status === 'rejected' || hasRejectedItems) {
    return { barColor: 'bg-red-500', pctColor: 'text-red-400', borderColor: 'border-red-200', badgeColor: 'bg-red-100 text-red-700', key: 'rejected' };
  }
  if (hasFailedItems) {
    return { barColor: 'bg-red-400', pctColor: 'text-red-300', borderColor: 'border-red-200', badgeColor: 'bg-red-100 text-red-700', key: 'failed' };
  }
  if (status === 'pending_review') {
    return { barColor: 'bg-blue-500', pctColor: 'text-blue-400', borderColor: 'border-blue-200', badgeColor: 'bg-blue-100 text-blue-700', key: 'pending_review' };
  }
  if (status === 'reopened') {
    return { barColor: 'bg-orange-500', pctColor: 'text-orange-400', borderColor: 'border-orange-200', badgeColor: 'bg-orange-100 text-orange-700', key: 'reopened' };
  }
  if (status === 'approved') {
    return { barColor: 'bg-emerald-500', pctColor: 'text-emerald-400', borderColor: 'border-emerald-200', badgeColor: 'bg-emerald-100 text-emerald-700', key: 'approved' };
  }
  const pct = stage.total > 0 ? Math.round((stage.done / stage.total) * 100) : 0;
  if (pct > 0) {
    return { barColor: 'bg-amber-500', pctColor: 'text-amber-400', borderColor: 'border-amber-200', badgeColor: 'bg-amber-100 text-amber-700', key: 'in_progress' };
  }
  return { barColor: 'bg-slate-200', pctColor: 'text-slate-400', borderColor: 'border-slate-200', badgeColor: 'bg-slate-100 text-slate-600', key: 'not_started' };
};

export const getStageVisualStatusLite = (stage) => {
  if (!stage) return { barColor: 'bg-slate-200', chipColor: 'bg-slate-100 text-slate-500', badgeColor: 'bg-slate-100 text-slate-600', key: 'not_started' };
  const status = stage.computed_status || 'draft';
  const hasFailedItems = (stage.fail_count || 0) > 0;
  const hasRejectedItems = stage.items?.some(i => !!i.reviewer_rejection) || false;

  if (status === 'approved' && (hasFailedItems || hasRejectedItems)) {
    return { barColor: 'bg-amber-500', chipColor: 'bg-amber-100 text-amber-700', badgeColor: 'bg-amber-100 text-amber-700', key: 'inconsistent', label: 'מצב לא עקבי' };
  }
  if (status === 'rejected' || hasRejectedItems || hasFailedItems) {
    return { barColor: 'bg-red-500', chipColor: 'bg-red-100 text-red-700', badgeColor: 'bg-red-100 text-red-700', key: 'rejected' };
  }
  if (status === 'pending_review') {
    return { barColor: 'bg-blue-500', chipColor: 'bg-blue-100 text-blue-700', badgeColor: 'bg-blue-100 text-blue-700', key: 'pending_review' };
  }
  if (status === 'reopened') {
    return { barColor: 'bg-orange-500', chipColor: 'bg-orange-100 text-orange-700', badgeColor: 'bg-orange-100 text-orange-700', key: 'reopened' };
  }
  if (status === 'approved') {
    return { barColor: 'bg-emerald-500', chipColor: 'bg-emerald-100 text-emerald-700', badgeColor: 'bg-emerald-100 text-emerald-700', key: 'approved' };
  }
  const pct = stage.total > 0 ? Math.round((stage.done / stage.total) * 100) : 0;
  if (pct > 0) {
    return { barColor: 'bg-amber-400', chipColor: 'bg-amber-100 text-amber-700', badgeColor: 'bg-amber-100 text-amber-700', key: 'in_progress' };
  }
  return { barColor: 'bg-slate-200', chipColor: 'bg-slate-100 text-slate-500', badgeColor: 'bg-slate-100 text-slate-600', key: 'not_started' };
};

export const getFloorVisualStatus = (stages) => {
  if (!stages || stages.length === 0) return { barColor: 'bg-slate-200', pctColor: 'text-slate-400', borderColor: 'border-slate-200', badgeColor: 'bg-slate-100 text-slate-600', key: 'not_started' };

  let anyRejected = false;
  let anyFailed = false;
  let anyPendingReview = false;
  let anyReopened = false;
  let allApproved = true;
  let anyProgress = false;

  for (const stage of stages) {
    const status = stage.computed_status || 'draft';
    const hasFail = (stage.fail_count || 0) > 0;

    if (status === 'rejected') anyRejected = true;
    if (hasFail) anyFailed = true;
    if (status === 'pending_review') anyPendingReview = true;
    if (status === 'reopened') anyReopened = true;
    if (status !== 'approved') allApproved = false;
    if (stage.done > 0 || status !== 'draft') anyProgress = true;
  }

  if (anyRejected || anyFailed) {
    return { barColor: 'bg-red-500', pctColor: 'text-red-400', borderColor: 'border-red-200', badgeColor: 'bg-red-100 text-red-700', key: 'rejected' };
  }
  if (anyPendingReview) {
    return { barColor: 'bg-blue-500', pctColor: 'text-blue-400', borderColor: 'border-blue-200', badgeColor: 'bg-blue-100 text-blue-700', key: 'pending_review' };
  }
  if (anyReopened) {
    return { barColor: 'bg-orange-500', pctColor: 'text-orange-400', borderColor: 'border-orange-200', badgeColor: 'bg-orange-100 text-orange-700', key: 'reopened' };
  }
  if (allApproved && anyProgress) {
    return { barColor: 'bg-emerald-500', pctColor: 'text-emerald-400', borderColor: 'border-emerald-200', badgeColor: 'bg-emerald-100 text-emerald-700', key: 'approved' };
  }
  if (anyProgress) {
    return { barColor: 'bg-amber-500', pctColor: 'text-amber-400', borderColor: 'border-amber-200', badgeColor: 'bg-amber-100 text-amber-700', key: 'in_progress' };
  }
  return { barColor: 'bg-slate-200', pctColor: 'text-slate-400', borderColor: 'border-slate-200', badgeColor: 'bg-slate-100 text-slate-600', key: 'not_started' };
};

export const getQualityBadge = (stage) => {
  if (!stage) return { label: 'ללא נתונים', color: 'bg-slate-100 text-slate-500', key: 'no_data' };
  const failCount = stage.fail_count || 0;
  const hasRejectedItems = stage.items?.some(i => !!i.reviewer_rejection) || false;
  const passCount = stage.pass_count || 0;
  const pendingCount = stage.pending_count || 0;
  const total = stage.total || 0;
  const doneCount = stage.done || 0;

  if (total === 0) return { label: 'ללא נתונים', color: 'bg-slate-100 text-slate-500', key: 'no_data' };
  if (failCount > 0 || hasRejectedItems) {
    return { label: 'נכשל', color: 'bg-red-100 text-red-700', key: 'failed' };
  }
  if (passCount === total) {
    return { label: 'תקין', color: 'bg-emerald-100 text-emerald-700', key: 'passed' };
  }
  if (doneCount > 0 || passCount > 0) {
    return { label: 'בביצוע', color: 'bg-amber-100 text-amber-700', key: 'mixed' };
  }
  return { label: 'טרם התחיל', color: 'bg-slate-100 text-slate-500', key: 'not_started' };
};

export const getReviewBadge = (stage) => {
  if (!stage) return null;
  const status = stage.computed_status;
  const hasFailedItems = (stage.fail_count || 0) > 0;
  const hasRejectedItems = stage.items?.some(i => !!i.reviewer_rejection) || false;
  if (status === 'approved' && (hasFailedItems || hasRejectedItems)) {
    return { label: 'מצב לא עקבי', color: 'bg-amber-100 text-amber-700', key: 'inconsistent' };
  }
  switch (status) {
    case 'approved': return { label: 'אושר ביקורת', color: 'bg-emerald-100 text-emerald-700', key: 'approved' };
    case 'rejected': return { label: 'נדחה', color: 'bg-red-100 text-red-700', key: 'rejected' };
    case 'pending_review': return { label: 'ממתין לאישור', color: 'bg-blue-100 text-blue-700', key: 'pending_review' };
    case 'reopened': return { label: 'נפתח מחדש', color: 'bg-orange-100 text-orange-700', key: 'reopened' };
    default: return null;
  }
};

export const getFloorQualityBadge = (stages) => {
  if (!stages || stages.length === 0) return { label: 'ללא נתונים', color: 'bg-slate-100 text-slate-500', key: 'no_data' };
  let totalFail = 0, totalPass = 0, totalItems = 0, totalDone = 0;
  for (const stage of stages) {
    totalFail += stage.fail_count || 0;
    totalPass += stage.pass_count || 0;
    totalItems += stage.total || 0;
    totalDone += stage.done || 0;
  }
  if (totalItems === 0) return { label: 'ללא נתונים', color: 'bg-slate-100 text-slate-500', key: 'no_data' };
  if (totalFail > 0) return { label: 'נכשל', color: 'bg-red-100 text-red-700', key: 'failed' };
  if (totalPass === totalItems) return { label: 'תקין', color: 'bg-emerald-100 text-emerald-700', key: 'passed' };
  if (totalDone > 0 || totalPass > 0) return { label: 'בביצוע', color: 'bg-amber-100 text-amber-700', key: 'mixed' };
  return { label: 'טרם התחיל', color: 'bg-slate-100 text-slate-500', key: 'not_started' };
};

export const getFloorBadgeVisualStatus = (badgeStatus) => {
  switch (badgeStatus) {
    case 'rejected':
      return { color: 'text-red-600', bg: 'bg-red-50', iconColor: 'text-red-500' };
    case 'reopened':
      return { color: 'text-orange-600', bg: 'bg-orange-50', iconColor: 'text-orange-500' };
    case 'inconsistent':
      return { color: 'text-amber-600', bg: 'bg-amber-50', iconColor: 'text-amber-500' };
    case 'approved':
      return { color: 'text-emerald-600', bg: 'bg-emerald-50', iconColor: 'text-emerald-500' };
    case 'pending_review':
    case 'submitted':
      return { color: 'text-blue-600', bg: 'bg-blue-50', iconColor: 'text-blue-500' };
    case 'in_progress':
      return { color: 'text-amber-600', bg: 'bg-amber-50', iconColor: 'text-amber-500' };
    default:
      return { color: 'text-slate-400', bg: 'bg-slate-50', iconColor: 'text-slate-400' };
  }
};
