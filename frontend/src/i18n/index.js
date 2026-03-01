import he from './he.json';
import en from './en.json';

const locales = { he, en };
const currentLocale = 'he';

export function t(section, key) {
  const dict = locales[currentLocale] || locales.he;
  const sectionData = dict[section];
  if (!sectionData) return key;
  return sectionData[key] || key;
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
