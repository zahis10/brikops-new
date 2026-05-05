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

  // === Phase 2D-1 (#500) — saved views CRUD ===
  // Backend endpoints already shipped in #483:
  //   GET    /execution-matrix/{projectId}/views
  //   POST   /execution-matrix/{projectId}/views
  //   PATCH  /execution-matrix/{projectId}/views/{viewId}   (NOT PUT — verified
  //                                                          execution_matrix_router.py:561)
  //   DELETE /execution-matrix/{projectId}/views/{viewId}
  //
  // payload.filters MUST match MatrixSavedViewFilters (schemas.py:969):
  //   { building_ids?, floor_ids?, unit_ids?,
  //     stage_status_filters?: {stageId: string[]},
  //     tag_value_filters?:    {stageId: string[]},
  //     search_text? }
  // Frontend sentinel '__empty__' → "" conversion happens in
  // useMatrixFilters.serializeFilters (callers pass already-serialized payloads).
  async listSavedViews(projectId) {
    const response = await axios.get(
      `${API}/execution-matrix/${projectId}/views`,
      { headers: getAuthHeader() }
    );
    return response.data?.views || [];
  },

  async createSavedView(projectId, payload) {
    // payload: { title, icon?, filters }
    const response = await axios.post(
      `${API}/execution-matrix/${projectId}/views`,
      payload,
      { headers: getAuthHeader() }
    );
    return response.data;
  },

  async updateSavedView(projectId, viewId, payload) {
    const response = await axios.patch(
      `${API}/execution-matrix/${projectId}/views/${viewId}`,
      payload,
      { headers: getAuthHeader() }
    );
    return response.data;
  },

  async deleteSavedView(projectId, viewId) {
    await axios.delete(
      `${API}/execution-matrix/${projectId}/views/${viewId}`,
      { headers: getAuthHeader() }
    );
    return { ok: true };
  },
};

export default matrixService;
