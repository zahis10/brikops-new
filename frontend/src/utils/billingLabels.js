import { getPlanCatalog, getLegacyPlanLabel } from './billingPlanCatalog';

const BILLING_STATUS_LABELS = {
  trial: 'ניסיון',
  trialing: 'ניסיון',
  active: 'פעיל',
  past_due: 'חוב פתוח',
  expired: 'פג תוקף',
  suspended: 'מושעה',
  canceled: 'בוטל',
  paused: 'מושהה',
  archived: 'בארכיון',
};

const ACCESS_LABELS = {
  full_access: 'גישה מלאה',
  FULL_ACCESS: 'גישה מלאה',
  read_only: 'קריאה בלבד',
  READ_ONLY: 'קריאה בלבד',
};

const SETUP_STATE_LABELS = {
  trial: 'ניסיון',
  pending_handoff: 'ממתין להעברה',
  pending_billing_setup: 'ממתין להגדרת חיוב',
  ready: 'מוכן',
  active: 'פעיל',
};

const SETUP_STATE_COLORS = {
  trial: 'bg-blue-100 text-blue-700',
  pending_handoff: 'bg-amber-100 text-amber-700',
  pending_billing_setup: 'bg-orange-100 text-orange-700',
  ready: 'bg-emerald-100 text-emerald-700',
  active: 'bg-green-100 text-green-700',
};

const TIER_LABELS = {
  tier_s: 'עד 50 יחידות',
  tier_m: '51-200 יחידות',
  tier_l: '201-500 יחידות',
  tier_xl: '501+ יחידות',
  none: '—',
};

const BILLING_STATUS_COLORS = {
  trial: 'bg-blue-100 text-blue-700',
  trialing: 'bg-blue-100 text-blue-700',
  active: 'bg-green-100 text-green-700',
  past_due: 'bg-red-100 text-red-700',
  expired: 'bg-red-100 text-red-700',
  suspended: 'bg-red-100 text-red-700',
  canceled: 'bg-slate-100 text-slate-600',
  paused: 'bg-amber-100 text-amber-700',
  archived: 'bg-slate-100 text-slate-500',
};

export function getBillingStatusLabel(status) {
  return BILLING_STATUS_LABELS[status] || '—';
}

export function getBillingStatusColor(status) {
  return BILLING_STATUS_COLORS[status] || 'bg-slate-100 text-slate-600';
}

export function getAccessLabel(access) {
  return ACCESS_LABELS[access] || '—';
}

export function getSetupStateLabel(state) {
  return SETUP_STATE_LABELS[state] || '—';
}

export function getSetupStateColor(state) {
  return SETUP_STATE_COLORS[state] || 'bg-slate-100 text-slate-600';
}

export function getTierLabel(tier) {
  return TIER_LABELS[tier] || '—';
}

export function getPlanLabel(planId) {
  const catalog = getPlanCatalog(planId);
  if (catalog) return catalog.label;
  const legacy = getLegacyPlanLabel(planId);
  if (legacy) return legacy;
  return planId || '—';
}

export function formatCurrency(amount) {
  if (amount == null || isNaN(amount)) return '—';
  return `₪${Number(amount).toLocaleString('he-IL')}`;
}

const INVOICE_STATUS_LABELS = {
  draft: 'טיוטה',
  issued: 'הונפק',
  paid: 'שולם',
  past_due: 'באיחור',
  void: 'מבוטל',
};

const INVOICE_STATUS_COLORS = {
  draft: 'bg-slate-100 text-slate-600',
  issued: 'bg-blue-100 text-blue-700',
  paid: 'bg-green-100 text-green-700',
  past_due: 'bg-red-100 text-red-700',
  void: 'bg-slate-100 text-slate-500',
};

export function getInvoiceStatusLabel(status) {
  return INVOICE_STATUS_LABELS[status] || '—';
}

export function getInvoiceStatusColor(status) {
  return INVOICE_STATUS_COLORS[status] || 'bg-slate-100 text-slate-600';
}

export function getObservedUnitsWarning(observed, contracted) {
  if (observed != null && contracted != null && observed > contracted) {
    return 'זוהתה חריגה בין מספר היחידות בפועל למספר היחידות החוזיות. החיוב נקבע לפי מספר היחידות החוזיות.';
  }
  return null;
}
