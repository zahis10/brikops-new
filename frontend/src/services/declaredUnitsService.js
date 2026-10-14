import axios from 'axios';
import { API, getAuthHeader } from './api';

export const declaredUnitsService = {
  async update(projectId, totalUnits) {
    const res = await axios.put(`${API}/projects/${projectId}/declared-units`, { total_units: totalUnits }, { headers: getAuthHeader() });
    return res.data;
  },
};
