const PLAN_CATALOG = {
  plan_basic: {
    id: 'plan_basic',
    label: 'בסיסי',
    shortDescription: 'פתרון מסודר לפרויקט בתחילת עבודה שוטפת',
    bestFor: 'מתאים לפרויקטים קטנים/בינוניים בתחילת תהליך',
    badge: null,
    highlights: [
      'ניהול חיוב פרויקט לפי חבילה + מדרגת יחידות',
      'תצוגת עלות חודשית ברורה לפרויקט',
      'מעקב יחידות חוזיות מול יחידות בפועל',
      'מתאים להתחלה מסודרת של תהליך עבודה',
    ],
  },
  plan_pro: {
    id: 'plan_pro',
    label: 'מקצועי',
    shortDescription: 'האיזון המומלץ לרוב הפרויקטים הפעילים',
    bestFor: 'מתאים לרוב הפרויקטים הפעילים עם צוות וניהול שוטף',
    badge: 'מומלץ',
    highlights: [
      'כל מה שבבסיסי',
      'מתאים לניהול שוטף בהיקף עבודה גבוה יותר',
      'נראות טובה יותר לעלות ולתכנון חיוב ארגוני',
      'בחירה מומלצת לרוב הלקוחות',
    ],
  },
  plan_xl: {
    id: 'plan_xl',
    label: 'XL',
    shortDescription: 'מיועד לפרויקטים גדולים והיקפי עבודה משמעותיים',
    bestFor: 'מתאים לארגונים/פרויקטים גדולים או מורכבים',
    badge: 'להיקף גדול',
    highlights: [
      'כל מה שבמקצועי',
      'מותאם לסדרי גודל גדולים',
      'מתאים לעבודה ארגונית בפרויקטים עם נפח גבוה',
      'בחירה מתאימה להיקפים גדולים במיוחד',
    ],
  },
};

const PLAN_ORDER = ['plan_basic', 'plan_pro', 'plan_xl'];

export function getPlanCatalog(planId) {
  return PLAN_CATALOG[planId] || null;
}

export function getAllPlanCatalog() {
  return PLAN_ORDER.map(id => PLAN_CATALOG[id]);
}

export function getPlanBadge(planId) {
  return PLAN_CATALOG[planId]?.badge || null;
}
