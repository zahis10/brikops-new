import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { onboardingService, projectService } from '../services/api';
import { toast } from 'sonner';
import { ArrowRight, Check, X, Clock, Users, Loader2, Filter, Phone, Building2, Calendar } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';

const TABS = [
  { value: null, label: 'הכל' },
  { value: 'pending', label: 'ממתין' },
  { value: 'approved', label: 'אושר' },
  { value: 'rejected', label: 'נדחה' },
];

const TRACK_LABELS = {
  management: 'הנהלה',
  subcontractor: 'קבלן משנה',
};

const maskPhone = (phone) => {
  if (!phone || phone.length < 4) return phone || '';
  return phone.slice(0, -4).replace(/./g, '*') + phone.slice(-4);
};

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString('he-IL', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
};

const StatusBadge = ({ status }) => {
  const styles = {
    pending: 'bg-amber-100 text-amber-700 border-amber-200',
    approved: 'bg-green-100 text-green-700 border-green-200',
    rejected: 'bg-red-100 text-red-700 border-red-200',
  };
  const labels = {
    pending: 'ממתין',
    approved: 'אושר',
    rejected: 'נדחה',
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${styles[status] || 'bg-slate-100 text-slate-700 border-slate-200'}`}>
      {labels[status] || status}
    </span>
  );
};

const JoinRequestsPage = () => {
  const navigate = useNavigate();
  const [requests, setRequests] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [activeTab, setActiveTab] = useState(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [rejectReasonId, setRejectReasonId] = useState(null);
  const [rejectReason, setRejectReason] = useState('');

  useEffect(() => {
    const loadProjects = async () => {
      try {
        const data = await projectService.list();
        const list = Array.isArray(data) ? data : data.projects || [];
        setProjects(list);
        if (list.length > 0) {
          setSelectedProject(list[0]._id || list[0].id);
        }
      } catch (err) {
        console.error('Failed to load projects:', err);
      }
    };
    loadProjects();
  }, []);

  const loadRequests = useCallback(async () => {
    if (!selectedProject) return;
    setLoading(true);
    try {
      const data = await onboardingService.getJoinRequests(selectedProject, activeTab);
      setRequests(Array.isArray(data) ? data : data.requests || []);
    } catch (error) {
      toast.error('שגיאה בטעינת בקשות');
      console.error('Failed to load join requests:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedProject, activeTab]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  const handleApprove = async (requestId) => {
    setActionLoading(requestId);
    try {
      await onboardingService.approveRequest(requestId);
      toast.success('הבקשה אושרה בהצלחה');
      loadRequests();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'שגיאה באישור הבקשה');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (requestId) => {
    if (!rejectReason.trim()) {
      toast.error('יש להזין סיבת דחייה');
      return;
    }
    setActionLoading(requestId);
    try {
      await onboardingService.rejectRequest(requestId, rejectReason);
      toast.success('הבקשה נדחתה');
      setRejectReasonId(null);
      setRejectReason('');
      loadRequests();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'שגיאה בדחיית הבקשה');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-3">
          <button
            onClick={() => navigate('/projects')}
            className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <ArrowRight className="w-5 h-5 text-slate-600" />
          </button>
          <div className="flex-1">
            <h1 className="text-xl font-bold text-slate-900" style={{ fontFamily: 'Rubik, sans-serif' }}>
              בקשות הצטרפות
            </h1>
            <p className="text-sm text-slate-500">ניהול בקשות הצטרפות לפרויקט</p>
          </div>
          <Users className="w-6 h-6 text-amber-500" />
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-6">
        {projects.length > 1 && (
          <div className="mb-4">
            <select
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
              className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
            >
              {projects.map((p) => (
                <option key={p._id || p.id} value={p._id || p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="flex gap-2 mb-6 p-1 bg-slate-100 rounded-lg overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.value || 'all'}
              onClick={() => setActiveTab(tab.value)}
              className={`flex-1 min-w-fit py-2 px-3 rounded-md text-sm font-medium transition-all whitespace-nowrap ${
                activeTab === tab.value
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
          </div>
        ) : requests.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <Filter className="w-12 h-12 mb-3" />
            <p className="text-lg font-medium">אין בקשות</p>
            <p className="text-sm">לא נמצאו בקשות הצטרפות</p>
          </div>
        ) : (
          <div className="space-y-3">
            {requests.map((req) => {
              const reqId = req._id || req.id;
              return (
                <Card key={reqId} className="p-4 bg-white border border-slate-200 rounded-xl">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-base font-semibold text-slate-900">
                          {req.full_name || req.name || 'ללא שם'}
                        </h3>
                        <StatusBadge status={req.status} />
                      </div>
                      <div className="flex flex-wrap gap-3 text-sm text-slate-500">
                        <span className="inline-flex items-center gap-1">
                          <Phone className="w-3.5 h-3.5" />
                          <bdi className="font-mono" dir="ltr">{maskPhone(req.phone_e164 || req.phone)}</bdi>
                        </span>
                        {(req.track) && (
                          <span className="inline-flex items-center gap-1">
                            <Users className="w-3.5 h-3.5" />
                            {TRACK_LABELS[req.track] || req.track}
                          </span>
                        )}
                        {req.role && (
                          <span className="text-amber-600 font-medium">{req.role_label || req.role}</span>
                        )}
                        {req.company_name && (
                          <span className="inline-flex items-center gap-1">
                            <Building2 className="w-3.5 h-3.5" />
                            {req.company_name}
                          </span>
                        )}
                        {(req.created_at || req.requested_at) && (
                          <span className="inline-flex items-center gap-1">
                            <Calendar className="w-3.5 h-3.5" />
                            {formatDate(req.created_at || req.requested_at)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {req.status === 'pending' && (
                    <div className="flex gap-2 mt-3 pt-3 border-t border-slate-100">
                      {rejectReasonId === reqId ? (
                        <div className="flex-1 space-y-2">
                          <input
                            type="text"
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            placeholder="סיבת דחייה..."
                            className="w-full h-9 px-3 text-sm text-right bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500/50 focus:border-red-500"
                            autoFocus
                          />
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              onClick={() => handleReject(reqId)}
                              disabled={actionLoading === reqId}
                              className="bg-red-500 hover:bg-red-600 text-white text-xs"
                            >
                              {actionLoading === reqId ? <Loader2 className="w-3 h-3 animate-spin" /> : 'אישור דחייה'}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => { setRejectReasonId(null); setRejectReason(''); }}
                              className="text-xs"
                            >
                              ביטול
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <Button
                            size="sm"
                            onClick={() => handleApprove(reqId)}
                            disabled={actionLoading === reqId}
                            className="bg-green-500 hover:bg-green-600 text-white text-sm flex-1"
                          >
                            {actionLoading === reqId ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <>
                                <Check className="w-4 h-4 ml-1" />
                                אישור
                              </>
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setRejectReasonId(reqId)}
                            disabled={actionLoading === reqId}
                            className="text-red-600 border-red-200 hover:bg-red-50 text-sm flex-1"
                          >
                            <X className="w-4 h-4 ml-1" />
                            דחייה
                          </Button>
                        </>
                      )}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default JoinRequestsPage;
