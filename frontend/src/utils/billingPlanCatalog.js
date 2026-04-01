const PLAN_CATALOG = {
  standard: {
    id: 'standard',
    label: 'רישיון פרויקט',
    shortDescription: 'רישיון + תמחור ליחידה',
    badge: null,
  },
  founder_6m: {
    id: 'founder_6m',
    label: 'מנוי מייסדים',
    shortDescription: '₪500/חודש — 6 חודשים',
    badge: 'מייסדים',
  },
};

const LEGACY_LABELS = {
  plan_basic: 'בסיסי (ארכיון)',
  plan_pro: 'מקצועי (ארכיון)',
  plan_xl: 'XL (ארכיון)',
};

export function getPlanCatalog(planId) {
  return PLAN_CATALOG[planId] || null;
}

export function getLegacyPlanLabel(planId) {
  return LEGACY_LABELS[planId] || null;
}

export function getAllPlanCatalog() {
  return [PLAN_CATALOG.standard];
}

export function getPlanBadge(planId) {
  return PLAN_CATALOG[planId]?.badge || null;
}
