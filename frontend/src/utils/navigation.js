const MANAGEMENT_ROLES = ['owner', 'admin', 'project_manager', 'management_team'];

export function navigateToProject(project, navigate) {
  const id = project.id || project._id;
  const role = project.my_role;
  localStorage.setItem('lastProjectId', id);

  if (MANAGEMENT_ROLES.includes(role)) {
    navigate(`/projects/${id}/control?workMode=structure`);
  } else if (role === 'contractor') {
    navigate('/projects');
  } else {
    navigate(`/projects/${id}/tasks`);
  }
}

export function getProjectBackPath(projectRole, projectId) {
  if (MANAGEMENT_ROLES.includes(projectRole)) {
    return `/projects/${projectId}/control`;
  }
  return '/projects';
}
