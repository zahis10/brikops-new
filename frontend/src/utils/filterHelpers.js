export const arraysEqualAsSets = (a, b) => {
  if (!Array.isArray(a) || !Array.isArray(b)) return false;
  if (a.length !== b.length) return false;
  const set = new Set(a);
  return b.every(v => set.has(v));
};
