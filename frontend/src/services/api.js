import axios from 'axios';
import { downloadBlob } from '../utils/fileDownload';

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');
const API = `${BACKEND_URL}/api`;

export { BACKEND_URL };

const _cache = new Map();
const _CACHE_TTL_MS = 30_000;

function cachedFetch(key, fetcher) {
  const entry = _cache.get(key);
  const now = Date.now();
  if (entry && (now - entry.ts) < _CACHE_TTL_MS) return entry.value;
  const promise = fetcher().catch(err => {
    setTimeout(() => _cache.delete(key), 5_000);
    throw err;
  });
  _cache.set(key, { value: promise, ts: now });
  return promise;
}

export function clearProjectCache(projectId) {
  if (!projectId) {
    _cache.clear();
    return;
  }
  for (const key of _cache.keys()) {
    if (key.includes(projectId)) _cache.delete(key);
  }
}

let _paywallCallback = null;
export const setPaywallCallback = (cb) => { _paywallCallback = cb; };

axios.interceptors.response.use(
  (response) => {
    const newToken = response.headers['x-new-token'];
    if (newToken) {
      localStorage.setItem('token', newToken);
      document.cookie = 'brikops_logged_in=1; domain=.brikops.com; path=/; max-age=2592000; SameSite=Lax; Secure';
    }
    return response;
  },
  (error) => {
    // NOTE: Do NOT add 401 handling here.
    // Auth errors are handled in AuthContext.fetchCurrentUser.
    // Adding token cleanup here would bypass the network
    // error resilience logic. See #171.
    if (error.response?.status === 402) {
      const data = error.response.data;
      if (data?.code === 'PAYWALL' && _paywallCallback) {
        _paywallCallback();
      }
    }
    if (error.response) {
      const requestId = error.response.headers?.['x-request-id'];
      if (requestId) {
        error.requestId = requestId;
        console.error(
          `[API Error] ${error.response.status} ${error.config?.method?.toUpperCase()} ${error.config?.url} request_id=${requestId}`
        );
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
    return cachedFetch(`project:get:${id}`, async () => {
      const response = await axios.get(`${API}/projects/${id}`, { headers: getAuthHeader() });
      return response.data;
    });
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
    clearProjectCache(projectId);
    return response.data;
  },
  async getHierarchy(projectId, { signal } = {}) {
    if (signal) {
      const response = await axios.get(`${API}/projects/${projectId}/hierarchy`, { headers: getAuthHeader(), signal });
      return response.data;
    }
    return cachedFetch(`project:hierarchy:${projectId}`, async () => {
      const response = await axios.get(`${API}/projects/${projectId}/hierarchy`, { headers: getAuthHeader() });
      return response.data;
    });
  },
  async assignPm(projectId, userId) {
    const response = await axios.post(`${API}/projects/${projectId}/assign-pm`, { user_id: userId }, { headers: getAuthHeader() });
    clearProjectCache(projectId);
    return response.data;
  },
  async getMemberships(projectId) {
    return cachedFetch(`project:memberships:${projectId}`, async () => {
      const response = await axios.get(`${API}/projects/${projectId}/memberships`, { headers: getAuthHeader() });
      return response.data;
    });
  },
  async getAvailablePms(projectId, search = '') {
    const params = search ? { search } : {};
    const response = await axios.get(`${API}/projects/${projectId}/available-pms`, { headers: getAuthHeader(), params });
    return response.data;
  },
  async changeMemberRole(projectId, userId, newRole) {
    const response = await axios.put(`${API}/projects/${projectId}/members/${userId}/role`, { new_role: newRole }, { headers: getAuthHeader() });
    clearProjectCache(projectId);
    return response.data;
  },
  async removeMember(projectId, userId) {
    const response = await axios.delete(`${API}/projects/${projectId}/members/${userId}`, { headers: getAuthHeader() });
    clearProjectCache(projectId);
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
  async getTeamActivity(projectId, period = 7) {
    const response = await axios.get(`${API}/projects/${projectId}/team-activity?period=${period}`, { headers: getAuthHeader() });
    return response.data;
  },
  async getActivityTrend(projectId, days = 30) {
    const response = await axios.get(`${API}/projects/${projectId}/activity-trend?days=${days}`, { headers: getAuthHeader() });
    return response.data;
  },
  async updateContractorProfile(projectId, userId, body) {
    const response = await axios.put(`${API}/projects/${projectId}/members/${userId}/contractor-profile`, body, { headers: getAuthHeader() });
    clearProjectCache(projectId);
    return response.data;
  },
  async markOnboardingComplete(projectId) {
    const response = await axios.put(`${API}/projects/${projectId}/onboarding-complete`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async sendContractorReminder(projectId, companyId) {
    const response = await axios.post(`${API}/projects/${projectId}/reminders/contractor/${companyId}`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async sendDigest(projectId) {
    const response = await axios.post(`${API}/projects/${projectId}/reminders/digest`, {}, { headers: getAuthHeader() });
    return response.data;
  },
};

export const safetyService = {
  async getScore(projectId, refresh = false) {
    const params = refresh ? { refresh: 'true' } : {};
    const response = await axios.get(
      `${API}/safety/${projectId}/score`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },

  async listDocuments(projectId, params = {}) {
    const response = await axios.get(
      `${API}/safety/${projectId}/documents`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },

  async listTasks(projectId, params = {}) {
    const response = await axios.get(
      `${API}/safety/${projectId}/tasks`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },

  async listWorkers(projectId, params = {}) {
    const response = await axios.get(
      `${API}/safety/${projectId}/workers`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },

  async listTrainings(projectId, params = {}) {
    const response = await axios.get(
      `${API}/safety/${projectId}/trainings`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },

  async listIncidents(projectId, params = {}) {
    const response = await axios.get(
      `${API}/safety/${projectId}/incidents`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },

  async healthz() {
    const response = await axios.get(`${API}/safety/healthz`, { headers: getAuthHeader() });
    return response.data;
  },

  // ---- exports (binary blob) + single-doc delete ----

  async exportExcel(projectId) {
    const response = await axios.get(
      `${API}/safety/${projectId}/export/excel`,
      { headers: getAuthHeader(), responseType: 'blob' }
    );
    return response;
  },

  async exportFiltered(projectId, params = {}) {
    const response = await axios.get(
      `${API}/safety/${projectId}/export/filtered`,
      { headers: getAuthHeader(), responseType: 'blob', params }
    );
    return response;
  },

  async exportPdfRegister(projectId) {
    const response = await axios.get(
      `${API}/safety/${projectId}/export/pdf-register`,
      { headers: getAuthHeader(), responseType: 'blob' }
    );
    return response;
  },

  async deleteDocument(projectId, documentId) {
    const response = await axios.delete(
      `${API}/safety/${projectId}/documents/${documentId}`,
      { headers: getAuthHeader() }
    );
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
  async patch(unitId, data) {
    const response = await axios.patch(`${API}/units/${unitId}`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async updateSpareTiles(unitId, spareTiles) {
    const response = await axios.patch(`${API}/units/${unitId}/spare-tiles`, { spare_tiles: spareTiles }, { headers: getAuthHeader() });
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

export const companySearchService = {
  async search(query) {
    const response = await axios.get(`${API}/companies/search`, { headers: getAuthHeader(), params: { q: query } });
    return response.data;
  },
};

export const projectCompanyService = {
  async list(projectId) {
    return cachedFetch(`project:companies:${projectId}`, async () => {
      const response = await axios.get(`${API}/projects/${projectId}/companies`, { headers: getAuthHeader() });
      return response.data;
    });
  },
  async create(projectId, data) {
    const response = await axios.post(`${API}/projects/${projectId}/companies`, data, { headers: getAuthHeader() });
    clearProjectCache(projectId);
    return response.data;
  },
  async update(projectId, companyId, data) {
    const response = await axios.put(`${API}/projects/${projectId}/companies/${companyId}`, data, { headers: getAuthHeader() });
    clearProjectCache(projectId);
    return response.data;
  },
  async remove(projectId, companyId) {
    const response = await axios.delete(`${API}/projects/${projectId}/companies/${companyId}`, { headers: getAuthHeader() });
    clearProjectCache(projectId);
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
    return cachedFetch(`project:trades:${projectId}`, async () => {
      const response = await axios.get(`${API}/projects/${projectId}/trades`, { headers: getAuthHeader() });
      return response.data;
    });
  },
  async createForProject(projectId, data) {
    const response = await axios.post(`${API}/projects/${projectId}/trades`, data, { headers: getAuthHeader() });
    clearProjectCache(projectId);
    return response.data;
  },
};

export const projectStatsService = {
  async get(projectId) {
    return cachedFetch(`project:stats:${projectId}`, async () => {
      const response = await axios.get(`${API}/projects/${projectId}/stats`, { headers: getAuthHeader() });
      return response.data;
    });
  },
};

export const excelService = {
  async downloadTemplate(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/excel-template`, {
      headers: getAuthHeader(),
      responseType: 'blob',
    });
    return downloadBlob(
      new Blob([response.data], { type: 'text/csv' }),
      `template_${projectId}.csv`,
      'text/csv'
    );
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
  async getReminderPreferences() {
    const response = await axios.get(`${API}/users/me/reminder-preferences`, { headers: getAuthHeader() });
    return response.data;
  },
  async updateReminderPreferences(prefs) {
    const response = await axios.put(`${API}/users/me/reminder-preferences`, prefs, { headers: getAuthHeader() });
    return response.data;
  },
};

export const taskService = {
  async list(params = {}) {
    const { signal, ...queryParams } = params;
    const config = { headers: getAuthHeader(), params: queryParams };
    if (signal) config.signal = signal;
    const response = await axios.get(`${API}/tasks`, config);
    const d = response.data;
    if (d && typeof d === 'object' && !Array.isArray(d)) return d;
    const items = Array.isArray(d) ? d : (Array.isArray(d?.items) ? d.items : []);
    return { items, total: items.length, limit: 50, offset: 0 };
  },
  async myStats(params = {}) {
    const response = await axios.get(`${API}/tasks/my-stats`, { headers: getAuthHeader(), params });
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
    const fileBytes = await file.arrayBuffer();
    const fileName = file.name || 'photo.jpg';
    const fileType = file.type || 'image/jpeg';
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const blob = new Blob([fileBytes], { type: fileType });
        const safeFile = new File([blob], fileName, { type: fileType });
        const formData = new FormData();
        formData.append('file', safeFile);
        const response = await axios.post(`${API}/tasks/${id}/attachments`, formData, {
          headers: getAuthHeader(),
          timeout: 90000,
        });
        return response.data;
      } catch (err) {
        const status = err.response?.status;
        const isServerError = !status || status >= 500;
        console.warn(`[uploadAttachment] attempt ${attempt}/3 failed: status=${status || 'network'} file=${fileName} size=${fileBytes.byteLength}`);
        if (attempt === 3 || !isServerError) throw err;
        await new Promise(r => setTimeout(r, attempt * 1000));
      }
    }
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
  async forceClose(id, reason, closeType = 'field_verified') {
    const response = await axios.post(`${API}/tasks/${id}/force-close`, { reason, close_type: closeType }, { headers: getAuthHeader() });
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
  async updatePreferredLanguage(projectId, userId, lang) {
    const response = await axios.put(
      `${API}/projects/${projectId}/members/${userId}/preferred-language`,
      { preferred_language: lang },
      { headers: getAuthHeader() }
    );
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
    // #395 — pass platform so backend can pick Android SMS Retriever format on Android builds
    let platform;
    try { platform = (await import('@capacitor/core')).Capacitor.getPlatform(); } catch (_e) { platform = 'web'; }
    const response = await axios.post(`${API}/auth/request-otp`, { phone_e164, platform }, { timeout: 10000 });
    const data = response.data;
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
  socialAuth: async (provider, idToken, appleName = null) => {
    const res = await axios.post(`${API}/auth/social`, {
      provider,
      id_token: idToken,
      apple_name: appleName,
    }, { timeout: 15000 });
    return res.data;
  },
  socialSendOtp: async (sessionToken, phone = null) => {
    // #395 — pass platform so backend can pick Android SMS Retriever format on Android builds
    let platform;
    try { platform = (await import('@capacitor/core')).Capacitor.getPlatform(); } catch (_e) { platform = 'web'; }
    const res = await axios.post(`${API}/auth/social/send-otp`, {
      session_token: sessionToken,
      phone: phone || undefined,
      platform,
    }, { timeout: 10000 });
    return res.data;
  },
  socialVerifyOtp: async (sessionToken, otpCode) => {
    const res = await axios.post(`${API}/auth/social/verify-otp`, {
      session_token: sessionToken,
      otp_code: otpCode,
    }, { timeout: 10000 });
    return res.data;
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
    const response = await axios.get(`${API}/invites/${inviteId}/info`);
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
  async upload(projectId, unitId, file, discipline, opts = {}) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('discipline', discipline);
    if (opts.note) formData.append('note', opts.note);
    if (opts.name) formData.append('name', opts.name);
    if (opts.plan_type) formData.append('plan_type', opts.plan_type);
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
  async upload(projectId, file, discipline, { note, name, plan_type, floor_id, unit_id } = {}) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('discipline', discipline);
    if (note) formData.append('note', note);
    if (name) formData.append('name', name);
    if (plan_type) formData.append('plan_type', plan_type);
    if (floor_id) formData.append('floor_id', floor_id);
    if (unit_id) formData.append('unit_id', unit_id);
    const response = await axios.post(`${API}/projects/${projectId}/plans`, formData, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
  async update(projectId, planId, data) {
    const response = await axios.patch(`${API}/projects/${projectId}/plans/${planId}`, data, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
  markSeen(projectId, planId) {
    const token = localStorage.getItem('token');
    const url = `${API}/projects/${projectId}/plans/${planId}/seen`;
    try {
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        keepalive: true,
        body: '{}',
      });
    } catch {}
  },
  async getSeenStatus(projectId, planId) {
    const response = await axios.get(`${API}/projects/${projectId}/plans/${planId}/seen`, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
  async history(projectId, planId) {
    const response = await axios.get(`${API}/projects/${projectId}/plans/${planId}/history`, {
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
  async uploadVersion(projectId, planId, file, note = '') {
    const formData = new FormData();
    formData.append('file', file);
    if (note) formData.append('note', note);
    const response = await axios.post(`${API}/projects/${projectId}/plans/${planId}/versions`, formData, {
      headers: getAuthHeader(),
    });
    return response.data;
  },
  async getVersions(projectId, planId) {
    const response = await axios.get(`${API}/projects/${projectId}/plans/${planId}/versions`, {
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
  async invoicesSummary() {
    const response = await axios.get(`${API}/admin/billing/invoices-summary`, { headers: getAuthHeader() });
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
  async migrationDryRun() {
    const response = await axios.get(`${API}/admin/billing/migration/dry-run`, { headers: getAuthHeader() });
    return response.data;
  },
  async migrationApply() {
    const response = await axios.post(`${API}/admin/billing/migration/apply`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async recalcAllOrgs() {
    const response = await axios.post(`${API}/admin/billing/recalc-all`, {}, { headers: getAuthHeader() });
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
  async checkout(orgId, cycle = 'monthly', plan = 'standard') {
    const response = await axios.post(`${API}/billing/org/${orgId}/checkout`, { cycle, plan }, { headers: getAuthHeader() });
    return response.data;
  },
  async plansAvailable(orgId) {
    const response = await axios.get(`${API}/billing/plans-available`, {
      params: { org_id: orgId },
      headers: getAuthHeader(),
    });
    return response.data;
  },
  async getFounderConfig() {
    const response = await axios.get(`${API}/admin/config/founder-plan`, { headers: getAuthHeader() });
    return response.data;
  },
  async toggleFounderPlan(enabled) {
    const response = await axios.patch(`${API}/admin/config/founder-plan`,
      { enabled },
      { headers: getAuthHeader() }
    );
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
  async updateOrgPricing(orgId, data) {
    const response = await axios.patch(`${API}/admin/billing/org/${orgId}/pricing`, data, { headers: getAuthHeader() });
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
  async failedRenewals() {
    const response = await axios.get(`${API}/billing/failed-renewals`, { headers: getAuthHeader() });
    return response.data;
  },
  async resolveFailedRenewal(attemptId) {
    const response = await axios.post(`${API}/billing/resolve-failed-renewal`, { attempt_id: attemptId }, { headers: getAuthHeader() });
    return response.data;
  },
  async getPendingQuotaRequest(projectId) {
    const response = await axios.get(`${API}/billing/project/${projectId}/pending-quota-request`, { headers: getAuthHeader() });
    return response.data;
  },
  async createQuotaRequest(projectId, body) {
    const response = await axios.post(`${API}/billing/project/${projectId}/request-quota`, body, { headers: getAuthHeader() });
    return response.data;
  },
  async getRecentQuotaUpdates(projectId) {
    const response = await axios.get(`${API}/billing/project/${projectId}/recent-quota-updates`, { headers: getAuthHeader() });
    return response.data;
  },
  async listQuotaRequests(status = 'pending') {
    const response = await axios.get(`${API}/admin/quota-requests?status=${status}`, { headers: getAuthHeader() });
    return response.data;
  },
  async approveQuotaRequest(requestId, body = {}) {
    const response = await axios.post(`${API}/admin/quota-requests/${requestId}/approve`, body, { headers: getAuthHeader() });
    return response.data;
  },
  async rejectQuotaRequest(requestId, body = {}) {
    const response = await axios.post(`${API}/admin/quota-requests/${requestId}/reject`, body, { headers: getAuthHeader() });
    return response.data;
  },
  async setProjectTotalUnits(projectId, totalUnits, reason = '') {
    const response = await axios.post(
      `${API}/admin/projects/${projectId}/set-total-units`,
      { total_units: totalUnits, reason },
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async cancelSubscription(orgId, reason = '') {
    const response = await axios.post(
      `${API}/billing/org/${orgId}/cancel`,
      { reason },
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async reactivateSubscription(orgId) {
    const response = await axios.post(
      `${API}/billing/org/${orgId}/reactivate`,
      {},
      { headers: getAuthHeader() }
    );
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

export const adminOrgService = {
  async listOrgs() {
    const response = await axios.get(`${API}/admin/billing/orgs`, { headers: getAuthHeader() });
    return response.data;
  },
  async getOrgProjects(orgId) {
    const response = await axios.get(`${API}/admin/orgs/${orgId}/projects`, { headers: getAuthHeader() });
    return response.data;
  },
  async getOrgMembers(orgId) {
    const response = await axios.get(`${API}/orgs/${orgId}/members`, { headers: getAuthHeader() });
    return response.data;
  },
  async updateOrg(orgId, data) {
    const response = await axios.put(`${API}/admin/orgs/${orgId}`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async changeOwner(orgId, userId) {
    const response = await axios.put(`${API}/admin/orgs/${orgId}/owner`, { user_id: userId }, { headers: getAuthHeader() });
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
  async getUnitRun(unitId) {
    const response = await axios.get(`${API}/qc/units/${unitId}/run`, { headers: getAuthHeader() });
    return response.data;
  },
  async getUnitsStatus(floorId) {
    const response = await axios.get(`${API}/qc/floors/${floorId}/units-status`, { headers: getAuthHeader() });
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
  async getExecutionSummary(projectId) {
    const response = await axios.get(`${API}/qc/projects/${projectId}/execution-summary`, { headers: getAuthHeader() });
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
  async updateMyPreferredLanguage(lang) {
    const response = await axios.put(`${API}/auth/me/preferred-language`, { preferred_language: lang }, { headers: getAuthHeader() });
    return response.data;
  },
  async updateWhatsAppNotifications(enabled) {
    const response = await axios.put(`${API}/auth/me/whatsapp-notifications`, { enabled }, { headers: getAuthHeader() });
    return response.data;
  },
};

export const deletionService = {
  async requestOtp() {
    const response = await axios.post(`${API}/users/me/request-deletion-otp`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async requestDeletion(body) {
    const response = await axios.post(`${API}/users/me/request-deletion`, body, { headers: getAuthHeader() });
    return response.data;
  },
  async requestFullDeletion(body) {
    const response = await axios.post(`${API}/users/me/request-full-deletion`, body, { headers: getAuthHeader() });
    return response.data;
  },
  async cancelDeletion() {
    const response = await axios.post(`${API}/users/me/cancel-deletion`, {}, { headers: getAuthHeader() });
    return response.data;
  },
  async getStatus() {
    const response = await axios.get(`${API}/users/me/deletion-status`, { headers: getAuthHeader() });
    return response.data;
  },
};

export const templateService = {
  async list(params = {}) {
    const response = await axios.get(`${API}/admin/qc/templates`, { headers: getAuthHeader(), params });
    return response.data;
  },
  async get(templateId) {
    const response = await axios.get(`${API}/admin/qc/templates/${templateId}`, { headers: getAuthHeader() });
    return response.data;
  },
  async create(data) {
    const response = await axios.post(`${API}/admin/qc/templates`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async update(templateId, data) {
    const response = await axios.put(`${API}/admin/qc/templates/${templateId}`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async clone(templateId, data) {
    const response = await axios.post(`${API}/admin/qc/templates/${templateId}/clone`, data || {}, { headers: getAuthHeader() });
    return response.data;
  },
  async assignToProject(projectId, data) {
    const response = await axios.put(`${API}/projects/${projectId}/qc-template`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async assignHandoverToProject(projectId, data) {
    const response = await axios.put(`${API}/projects/${projectId}/handover-template`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async getProjectAssignment(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/qc-template`, { headers: getAuthHeader() });
    return response.data;
  },
  async getHandoverProjectAssignment(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/handover-template`, { headers: getAuthHeader() });
    return response.data;
  },
  async archiveFamily(familyId, archive = true) {
    const response = await axios.put(`${API}/admin/qc/templates/${familyId}/archive`, { archive }, { headers: getAuthHeader() });
    return response.data;
  },
};

export const projectQcService = {
  async getAssignment(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/qc-template`, { headers: getAuthHeader() });
    return response.data;
  },
};

export const handoverService = {
  async listProtocols(projectId, params = {}) {
    const query = new URLSearchParams();
    if (params.unit_id) query.set('unit_id', params.unit_id);
    if (params.building_id) query.set('building_id', params.building_id);
    if (params.type) query.set('type', params.type);
    if (params.status) query.set('status', params.status);
    const qs = query.toString();
    const url = `${API}/projects/${projectId}/handover/protocols${qs ? `?${qs}` : ''}`;
    const response = await axios.get(url, { headers: getAuthHeader() });
    return response.data;
  },
  async createProtocol(projectId, data) {
    const response = await axios.post(`${API}/projects/${projectId}/handover/protocols`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async getProtocol(projectId, protocolId) {
    const response = await axios.get(`${API}/projects/${projectId}/handover/protocols/${protocolId}`, { headers: getAuthHeader() });
    return response.data;
  },
  async updateProtocol(projectId, protocolId, data) {
    const response = await axios.put(`${API}/projects/${projectId}/handover/protocols/${protocolId}`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async updateItem(projectId, protocolId, sectionId, itemId, data) {
    const response = await axios.put(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/sections/${sectionId}/items/${itemId}`,
      data, { headers: getAuthHeader() }
    );
    return response.data;
  },
  async batchUpdateItems(projectId, protocolId, sectionId, data) {
    const response = await axios.patch(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/sections/${sectionId}/batch-items`,
      data, { headers: getAuthHeader() }
    );
    return response.data;
  },
  async createDefectFromItem(projectId, protocolId, itemId, data) {
    const response = await axios.post(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/items/${itemId}/create-defect`,
      data, { headers: getAuthHeader() }
    );
    return response.data;
  },
  async signRole(projectId, protocolId, role, formData) {
    const response = await axios.put(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/signatures/${role}`,
      formData, { headers: { ...getAuthHeader(), 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },
  async deleteSignature(projectId, protocolId, role) {
    const response = await axios.delete(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/signatures/${role}`,
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async getSignatureImage(projectId, protocolId, role) {
    const response = await axios.get(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/signatures/${role}/image`,
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async getSummary(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/handover/summary`, { headers: getAuthHeader() });
    return response.data;
  },
  async getOverview(projectId, params = {}) {
    const response = await axios.get(`${API}/projects/${projectId}/handover/overview`, { headers: getAuthHeader(), params });
    return response.data;
  },
  async getTemplate(projectId) {
    const response = await axios.get(`${API}/projects/${projectId}/handover-template`, { headers: getAuthHeader() });
    return response.data;
  },
  async assignTemplate(projectId, data) {
    const response = await axios.put(`${API}/projects/${projectId}/handover-template`, data, { headers: getAuthHeader() });
    return response.data;
  },
  async getOrgLegalSections(orgId) {
    const response = await axios.get(`${API}/organizations/${orgId}/handover-legal-sections`, { headers: getAuthHeader() });
    return response.data;
  },
  async putOrgLegalSections(orgId, sections) {
    const response = await axios.put(`${API}/organizations/${orgId}/handover-legal-sections`, { sections }, { headers: getAuthHeader() });
    return response.data;
  },
  async uploadOrgLogo(orgId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.put(`${API}/organizations/${orgId}/logo`, formData, {
      headers: { ...getAuthHeader(), 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  async deleteOrgLogo(orgId) {
    const response = await axios.delete(`${API}/organizations/${orgId}/logo`, { headers: getAuthHeader() });
    return response.data;
  },
  async updateLegalSectionBody(projectId, protocolId, sectionId, body) {
    const response = await axios.put(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/legal-sections/${sectionId}`,
      { body }, { headers: getAuthHeader() }
    );
    return response.data;
  },
  async signLegalSection(projectId, protocolId, sectionId, formData) {
    const response = await axios.put(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/legal-sections/${sectionId}/sign`,
      formData, { headers: { ...getAuthHeader(), 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },
  async getLegalSectionSignatureImage(projectId, protocolId, sectionId, signerSlot = null) {
    const params = signerSlot ? { signer_slot: signerSlot } : {};
    const response = await axios.get(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/legal-sections/${sectionId}/signature-image`,
      { headers: getAuthHeader(), params }
    );
    return response.data;
  },
  async uploadMeterPhoto(projectId, protocolId, meterType, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/meter-photo/${meterType}`,
      formData, { headers: { ...getAuthHeader(), 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },
  async uploadTenantIdPhoto(projectId, protocolId, tenantIdx, formData) {
    const response = await axios.post(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/tenants/${tenantIdx}/id-photo`,
      formData, { headers: { ...getAuthHeader(), 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },
  async deleteTenantIdPhoto(projectId, protocolId, tenantIdx) {
    const response = await axios.delete(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/tenants/${tenantIdx}/id-photo`,
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async updateTenantNotes(projectId, protocolId, tenantNotes) {
    const response = await axios.put(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/tenant-notes`,
      { tenant_notes: tenantNotes }, { headers: getAuthHeader() }
    );
    return response.data;
  },
  async getPdfBlob(projectId, protocolId) {
    const response = await axios.get(
      `${API}/projects/${projectId}/handover/protocols/${protocolId}/pdf`,
      { headers: getAuthHeader(), responseType: 'blob' }
    );
    return response.data;
  },
  async downloadPdf(projectId, protocolId, filename) {
    const blob = await this.getPdfBlob(projectId, protocolId);
    const finalName = filename || `protocol_${protocolId.slice(0, 8)}.pdf`;
    return downloadBlob(new Blob([blob], { type: 'application/pdf' }), finalName, 'application/pdf');
  },
};

export const g4ImportService = {
  async downloadTemplate(projectId) {
    const response = await axios.get(
      `${API}/projects/${projectId}/import/g4/template`,
      { headers: getAuthHeader(), responseType: 'blob' }
    );
    return downloadBlob(
      new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }),
      'g4_template.xlsx',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    );
  },
  async preview(projectId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(
      `${API}/projects/${projectId}/import/g4/preview`,
      formData,
      { headers: { ...getAuthHeader(), 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },
  async execute(projectId, rows) {
    const response = await axios.post(
      `${API}/projects/${projectId}/import/g4/execute`,
      { rows },
      { headers: getAuthHeader() }
    );
    return response.data;
  },
};

export const exportService = {
  async exportDefects({ scope, unit_id, building_id, project_id, filters, format = 'excel' }) {
    const response = await axios.post(
      `${API}/defects/export`,
      { scope, unit_id, building_id, project_id, filters, format },
      { headers: getAuthHeader(), responseType: 'blob' }
    );
    const disposition = response.headers['content-disposition'] || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const ext = format === 'pdf' ? '.pdf' : '.xlsx';
    const filename = match ? match[1] : `defects_export_${new Date().toISOString().slice(0, 10)}${ext}`;
    const mime = format === 'pdf'
      ? 'application/pdf'
      : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    return downloadBlob(new Blob([response.data], { type: mime }), filename, mime);
  },
};

export const dataExportService = {
  async exportFullExcel(projectId) {
    const response = await axios.post(
      `${API}/projects/${projectId}/export/excel`, {},
      { headers: getAuthHeader(), responseType: 'blob' }
    );
    return response;
  },
  async startExport(projectId) {
    const response = await axios.post(
      `${API}/projects/${projectId}/export`, {},
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async getStatus(projectId, jobId) {
    const response = await axios.get(
      `${API}/projects/${projectId}/export/${jobId}`,
      { headers: getAuthHeader() }
    );
    return response.data;
  },
  async getLatest(projectId) {
    const response = await axios.get(
      `${API}/projects/${projectId}/export/latest`,
      { headers: getAuthHeader() }
    );
    return response.data;
  },
};

export const adminAnalyticsService = {
  async getUserActivity(params) {
    const response = await axios.get(`${API}/admin/analytics/user-activity`, {
      headers: getAuthHeader(), params,
    });
    return response.data;
  },
  async getFeatureUsage(period) {
    const response = await axios.get(`${API}/admin/analytics/feature-usage`, {
      headers: getAuthHeader(), params: { period },
    });
    return response.data;
  },
};
