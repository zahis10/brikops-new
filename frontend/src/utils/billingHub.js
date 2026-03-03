export function getBillingHubUrl({ orgId, projectId }) {
  if (!orgId) return null;
  const base = `/billing/org/${orgId}`;
  const query = projectId ? `?project_id=${projectId}` : '';
  return `${base}${query}#billing`;
}
