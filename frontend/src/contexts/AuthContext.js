import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { BACKEND_URL, configService } from '../services/api';

const AuthContext = createContext(null);

const API = `${BACKEND_URL}/api`;

const RETRY_DELAY_MS = 5000;

const _setBrikopsCookie = () => {
  document.cookie = 'brikops_logged_in=1; domain=.brikops.com; path=/; max-age=2592000; SameSite=Lax; Secure';
};
const _clearBrikopsCookie = () => {
  document.cookie = 'brikops_logged_in=; domain=.brikops.com; path=/; max-age=0';
};

const _isAuthError = (error) => {
  const status = error?.response?.status;
  return status === 401 || status === 403;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [features, setFeatures] = useState(null);
  const [networkError, setNetworkError] = useState(false);
  const [token, setToken] = useState(() => {
    const hash = window.location.hash;
    if (hash) {
      const hashParams = new URLSearchParams(hash.substring(1));
      const hashToken = hashParams.get('token');
      if (hashToken) {
        localStorage.setItem('token', hashToken);
        _setBrikopsCookie();
        window.history.replaceState({}, '', window.location.pathname + window.location.search);
        return hashToken;
      }
    }
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get('_token');
    if (urlToken) {
      localStorage.setItem('token', urlToken);
      _setBrikopsCookie();
      urlParams.delete('_token');
      const newUrl = window.location.pathname + (urlParams.toString() ? '?' + urlParams.toString() : '');
      window.history.replaceState({}, '', newUrl);
      return urlToken;
    }
    return localStorage.getItem('token');
  });
  const [loading, setLoading] = useState(true);
  const retryTimerRef = useRef(null);
  const toastShownRef = useRef(false);

  useEffect(() => {
    return () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
    };
  }, []);

  const fetchCurrentUser = useCallback(async (isRetry = false) => {
    try {
      const response = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const userData = response.data;
      setUser(userData);
      setNetworkError(false);
      toastShownRef.current = false;
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
    } catch (error) {
      if (_isAuthError(error)) {
        setToken(null);
        setUser(null);
        setNetworkError(false);
        localStorage.removeItem('token');
        _clearBrikopsCookie();
        if (retryTimerRef.current) {
          clearTimeout(retryTimerRef.current);
          retryTimerRef.current = null;
        }
      } else {
        setNetworkError(true);
        if (isRetry && !toastShownRef.current) {
          toast.error('בעיית חיבור');
          toastShownRef.current = true;
        }
        const savedToken = token;
        retryTimerRef.current = setTimeout(() => {
          retryTimerRef.current = null;
          if (savedToken === localStorage.getItem('token')) {
            fetchCurrentUser(true);
          }
        }, RETRY_DELAY_MS);
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  const fetchFeatures = useCallback(async () => {
    try {
      const data = await configService.getFeatures();
      setFeatures(data?.feature_flags || {});
    } catch {
      setFeatures({});
    }
  }, []);

  useEffect(() => {
    if (token) {
      toastShownRef.current = false;
      fetchCurrentUser(false);
      fetchFeatures();
    } else {
      setLoading(false);
    }
  }, [token, fetchCurrentUser, fetchFeatures]);

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${API}/auth/login`, { email, password });
      const data = response.data;
      if (!data || !data.token) {
        console.error('[AUTH] Login response missing token', { status: response.status, hasData: !!data });
        return { success: false, error: 'תגובה לא תקינה מהשרת' };
      }
      const { token: newToken, user: userData, platform_role } = data;
      setToken(newToken);
      setUser({ ...userData, platform_role: platform_role || 'none' });
      try { localStorage.setItem('token', newToken); } catch (e) { console.warn('[AUTH] localStorage write failed', e); }
      try { _setBrikopsCookie(); } catch (e) { /* ignore cookie errors */ }
      return { success: true };
    } catch (error) {
      console.error('[AUTH] Login error', error?.message, error?.response?.status, error?.stack);
      const detail = error.response?.data?.detail;
      return {
        success: false,
        error: detail || (error.message ? `שגיאה טכנית: ${error.message}` : 'Login failed')
      };
    }
  };

  const loginWithOtp = (newToken, userData, platformRole) => {
    setToken(newToken);
    setUser({ ...userData, platform_role: platformRole || userData?.platform_role || 'none' });
    try { localStorage.setItem('token', newToken); } catch (e) { console.warn('[AUTH] localStorage write failed', e); }
    try { _setBrikopsCookie(); } catch (e) { /* ignore */ }
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
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    setToken(null);
    setUser(null);
    setNetworkError(false);
    localStorage.removeItem('token');
    _clearBrikopsCookie();
  };

  const refreshUser = useCallback(async () => {
    if (!token) return;
    try {
      const response = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUser(response.data);
    } catch {}
  }, [token]);

  const value = {
    user,
    token,
    loading,
    features,
    networkError,
    login,
    loginWithOtp,
    register,
    logout,
    refreshUser,
    isAuthenticated: !!token && !!user
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
