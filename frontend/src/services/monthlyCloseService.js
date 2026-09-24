import axios from 'axios';
import { API, getAuthHeader } from './api';

const path = (projectId) => `${API}/projects/${projectId}/monthly-close`;

export const monthlyCloseService = {
  async getSettings(projectId) {
    const response = await axios.get(`${path(projectId)}/settings`, { headers: getAuthHeader() });
    return response.data;
  },
  async putSettings(projectId, body) {
    const response = await axios.put(`${path(projectId)}/settings`, body, { headers: getAuthHeader() });
    return response.data;
  },
  async getMonths(projectId) {
    const response = await axios.get(`${path(projectId)}/months`, { headers: getAuthHeader() });
    return response.data;
  },
  async getMonth(projectId, month) {
    const response = await axios.get(`${path(projectId)}/${month}`, { headers: getAuthHeader() });
    return response.data;
  },
  async closeMonth(projectId, month, { note } = {}) {
    const response = await axios.post(`${path(projectId)}/${month}/close`, { note }, { headers: getAuthHeader() });
    return response.data;
  },
  async exportXlsx(projectId, month, companyId) {
    const response = await axios.post(
      `${path(projectId)}/${month}/export.xlsx`,
      { company_id: companyId },
      { headers: getAuthHeader(), responseType: 'blob' }
    );
    const cd = response.headers['content-disposition'] || '';
    let filename = `progress-account-${month}.xlsx`;
    const utf8Match = cd.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match) {
      try { filename = decodeURIComponent(utf8Match[1]); } catch { /* keep default */ }
    } else {
      const asciiMatch = cd.match(/filename="([^"]+)"/);
      if (asciiMatch) filename = asciiMatch[1];
    }
    return { blob: response.data, filename };
  },
};