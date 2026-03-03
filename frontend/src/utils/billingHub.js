export function buildOrgBillingUrl({ orgId, focus } = {}) {
  if (!orgId) return null;
  const base = `/billing/org/${orgId}`;
  if (focus) {
    return `${base}?focus=${focus}#${focus}`;
  }
  return base;
}

export function getBillingHubUrl({ orgId, projectId } = {}) {
  if (!orgId) return null;
  const base = `/billing/org/${orgId}`;
  const query = projectId ? `?project_id=${projectId}` : '';
  return `${base}${query}#billing`;
}
