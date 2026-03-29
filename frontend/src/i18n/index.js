import he from './he.json';
import en from './en.json';
import ar from './ar.json';
import zh from './zh.json';

const LOCALES = { he, en, ar, zh };
let currentLocale = 'he';

export function setLanguage(lang) {
  const base = (lang || '').split('-')[0].split('_')[0].toLowerCase();
  currentLocale = LOCALES[base] ? base : 'he';
  document.documentElement.lang = currentLocale;
}

export function getLanguage() {
  return currentLocale;
}

export function t(section, key) {
  const val = LOCALES[currentLocale]?.[section]?.[key]
    ?? LOCALES['he']?.[section]?.[key]
    ?? key;
  if (process.env.NODE_ENV === 'development'
      && !LOCALES[currentLocale]?.[section]?.[key]) {
    const fallback = LOCALES['he']?.[section]?.[key] ? ' (falling back to he)' : ' (no fallback)';
    console.warn(`[i18n] Missing ${currentLocale} key: ${section}.${key}${fallback}`);
  }
  return val;
}

export function tTrade(key) {
  return t('trades', key);
}

export function tCategory(key) {
  return t('categories', key);
}

export function tStatus(key) {
  return t('statuses', key);
}

export function tPriority(key) {
  return t('priorities', key);
}

export function tRole(key) {
  return t('roles', key);
}

export function tSubRole(key) {
  return t('subRoles', key);
}

export function getLocale() {
  return currentLocale;
}
