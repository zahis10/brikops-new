import axios from 'axios';
import { API, getAuthHeader } from './api';

/**
 * Execution Matrix API client. Phase 2A uses GET only;
 * Phase 2B adds updateCell + getCellHistory; 2C/2D will add
 * stage management + saved views.
 *
 * Pattern matches projectService / safetyService in api.js
 * (axios + API + getAuthHeader). matrixService is the first
 * external consumer of getAuthHeader — establishes the pattern
 * for future services living outside api.js.
 */
export const matrixService = {
  async getMatrix(projectId) {
    const response = await axios.get(
      `${API}/execution-matrix/${projectId}`,
      { headers: getAuthHeader() }
    );
    return response.data;
  },

  async updateCell(projectId, unitId, stageId, payload) {
    // payload: { status?, note?, text_value? }
    // Returns: { project_id, unit_id, stage_id, status, note, text_value,
    //            last_updated_at, last_updated_by, last_actor_name }
    const response = await axios.put(
      `${API}/execution-matrix/${projectId}/cells/${unitId}/${stageId}`,
      payload,
      { headers: getAuthHeader() }
    );
    return response.data;
  },

  async getCellHistory(projectId, unitId, stageId, opts = {}) {
    // Returns: { history: [{ actor_id, actor_name, timestamp,
    //   status_before, status_after, note_before, note_after,
    //   text_before, text_after }] }
    // opts.signal: optional AbortSignal for cancellation
    const response = await axios.get(
      `${API}/execution-matrix/${projectId}/cells/${unitId}/${stageId}/history`,
      { headers: getAuthHeader(), signal: opts.signal }
    );
    return response.data;
  },

  async updateStages(projectId, payload) {
    // Phase 2C — replace the project's stage list (custom + hidden bases).
    // payload: {
    //   custom_stages_added: [{ id?, title, type, order }],
    //   base_stages_removed: [stage_id, ...],
    // }
    // Returns: { project_id, stages: [...resolved stages] }
    // NOTE: API constant already includes `/api` (per #491 D-svc finding).
    const response = await axios.patch(
      `${API}/execution-matrix/${projectId}/stages`,
      payload,
      { headers: getAuthHeader() }
    );
    return response.data;
  },
};

export default matrixService;
