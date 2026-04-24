import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { BACKEND_URL, configService } from '../services/api';
import { setLanguage } from '../i18n';

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
  if (status === 403 && error?.response?.data?.detail?.code === 'pending_deletion') return false;
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
    return localStorage.getItem('token');
  });
  const [loading, setLoading] = useState(true);
  const retryTimerRef = useRef(null);
  const toastShownRef = useRef(false);
  const sessionExpiredRef = useRef(false);

  useEffect(() => {
    return () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
    };
  }, []);

  useEffect(() => {
    const interceptorId = axios.interceptors.response.use(undefined, (error) => {
      if (
        error.response?.status === 403 &&
        error.response?.data?.detail?.code === 'pending_deletion'
      ) {
        error._pendingDeletion = true;
        setUser(prev => prev ? { ...prev, user_status: 'pending_deletion' } : prev);
        toast.dismiss();
      }
      return Promise.reject(error);
    });
    return () => axios.interceptors.response.eject(interceptorId);
  }, []);

  // Global 401 handler for mid-session token expiry.
  //
  // Fires when ANY API call returns 401 on a non-auth endpoint while the user
  // has a token. Clears the token, notifies the user, and redirects to /login.
  //
  // Why this lives here (not in api.js):
  //   See the comment in services/api.js line 47-50 — auth handling must
  //   stay in AuthContext to avoid breaking the network-error resilience
  //   logic in fetchCurrentUser.
  //
  // Why full-page reload (window.location.href):
  //   AuthProvider is rendered OUTSIDE BrowserRouter (App.js:520), so we
  //   can't use useNavigate() here. Full reload also guarantees clean
  //   state after session end — safer than trying to reset piece-by-piece.
  //
  // Debounce:
  //   If 5 concurrent API calls all return 401, we only want to fire the
  //   flow once. The ref guards against double-firing within a short window.
  useEffect(() => {
    const interceptorId = axios.interceptors.response.use(undefined, (error) => {
      try {
        const status = error?.response?.status;
        if (status !== 401) return Promise.reject(error);

        // Skip auth endpoints — failed login/OTP/register legitimately return 401.
        const url = error.config?.url || '';
        if (url.includes('/auth/')) return Promise.reject(error);

        // Skip if user has no token — no session to expire.
        const currentToken = localStorage.getItem('token');
        if (!currentToken) return Promise.reject(error);

        // Debounce: fire once per expiry event.
        if (sessionExpiredRef.current) return Promise.reject(error);
        sessionExpiredRef.current = true;

        // Clear session state (without triggering another logout-related re-render).
        setToken(null);
        setUser(null);
        setNetworkError(false);
        localStorage.removeItem('token');
        _clearBrikopsCookie();

        // Notify and redirect.
        toast.info('החיבור פג, אנא התחבר מחדש');
        // 1500ms gives the user enough time to actually READ the Hebrew toast
        // before the page reloads. Concurrent 401s during this window are
        // caught by the sessionExpiredRef debounce above (they Promise.reject
        // without re-triggering the flow — API calls to backend still fire,
        // but are harmless 401 responses).
        setTimeout(() => {
          window.location.href = '/login';
        }, 1500);
      } catch (e) {
        console.warn('[AUTH] 401 interceptor failure', e);
      }
      return Promise.reject(error);
    });
    return () => axios.interceptors.response.eject(interceptorId);
  }, []);

  const fetchCurrentUser = useCallback(async (isRetry = false) => {
    try {
      const response = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const userData = response.data;
      if (userData.role === 'contractor' && userData.preferred_language) {
        setLanguage(userData.preferred_language);
      }
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
      if (userData?.role === 'contractor' && userData?.preferred_language) {
        setLanguage(userData.preferred_language);
      }
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
    if (userData?.role === 'contractor' && userData?.preferred_language) {
      setLanguage(userData.preferred_language);
    }
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

  const forceUserStatus = useCallback((status) => {
    setUser(prev => prev ? { ...prev, user_status: status } : prev);
  }, []);

  const replaceToken = useCallback((newToken) => {
    if (!newToken) return;
    setToken(newToken);
    try { localStorage.setItem('token', newToken); } catch (e) { console.warn('[AUTH] localStorage write failed', e); }
  }, []);

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
    forceUserStatus,
    replaceToken,
    isAuthenticated: !!token && !!user
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
