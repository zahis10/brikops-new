import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { identityService } from '../services/api';

const IdentityContext = createContext(null);

export const useIdentity = () => {
  const context = useContext(IdentityContext);
  if (!context) {
    return {
      identityStatus: null,
      identityLoading: true,
      refreshIdentity: () => {},
      showCompleteForm: false,
      setShowCompleteForm: () => {},
    };
  }
  return context;
};

export const IdentityProvider = ({ children }) => {
  const { user, token } = useAuth();
  const [identityStatus, setIdentityStatus] = useState(null);
  const [identityLoading, setIdentityLoading] = useState(true);
  const [showCompleteForm, setShowCompleteForm] = useState(false);

  const fetchStatus = useCallback(async () => {
    if (!token || !user) {
      setIdentityStatus(null);
      setIdentityLoading(false);
      return;
    }
    try {
      const status = await identityService.getAccountStatus();
      setIdentityStatus(status);
    } catch (err) {
      setIdentityStatus(null);
    } finally {
      setIdentityLoading(false);
    }
  }, [token, user]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const refreshIdentity = useCallback(async () => {
    await fetchStatus();
    setShowCompleteForm(false);
    try { sessionStorage.removeItem('identity_banner_dismissed'); } catch {}
  }, [fetchStatus]);

  const value = {
    identityStatus,
    identityLoading,
    refreshIdentity,
    showCompleteForm,
    setShowCompleteForm,
  };

  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>;
};
