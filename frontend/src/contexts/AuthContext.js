import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../services/api';

const AuthContext = createContext(null);

const API = `${BACKEND_URL}/api`;

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => {
    const hash = window.location.hash;
    if (hash) {
      const hashParams = new URLSearchParams(hash.substring(1));
      const hashToken = hashParams.get('token');
      if (hashToken) {
        localStorage.setItem('token', hashToken);
        window.history.replaceState({}, '', window.location.pathname + window.location.search);
        return hashToken;
      }
    }
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get('_token');
    if (urlToken) {
      localStorage.setItem('token', urlToken);
      urlParams.delete('_token');
      const newUrl = window.location.pathname + (urlParams.toString() ? '?' + urlParams.toString() : '');
      window.history.replaceState({}, '', newUrl);
      return urlToken;
    }
    return localStorage.getItem('token');
  });
  const [loading, setLoading] = useState(true);

  const fetchCurrentUser = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUser(response.data);
    } catch (error) {
      console.error('Failed to fetch user:', error);
      setToken(null);
      setUser(null);
      localStorage.removeItem('token');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      fetchCurrentUser();
    } else {
      setLoading(false);
    }
  }, [token, fetchCurrentUser]);

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${API}/auth/login`, { email, password });
      const { token: newToken, user: userData, platform_role } = response.data;
      setToken(newToken);
      setUser({ ...userData, platform_role: platform_role || 'none' });
      localStorage.setItem('token', newToken);
      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Login failed'
      };
    }
  };

  const loginWithOtp = (newToken, userData, platformRole) => {
    setToken(newToken);
    setUser({ ...userData, platform_role: platformRole || userData?.platform_role || 'none' });
    localStorage.setItem('token', newToken);
  };

  const register = async (userData) => {
    try {
      await axios.post(`${API}/auth/register`, userData);
      return await login(userData.email, userData.password);
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Registration failed'
      };
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
  };

  const value = {
    user,
    token,
    loading,
    login,
    loginWithOtp,
    register,
    logout,
    isAuthenticated: !!token && !!user
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
