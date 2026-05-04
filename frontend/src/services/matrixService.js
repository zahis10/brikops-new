import axios from 'axios';
import { API, getAuthHeader } from './api';

/**
 * Execution Matrix API client. Phase 2A uses GET only;
 * Phase 2B/2C/2D will add update/saved views endpoints.
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
};

export default matrixService;
