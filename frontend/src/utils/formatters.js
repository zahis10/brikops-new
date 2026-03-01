export function formatUnitLabel(label) {
  if (!label && label !== 0) return '';
  const str = String(label);
  if (/^\d+$/.test(str)) return `דירה ${str}`;
  if (str.startsWith('דירה ')) return str;
  return str;
}
