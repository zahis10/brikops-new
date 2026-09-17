import axios from 'axios';
import { API, getAuthHeader } from './api';

const sparePhotoService = {
  async upload(unitId, category, file) {
    const form = new FormData();
    form.append('file', file);
    form.append('category', category);
    const response = await axios.post(
      `${API}/units/${unitId}/spare-photos`,
      form,
      { headers: getAuthHeader() }
    );
    return response.data;
  },

  async remove(unitId, photoId) {
    await axios.delete(
      `${API}/units/${unitId}/spare-photos/${photoId}`,
      { headers: getAuthHeader() }
    );
  },
};

export default sparePhotoService;
