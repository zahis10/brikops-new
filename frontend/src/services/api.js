import axios from 'axios';

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');
const API = `${BACKEND_URL}/api`;
console.log('[API_BASE_URL]', BACKEND_URL || '(relative)');

export { BACKEND_URL };

let _paywallCallback = null;
export const setPaywallCallback = (cb) => { _paywallCallback = cb; };

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 402) {
      const data = error.response.data;
      if (data?.code === 'PAYWALL' && _paywallCallback) {
        _paywallCallback();
      }
    }
    return Promise.reject(error);
  }
);

const getAuthHeader = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const projectService = {
  async list() {
    const response = await axios.get(`${API}/projects`, { headers: getAuthHeader() });
    return response.data;
  },
  async get(id) {
    const response = await axios.get(`${API}/projects/${id}`, { headers: getAuthHeader() });
    return response.data;
  },
  async create(data) {
    const response = await axios.post(`${API}/projects`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async getBuildings(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/buildings`, { headers: getAuthHeader() });
    return response.data;
  },
  async createBuilding(projectId, data) {
    const response = await axios.post(`${API}/projects/${projectId}/buildings`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async getHierarchy(projectId, { signal } = {}) {
    const response = await axios.get(`${API}/projects/${projectId}/hierarchy`, { headers: getAuthHeader(), signal });
    return response.data;
  },
  async assignPm(projectId, userId) {
    const response = await axios.post(`${API}/projects/${projectId}/assign-pm`, { user_id: userId }, { headers: getAuthHeader() });
    return response.data;
  },
  async getMemberships(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/memberships`, { headers: getAuthHeader() });
    return response.data;
  },
  async getAvailablePms(projectId, search = '') {
    const params = search ? { search } : {};
    const response = await axios.get(`${API}/projects/${projectId}/available-pms`, { headers: getAuthHeader(), params });
    return response.data;
  },
  async changeMemberRole(projectId, userId, newRole) {
    const response = await axios.put(`${API}/projects/${projectId}/members/${userId}/role`, { new_role: newRole }, { headers: getAuthHeader() });
    return response.data;
  },
  async removeMember(projectId, userId) {
    const response = await axios.delete(`${API}/projects/${projectId}/members/${userId}`, { headers: getAuthHeader() });
    return response.data;
  },
  async removeOrgMember(userId) {
    const response = await axios.delete(`${API}/org/members/${userId}`, { headers: getAuthHeader() });
    return response.data;
  },
  async getDashboard(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/dashboard`, { headers: getAuthHeader() });
    return response.data;
  },
  async updateContractorProfile(projectId, userId, body) {
    const response = await axios.put(`${API}/projects/${projectId}/members/${userId}/contractor-profile`, body, { headers: getAuthHeader() });
    return response.data;
  },
};

export const buildingService = {
  async getFloors(buildingId) {
    const response = await axios.get(`${API}/buildings/${buildingId}/floors`, { headers: getAuthHeader() });
    return response.data;
  },
  async createFloor(buildingId, data) {
    const response = await axios.post(`${API}/buildings/${buildingId}/floors`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async bulkCreateFloors(data) {
    const response = await axios.post(`${API}/floors/bulk`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async defectsSummary(buildingId) {
    const response = await axios.get(`${API}/buildings/${buildingId}/defects-summary`, { headers: getAuthHeader() });
    return response.data;
  },
};

export const floorService = {
  async getUnits(floorId) {
    const response = await axios.get(`${API}/floors/${floorId}/units`, { headers: getAuthHeader() });
    return response.data;
  },
  async createUnit(floorId, data) {
    const response = await axios.post(`${API}/floors/${floorId}/units`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async bulkCreateUnits(data) {
    const response = await axios.post(`${API}/units/bulk`, data, { headers: getAuthHeader() });
    return response.data;
  },
};

export const unitService = {
  async get(unitId) {
    const response = await axios.get(`${API}/units/${unitId}`, { headers: getAuthHeader() });
    return response.data;
  },
  async getTasks(unitId, params = {}) {
    const response = await axios.get(`${API}/units/${unitId}/tasks`, { headers: getAuthHeader(), params });
    return response.data;
  },
};

export const archiveService = {
  async archiveBuilding(buildingId, reason) {
    const response = await axios.post(`${API}/buildings/${buildingId}/archive`, { reason }, { headers: getAuthHeader() });
    return response.data;
  },
  async archiveFloor(floorId, reason) {
    const response = await axios.post(`${API}/floors/${floorId}/archive`, { reason }, { headers: getAuthHeader() });
    return response.data;
  },
  async archiveUnit(unitId, reason) {
    const response = await axios.post(`${API}/units/${unitId}/archive`, { reason }, { headers: getAuthHeader() });
    return response.data;
  },
  async restoreBuilding(buildingId) {
    const response = await axios.post(`${API}/buildings/${buildingId}/restore`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async restoreFloor(floorId) {
    const response = await axios.post(`${API}/floors/${floorId}/restore`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async restoreUnit(unitId) {
    const response = await axios.post(`${API}/units/${unitId}/restore`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async undoBatch(batchId) {
    const response = await axios.post(`${API}/batches/${batchId}/undo`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async getArchived(projectId, entityType, search) {
    const params = {};
    if (entityType) params.entity_type = entityType;
    if (search) params.search = search;
    const response = await axios.get(`${API}/projects/${projectId}/archived`, { headers: getAuthHeader(), params });
    return response.data;
  },
  async hardDelete(entityType, entityId, typedConfirmation) {
    const response = await axios.delete(`${API}/admin/entities/${entityType}/${entityId}/permanent`, {
      headers: getAuthHeader(),
      data: { typed_confirmation: typedConfirmation },
    });
    return response.data;
  },
};

export const companyService = {
  async list() {
    const response = await axios.get(`${API}/companies`, { headers: getAuthHeader() });
    return response.data;
  },
  async create(data) {
    const response = await axios.post(`${API}/companies`, data, { headers: getAuthHeader() });
    return response.data;
  },
};

export const projectCompanyService = {
  async list(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/companies`, { headers: getAuthHeader() });
    return response.data;
  },
  async create(projectId, data) {
    const response = await axios.post(`${API}/projects/${projectId}/companies`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async update(projectId, companyId, data) {
    const response = await axios.put(`${API}/projects/${projectId}/companies/${companyId}`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async remove(projectId, companyId) {
    const response = await axios.delete(`${API}/projects/${projectId}/companies/${companyId}`, { headers: getAuthHeader() });
    return response.data;
  },
};

export const inviteService = {
  async list(projectId, status = null) {
    const params = status ? { status } : {};
    const response = await axios.get(`${API}/projects/${projectId}/invites`, { headers: getAuthHeader(), params });
    return response.data;
  },
  async create(projectId, data) {
    const response = await axios.post(`${API}/projects/${projectId}/invites`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async resend(projectId, inviteId) {
    const response = await axios.post(`${API}/projects/${projectId}/invites/${inviteId}/resend`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async cancel(projectId, inviteId) {
    const response = await axios.post(`${API}/projects/${projectId}/invites/${inviteId}/cancel`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async resendSms(projectId, inviteId) {
    const response = await axios.post(`${API}/projects/${projectId}/invites/${inviteId}/resend-sms`, {}, { headers: getAuthHeader() });
    return response.data;
  },
};

export const teamInviteService = inviteService;

export const tradeService = {
  async list() {
    const response = await axios.get(`${API}/trades`, { headers: getAuthHeader() });
    return response.data;
  },
  async listForProject(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/trades`, { headers: getAuthHeader() });
    return response.data;
  },
  async createForProject(projectId, data) {
    const response = await axios.post(`${API}/projects/${projectId}/trades`, data, { headers: getAuthHeader() });
    return response.data;
  },
};

export const projectStatsService = {
  async get(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/stats`, { headers: getAuthHeader() });
    return response.data;
  },
};

export const excelService = {
  async downloadTemplate(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/excel-template`, {
      headers: getAuthHeader(),
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `template_${projectId}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
  async importFile(projectId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(`${API}/projects/${projectId}/excel-import`, formData, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
};

export const userService = {
  async list(params = {}) {
    const response = await axios.get(`${API}/users`, { headers: getAuthHeader(), params });
    return response.data;
  },
};

export const taskService = {
  async list(params = {}) {
    const response = await axios.get(`${API}/tasks`, { headers: getAuthHeader(), params });
    return response.data;
  },
  async contractorSummary(projectId, status = null) {
    const params = status ? { status } : {};
    const response = await axios.get(`${API}/projects/${projectId}/tasks/contractor-summary`, { headers: getAuthHeader(), params });
    return response.data;
  },
  async taskBuckets(projectId, status = null) {
    const params = status ? { status } : {};
    const response = await axios.get(`${API}/projects/${projectId}/task-buckets`, { headers: getAuthHeader(), params });
    return response.data;
  },
  async get(id) {
    const response = await axios.get(`${API}/tasks/${id}`, { headers: getAuthHeader() });
    return response.data;
  },
  async create(data) {
    const response = await axios.post(`${API}/tasks`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async update(id, data) {
    const response = await axios.patch(`${API}/tasks/${id}`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async assign(id, data) {
    const response = await axios.patch(`${API}/tasks/${id}/assign`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async changeStatus(id, status, note = '') {
    const response = await axios.post(`${API}/tasks/${id}/status`, { status, note }, { headers: getAuthHeader() });
    return response.data;
  },
  async reopen(id) {
    const response = await axios.post(`${API}/tasks/${id}/reopen`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async getUpdates(id) {
    const response = await axios.get(`${API}/tasks/${id}/updates`, { headers: getAuthHeader() });
    return response.data;
  },
  async addUpdate(id, content) {
    const response = await axios.post(`${API}/tasks/${id}/updates`, { task_id: id, content }, { headers: getAuthHeader() });
    return response.data;
  },
  async uploadAttachment(id, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(`${API}/tasks/${id}/attachments`, formData, {
      headers: getAuthHeader(),
      timeout: 90000,
    });
    return response.data;
  },
  async submitContractorProof(id, filesOrFile, note = '') {
    const formData = new FormData();
    if (Array.isArray(filesOrFile)) {
      filesOrFile.forEach(f => formData.append('files', f));
    } else {
      formData.append('file', filesOrFile);
    }
    if (note) formData.append('note', note);
    const response = await axios.post(`${API}/tasks/${id}/contractor-proof`, formData, {
      headers: getAuthHeader(),
      timeout: 120000,
    });
    return response.data;
  },
  async managerDecision(id, decision, reason = '') {
    const response = await axios.post(`${API}/tasks/${id}/manager-decision`, { decision, reason }, { headers: getAuthHeader() });
    return response.data;
  },
};

export const notificationService = {
  async sendWhatsApp(taskId, message = '') {
    const response = await axios.post(`${API}/tasks/${taskId}/notify`, { message }, { headers: getAuthHeader() });
    return response.data;
  },
  async getTimeline(taskId) {
    const response = await axios.get(`${API}/tasks/${taskId}/notifications`, { headers: getAuthHeader() });
    return response.data;
  },
  async retry(jobId) {
    const response = await axios.post(`${API}/notifications/${jobId}/retry`, {}, { headers: getAuthHeader() });
    return response.data;
  },
};

export const feedService = {
  async list(projectId = null, limit = 50) {
    const params = { limit };
    if (projectId) params.project_id = projectId;
    const response = await axios.get(`${API}/updates/feed`, { headers: getAuthHeader(), params });
    return response.data;
  },
};

export const membershipService = {
  async getMyMemberships() {
    const response = await axios.get(`${API}/my-memberships`, { headers: getAuthHeader() });
    return response.data;
  },
};

export const sortIndexService = {
  async migrate(projectId) {
    const response = await axios.post(`${API}/projects/${projectId}/migrate-sort-index`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async resequence(buildingId, dryRun = false) {
    const response = await axios.post(`${API}/buildings/${buildingId}/resequence`, { dry_run: dryRun }, { headers: getAuthHeader() });
    return response.data;
  },
  async insertFloor(projectId, data) {
    const response = await axios.post(`${API}/projects/${projectId}/insert-floor`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async resequenceUnits(buildingId, dryRun = false) {
    const response = await axios.post(`${API}/buildings/${buildingId}/resequence`, { dry_run: dryRun }, { headers: getAuthHeader() });
    return response.data;
  },
};

export const versionService = {
  async get() {
    const response = await axios.get(`${API}/debug/version`, { headers: getAuthHeader() });
    return response.data;
  },
};

export const configService = {
  async getFeatures() {
    const response = await axios.get(`${API}/config/features`);
    return response.data;
  },
};

export const onboardingService = {
  async requestOtp(phone_e164) {
    const response = await axios.post(`${API}/auth/request-otp`, { phone_e164 }, { timeout: 10000 });
    const data = response.data;
    console.log('[OTP-DEBUG] request-otp response:', { status: response.status, success: data?.success, otpStatus: data?.status, rid: data?.rid });
    if (response.status === 200 && data?.success === true) {
      return data;
    }
    if (data?.success === false) {
      const err = new Error(data?.message || data?.detail || 'שגיאה בשליחת קוד');
      err.otpError = true;
      err.response = response;
      throw err;
    }
    return data;
  },
  async verifyOtp(phone_e164, code) {
    const response = await axios.post(`${API}/auth/verify-otp`, { phone_e164, code });
    return response.data;
  },
  async registerWithPhone(data) {
    const response = await axios.post(`${API}/auth/register-with-phone`, data);
    return response.data;
  },
  async registerManagement(data) {
    const response = await axios.post(`${API}/auth/register-management`, data);
    return response.data;
  },
  async loginPhone(phone_e164, password) {
    const response = await axios.post(`${API}/auth/login-phone`, { phone_e164, password });
    return response.data;
  },
  async setPassword(password) {
    const response = await axios.post(`${API}/auth/set-password`, { password }, { headers: getAuthHeader() });
    return response.data;
  },
  async getJoinRequests(projectId, status = null) {
    const params = status ? { status } : {};
    const response = await axios.get(`${API}/projects/${projectId}/join-requests`, { headers: getAuthHeader(), params });
    return response.data;
  },
  async approveRequest(requestId, body = {}) {
    const response = await axios.post(`${API}/join-requests/${requestId}/approve`, body, { headers: getAuthHeader() });
    return response.data;
  },
  async rejectRequest(requestId, reason) {
    const response = await axios.post(`${API}/join-requests/${requestId}/reject`, { reason }, { headers: getAuthHeader() });
    return response.data;
  },
  async getManagementRoles() {
    const response = await axios.get(`${API}/auth/management-roles`);
    return response.data;
  },
  async getSubcontractorRoles() {
    const response = await axios.get(`${API}/auth/subcontractor-roles`);
    return response.data;
  },
  async getOnboardingStatus(phone) {
    const response = await axios.get(`${API}/onboarding/status`, { params: { phone } });
    return response.data;
  },
  async createOrg(data) {
    const response = await axios.post(`${API}/onboarding/create-org`, data);
    return response.data;
  },
  async getInviteInfo(inviteId) {
    const response = await axios.get(`${API}/invites/${inviteId}/info`, { headers: getAuthHeader() });
    return response.data;
  },
  async acceptInvite(data) {
    const response = await axios.post(`${API}/onboarding/accept-invite`, data);
    return response.data;
  },
  async joinByCode(data) {
    const response = await axios.post(`${API}/onboarding/join-by-code`, data);
    return response.data;
  },
};

export const unitPlanService = {
  async list(projectId, unitId, params = {}) {
    const response = await axios.get(`${API}/projects/${projectId}/units/${unitId}/plans`, {
      headers: getAuthHeader(),
      params,
    });
    return response.data;
  },
  async upload(projectId, unitId, file, discipline, note = '') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('discipline', discipline);
    if (note) formData.append('note', note);
    const response = await axios.post(`${API}/projects/${projectId}/units/${unitId}/plans`, formData, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
};

export const projectPlanService = {
  async list(projectId, params = {}) {
    const response = await axios.get(`${API}/projects/${projectId}/plans`, {
      headers: getAuthHeader(),
      params,
    });
    return response.data;
  },
  async listArchived(projectId, params = {}) {
    const response = await axios.get(`${API}/projects/${projectId}/plans/archive`, {
      headers: getAuthHeader(),
      params,
    });
    return response.data;
  },
  async upload(projectId, file, discipline, note = '') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('discipline', discipline);
    if (note) formData.append('note', note);
    const response = await axios.post(`${API}/projects/${projectId}/plans`, formData, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
  async replace(projectId, planId, file, note = '') {
    const formData = new FormData();
    formData.append('file', file);
    if (note) formData.append('note', note);
    const response = await axios.post(`${API}/projects/${projectId}/plans/${planId}/replace`, formData, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
  async archive(projectId, planId, note = '') {
    const response = await axios.patch(`${API}/projects/${projectId}/plans/${planId}/archive`, { note }, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
  async restore(projectId, planId) {
    const response = await axios.patch(`${API}/projects/${projectId}/plans/${planId}/restore`, {}, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
  async delete(projectId, planId, reason) {
    const response = await axios.delete(`${API}/projects/${projectId}/plans/${planId}`, {
      headers: getAuthHeader(),
      data: { reason },
    });
    return response.data;
  },
};

export const disciplineService = {
  async list(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/disciplines`, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
  async add(projectId, label) {
    const response = await axios.post(`${API}/projects/${projectId}/disciplines`, { label }, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
};

export const adminUserService = {
  async listUsers(q = '', skip = 0, limit = 50) {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    params.set('skip', skip);
    params.set('limit', limit);
    const response = await axios.get(`${API}/admin/users?${params}`, { headers: getAuthHeader() });
    return response.data;
  },
  async getUser(userId) {
    const response = await axios.get(`${API}/admin/users/${userId}`, { headers: getAuthHeader() });
    return response.data;
  },
  async changeUserPhone(userId, phone, note) {
    const response = await axios.put(`${API}/admin/users/${userId}/phone`, { phone, note }, { headers: getAuthHeader() });
    return response.data;
  },
  async changeUserRole(userId, projectId, newRole, note) {
    const response = await axios.put(
      `${API}/admin/users/${userId}/projects/${projectId}/role`,
      { new_role: newRole, note },
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async resetUserPassword(userId, newPassword, note) {
    const response = await axios.post(
      `${API}/admin/users/${userId}/reset-password`,
      { new_password: newPassword, note },
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async updatePreferredLanguage(userId, preferredLanguage) {
    const response = await axios.put(
      `${API}/admin/users/${userId}/preferred-language`,
      { preferred_language: preferredLanguage },
      { headers: getAuthHeader() }
    );
    return response.data;
  },
};

export const isStepupError = (err) => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'object' && detail?.code === 'stepup_required') return true;
  if (typeof detail === 'string' && detail.includes('Step-Up')) return true;
  return false;
};

export const stepupService = {
  async requestChallenge() {
    const response = await axios.post(`${API}/admin/stepup/request`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async verifyChallenge(challengeId, code) {
    const response = await axios.post(`${API}/admin/stepup/verify`, { challenge_id: challengeId, code }, { headers: getAuthHeader() });
    return response.data;
  },
};

export const phoneChangeService = {
  async requestOtp(phone) {
    const response = await axios.post(`${API}/auth/change-phone/request`, { phone }, { headers: getAuthHeader() });
    return response.data;
  },
  async verifyOtp(phone, code) {
    const response = await axios.post(`${API}/auth/change-phone/verify`, { phone, code }, { headers: getAuthHeader() });
    return response.data;
  },
};

export const billingService = {
  async me() {
    const response = await axios.get(`${API}/billing/me`, { headers: getAuthHeader() });
    return response.data;
  },
  async orgBilling(orgId) {
    const response = await axios.get(`${API}/billing/org/${orgId}`, { headers: getAuthHeader() });
    return response.data;
  },
  async projectBilling(projectId) {
    const response = await axios.get(`${API}/billing/project/${projectId}`, { headers: getAuthHeader() });
    return response.data;
  },
  async listOrgs() {
    const response = await axios.get(`${API}/admin/billing/orgs`, { headers: getAuthHeader() });
    return response.data;
  },
  async openPaymentRequestsSummary() {
    const response = await axios.get(`${API}/admin/billing/payment-requests-summary`, { headers: getAuthHeader() });
    return response.data;
  },
  async override(data) {
    const response = await axios.post(`${API}/admin/billing/override`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async auditLog() {
    const response = await axios.get(`${API}/admin/billing/audit`, { headers: getAuthHeader() });
    return response.data;
  },
  async plans() {
    const response = await axios.get(`${API}/admin/billing/plans`, { headers: getAuthHeader() });
    return response.data;
  },
  async activePlans() {
    const response = await axios.get(`${API}/billing/plans/active`, { headers: getAuthHeader() });
    return response.data;
  },
  async createPlan(data) {
    const response = await axios.post(`${API}/admin/billing/plans`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async updatePlan(planId, data) {
    const response = await axios.put(`${API}/admin/billing/plans/${planId}`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async deactivatePlan(planId) {
    const response = await axios.patch(`${API}/admin/billing/plans/${planId}/deactivate`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async migrationDryRun() {
    const response = await axios.get(`${API}/admin/billing/migration/dry-run`, { headers: getAuthHeader() });
    return response.data;
  },
  async migrationApply() {
    const response = await axios.post(`${API}/admin/billing/migration/apply`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async updateProjectBilling(projectId, data) {
    const response = await axios.patch(`${API}/billing/project/${projectId}`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async listActivePlans() {
    const response = await axios.get(`${API}/billing/plans/active`, { headers: getAuthHeader() });
    return response.data;
  },
  async handoffRequest(projectId, note) {
    const response = await axios.post(`${API}/billing/project/${projectId}/handoff-request`, { note }, { headers: getAuthHeader() });
    return response.data;
  },
  async handoffAck(projectId) {
    const response = await axios.post(`${API}/billing/project/${projectId}/handoff-ack`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async setupComplete(projectId) {
    const response = await axios.post(`${API}/billing/project/${projectId}/setup-complete`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async checkout(orgId) {
    const response = await axios.post(`${API}/billing/org/${orgId}/checkout`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async previewRenewal(orgId, cycle) {
    const response = await axios.get(`${API}/billing/preview-renewal`, { params: { scope: 'org', id: orgId, cycle }, headers: getAuthHeader() });
    return response.data;
  },
  async createPaymentRequest(orgId, cycle, note = '', contactEmail = '') {
    const response = await axios.post(`${API}/billing/org/${orgId}/payment-request`, { cycle, note, contact_email: contactEmail }, { headers: getAuthHeader() });
    return response.data;
  },
  async markPaid(orgId, { requestId, cycle, paidNote } = {}) {
    const response = await axios.post(`${API}/billing/org/${orgId}/mark-paid`, { request_id: requestId, cycle, paid_note: paidNote }, { headers: getAuthHeader() });
    return response.data;
  },
  async listPaymentRequests(orgId, status = '') {
    const params = status ? { status } : {};
    const response = await axios.get(`${API}/billing/org/${orgId}/payment-requests`, { params, headers: getAuthHeader() });
    return response.data;
  },
  async getPaymentConfig(orgId) {
    const response = await axios.get(`${API}/billing/org/${orgId}/payment-config`, { headers: getAuthHeader() });
    return response.data;
  },
  async updatePaymentConfig(orgId, data) {
    const response = await axios.put(`${API}/billing/org/${orgId}/payment-config`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async cancelPaymentRequest(orgId, requestId) {
    const response = await axios.post(`${API}/billing/org/${orgId}/payment-requests/${requestId}/cancel`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async customerMarkPaid(orgId, requestId, customerPaidNote = '') {
    const response = await axios.post(`${API}/billing/org/${orgId}/payment-requests/${requestId}/mark-paid-by-customer`, { customer_paid_note: customerPaidNote }, { headers: getAuthHeader() });
    return response.data;
  },
  async uploadReceipt(orgId, requestId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(`${API}/billing/org/${orgId}/payment-requests/${requestId}/receipt`, formData, { headers: getAuthHeader() });
    return response.data;
  },
  async getReceiptUrl(orgId, requestId) {
    const response = await axios.get(`${API}/billing/org/${orgId}/payment-requests/${requestId}/receipt`, { headers: getAuthHeader() });
    return response.data;
  },
  async rejectPaymentRequest(orgId, requestId, rejectionReason = '') {
    const response = await axios.post(`${API}/billing/org/${orgId}/payment-requests/${requestId}/reject`, { rejection_reason: rejectionReason }, { headers: getAuthHeader() });
    return response.data;
  },
};

export const invoiceService = {
  async preview(orgId, period) {
    const response = await axios.get(`${API}/billing/org/${orgId}/invoice/preview`, { params: { period }, headers: getAuthHeader() });
    return response.data;
  },
  async generate(orgId, period) {
    const response = await axios.post(`${API}/billing/org/${orgId}/invoice/generate?period=${encodeURIComponent(period)}`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async list(orgId) {
    const response = await axios.get(`${API}/billing/org/${orgId}/invoices`, { headers: getAuthHeader() });
    return response.data;
  },
  async get(orgId, invoiceId) {
    const response = await axios.get(`${API}/billing/org/${orgId}/invoices/${invoiceId}`, { headers: getAuthHeader() });
    return response.data;
  },
  async markPaid(orgId, invoiceId) {
    const response = await axios.post(`${API}/billing/org/${orgId}/invoices/${invoiceId}/mark-paid`, {}, { headers: getAuthHeader() });
    return response.data;
  },
};

export const orgMemberService = {
  async listMembers(orgId) {
    const response = await axios.get(`${API}/orgs/${orgId}/members`, { headers: getAuthHeader() });
    return response.data;
  },
  async changeRole(orgId, userId, role) {
    const response = await axios.put(`${API}/orgs/${orgId}/members/${userId}/org-role`, { role }, { headers: getAuthHeader() });
    return response.data;
  },
};

export const transferService = {
  async initiate(targetPhone) {
    const response = await axios.post(`${API}/org/transfer/initiate`, 
      { target_phone: targetPhone }, 
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async cancel(requestId) {
    const response = await axios.post(`${API}/org/transfer/cancel`, 
      { request_id: requestId }, 
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async getPending() {
    const response = await axios.get(`${API}/org/transfer/pending`, 
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async verifyToken(token) {
    const response = await axios.get(`${API}/org/transfer/verify/${token}`);
    return response.data;
  },
  async requestOtp(token) {
    const response = await axios.post(`${API}/org/transfer/request-otp`, { token });
    return response.data;
  },
  async accept(token, otpCode, typedOrgName) {
    const response = await axios.post(`${API}/org/transfer/accept`, {
      token, otp_code: otpCode, typed_org_name: typedOrgName,
    });
    return response.data;
  },
};

export const qcService = {
  async getFloorRun(floorId) {
    const response = await axios.get(`${API}/qc/floors/${floorId}/run`, { headers: getAuthHeader() });
    return response.data;
  },
  async getRun(runId) {
    const response = await axios.get(`${API}/qc/run/${runId}`, { headers: getAuthHeader() });
    return response.data;
  },
  async updateItem(runId, itemId, data) {
    const response = await axios.patch(`${API}/qc/run/${runId}/item/${itemId}`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async uploadPhoto(runId, itemId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(`${API}/qc/run/${runId}/item/${itemId}/photo`, formData, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
  async submitStage(runId, stageId) {
    const response = await axios.post(`${API}/qc/run/${runId}/stage/${stageId}/submit`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async getFloorsBatchStatus(floorIds, { projectId, signal } = {}) {
    let url = `${API}/qc/floors/batch-status?floor_ids=${floorIds.join(',')}`;
    if (projectId) url += `&project_id=${projectId}`;
    const response = await axios.get(url, { headers: getAuthHeader(), signal });
    return response.data;
  },
  async getStagesMeta() {
    const response = await axios.get(`${API}/qc/meta/stages`, { headers: getAuthHeader() });
    return response.data;
  },
  async getApprovers(projectId) {
    const response = await axios.get(`${API}/qc/projects/${projectId}/approvers`, { headers: getAuthHeader() });
    return response.data;
  },
  async addApprover(projectId, data) {
    const response = await axios.post(`${API}/qc/projects/${projectId}/approvers`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async removeApprover(projectId, userId) {
    const response = await axios.delete(`${API}/qc/projects/${projectId}/approvers/${userId}`, { headers: getAuthHeader() });
    return response.data;
  },
  async approveStage(runId, stageId, data = {}) {
    const response = await axios.post(`${API}/qc/run/${runId}/stage/${stageId}/approve`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async rejectStage(runId, stageId, data) {
    const response = await axios.post(`${API}/qc/run/${runId}/stage/${stageId}/reject`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async getMyApproverStatus(runId) {
    const response = await axios.get(`${API}/qc/run/${runId}/my-approver-status`, { headers: getAuthHeader() });
    return response.data;
  },
  async rejectItem(runId, itemId, data) {
    const response = await axios.post(`${API}/qc/run/${runId}/item/${itemId}/reject`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async reopenStage(runId, stageId, data) {
    const response = await axios.post(`${API}/qc/run/${runId}/stage/${stageId}/reopen`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async getStageTimeline(runId, stageId) {
    const response = await axios.get(`${API}/qc/run/${runId}/stage/${stageId}/timeline`, { headers: getAuthHeader() });
    return response.data;
  },
  async getTeamContacts(runId) {
    const response = await axios.get(`${API}/qc/run/${runId}/team-contacts`, { headers: getAuthHeader() });
    return response.data;
  },
  async notifyRejection(runId, stageId, data) {
    const response = await axios.post(`${API}/qc/run/${runId}/stage/${stageId}/notify-rejection`, data, { headers: getAuthHeader() });
    return response.data;
  },
};

export const identityService = {
  async getAccountStatus() {
    const response = await axios.get(`${API}/auth/account-status`, { headers: getAuthHeader() });
    return response.data;
  },
  async completeAccount(email, password) {
    const response = await axios.post(`${API}/auth/complete-account`, { email, password }, { headers: getAuthHeader() });
    return response.data;
  },
  logEvent(action, payload = {}) {
    axios.post(`${API}/auth/identity-event`, { action, payload }, { headers: getAuthHeader() }).catch(() => {});
  },
};

export const qcNotificationService = {
  async getNotifications(limit = 20, offset = 0) {
    const response = await axios.get(`${API}/qc-notifications?limit=${limit}&offset=${offset}`, { headers: getAuthHeader() });
    return response.data;
  },
  async getUnreadCount() {
    const response = await axios.get(`${API}/qc-notifications/unread-count`, { headers: getAuthHeader() });
    return response.data;
  },
  async markRead(notificationId) {
    const response = await axios.patch(`${API}/qc-notifications/${notificationId}/read`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async markAllRead() {
    const response = await axios.patch(`${API}/qc-notifications/read-all`, {}, { headers: getAuthHeader() });
    return response.data;
  },
};

export const authService = {
  async forgotPassword(email) {
    const response = await axios.post(`${API}/auth/forgot-password`, { email });
    return response.data;
  },
  async resetPassword(token, new_password) {
    const response = await axios.post(`${API}/auth/reset-password`, { token, new_password });
    return response.data;
  },
  async changePassword(current_password, new_password) {
    const response = await axios.post(`${API}/auth/change-password`, { current_password, new_password }, { headers: getAuthHeader() });
    return response.data;
  },
  async changeEmail(current_password, new_email) {
    const response = await axios.post(`${API}/auth/change-email`, { current_password, new_email }, { headers: getAuthHeader() });
    return response.data;
  },
};

export const exportService = {
  async exportDefects({ scope, unit_id, building_id, filters, format = 'excel' }) {
    const response = await axios.post(
      `${API}/defects/export`,
      { scope, unit_id, building_id, filters, format },
      { headers: getAuthHeader(), responseType: 'blob' }
    );
    const disposition = response.headers['content-disposition'] || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const ext = format === 'pdf' ? '.pdf' : '.xlsx';
    const filename = match ? match[1] : `defects_export_${new Date().toISOString().slice(0, 10)}${ext}`;
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
    return { success: true, filename };
  },
};
