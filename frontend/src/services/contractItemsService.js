import axios from 'axios';
import { API, getAuthHeader } from './api';

const path = (projectId) => `${API}/projects/${projectId}/contract-items`;
const options = () => ({ headers: getAuthHeader() });

export const contractItemsService = {
  async list(projectId) {
    const response = await axios.get(path(projectId), options());
    return response.data;
  },
  async create(projectId, body) {
    const response = await axios.post(path(projectId), body, options());
    return response.data;
  },
  async update(projectId, itemId, body) {
    const response = await axios.patch(`${path(projectId)}/${itemId}`, body, options());
    return response.data;
  },
  async setMeasurement(projectId, itemId, month, body) {
    const response = await axios.put(`${path(projectId)}/${itemId}/measurements/${month}`, body, options());
    return response.data;
  },
};
