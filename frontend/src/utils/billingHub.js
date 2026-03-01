export function getBillingHubUrl({ orgId, projectId }) {
  if (!orgId) return '/';
  const base = `/billing/org/${orgId}`;
  const query = projectId ? `?project_id=${projectId}` : '';
  return `${base}${query}#billing`;
}
