import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';

const BillingContext = createContext(null);

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const useBilling = () => {
  const context = useContext(BillingContext);
  if (!context) {
    return { billing: null, loading: true, refreshBilling: () => {}, isReadOnly: false, isOwner: false, canManageBilling: false, isOrgPm: false, roleDisplay: null, showPaywall: false, setShowPaywall: () => {}, orgBilling: null, projectBilling: null, fetchOrgBilling: () => {}, fetchProjectBilling: () => {} };
  }
  return context;
};

export const BillingProvider = ({ children }) => {
  const { user, token } = useAuth();
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showPaywall, setShowPaywall] = useState(false);
  const [orgBilling, setOrgBilling] = useState(null);
  const [projectBilling, setProjectBilling] = useState(null);

  const fetchBilling = useCallback(async () => {
    if (!token || !user) {
      setBilling(null);
      setLoading(false);
      return;
    }
    if (user.role === 'contractor') {
      setBilling(null);
      setLoading(false);
      return;
    }
    try {
      const response = await axios.get(`${API}/billing/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setBilling(response.data);
    } catch (err) {
      console.error('Failed to fetch billing info:', err);
    } finally {
      setLoading(false);
    }
  }, [token, user]);

  const fetchOrgBilling = useCallback(async (orgId) => {
    if (!token || !orgId) return;
    try {
      const response = await axios.get(`${API}/billing/org/${orgId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setOrgBilling(response.data);
    } catch (err) {
      if (err.response?.status !== 404) {
        console.error('Failed to fetch org billing:', err);
      }
      setOrgBilling(null);
    }
  }, [token]);

  const fetchProjectBilling = useCallback(async (projectId) => {
    if (!token || !projectId) return;
    try {
      const response = await axios.get(`${API}/billing/project/${projectId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setProjectBilling(response.data);
    } catch (err) {
      if (err.response?.status !== 404) {
        console.error('Failed to fetch project billing:', err);
      }
      setProjectBilling(null);
    }
  }, [token]);

  useEffect(() => {
    fetchBilling();
  }, [fetchBilling]);

  const isReadOnly = billing?.effective_access === 'read_only';
  const isOwner = billing?.is_owner === true || user?.platform_role === 'super_admin';
  const canManageBilling = billing?.can_manage_billing === true;
  const isOrgPm = billing?.is_org_pm === true;
  const roleDisplay = billing?.role_display || null;

  const value = {
    billing,
    loading,
    refreshBilling: fetchBilling,
    isReadOnly,
    isOwner,
    canManageBilling,
    isOrgPm,
    roleDisplay,
    showPaywall,
    setShowPaywall,
    orgBilling,
    projectBilling,
    fetchOrgBilling,
    fetchProjectBilling,
  };

  return <BillingContext.Provider value={value}>{children}</BillingContext.Provider>;
};
