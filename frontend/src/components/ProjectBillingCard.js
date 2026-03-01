import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { billingService } from '../services/api';
import {
  getBillingStatusLabel, getBillingStatusColor,
  getAccessLabel, getTierLabel, getPlanLabel, formatCurrency, getObservedUnitsWarning,
} from '../utils/billingLabels';
import { getPlanBadge } from '../utils/billingPlanCatalog';
import { getBillingHubUrl } from '../utils/billingHub';
import { ExternalLink } from 'lucide-react';

function PlanBadge({ planId }) {
  const badge = getPlanBadge(planId);
  if (!badge) return null;
  const isPro = planId === 'plan_pro';
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
      isPro ? 'bg-amber-200 text-amber-800' : 'bg-slate-200 text-slate-600'
    }`}>
      {badge}
    </span>
  );
}

export default function ProjectBillingCard({ projectId, userRole }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const d = await billingService.projectBilling(projectId);
      setData(d);
    } catch (err) {
      if (err.response?.status === 404) {
        setData(null);
      } else {
        setError(err.response?.data?.detail || 'שגיאה בטעינת נתוני חיוב');
      }
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) return <div className="text-sm text-slate-400 py-2">טוען נתוני חיוב...</div>;
  if (error) return <div className="text-sm text-red-500 py-2">{error}</div>;
  if (!data) return null;

  const billing = data.billing;
  const warning = billing ? getObservedUnitsWarning(billing.observed_units, billing.contracted_units) : null;

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-4" dir="rtl">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">חיוב פרויקט</h3>
        <div className="flex items-center gap-2">
          {data.subscription_status && (
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${getBillingStatusColor(data.subscription_status)}`}>
              {getBillingStatusLabel(data.subscription_status)}
            </span>
          )}
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            data.effective_access === 'full_access' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
          }`}>
            {getAccessLabel(data.effective_access)}
          </span>
        </div>
      </div>

      <div className="text-sm text-slate-600">
        <span className="text-slate-500">ארגון:</span>
        <span className="mr-1 font-medium text-slate-700">{data.org_name}</span>
      </div>

      {(() => {
        const status = data.subscription_status;
        if (status === 'trialing' && data.trial_end_at) {
          return (
            <div className="flex items-center gap-2 text-sm bg-slate-50 rounded-lg px-3 py-2">
              <span className="text-slate-500">סיום ניסיון:</span>
              <span className="font-medium text-slate-700">{new Date(data.trial_end_at).toLocaleDateString('he-IL')}</span>
            </div>
          );
        }
        if (status === 'active' && data.paid_until) {
          const paidDate = new Date(data.paid_until);
          const now = new Date();
          const daysLeft = Math.ceil((paidDate - now) / 86400000);
          const isExpired = data.read_only_reason === 'payment_expired';
          const isWarning = !isExpired && daysLeft <= 14;
          return (
            <div className={`flex items-center gap-2 text-sm rounded-lg px-3 py-2 ${
              isExpired ? 'bg-red-50' : isWarning ? 'bg-amber-50' : 'bg-emerald-50'
            }`}>
              <span className="text-slate-500">{isExpired ? 'שולם עד:' : 'בתוקף עד:'}</span>
              <span className={`font-semibold ${
                isExpired ? 'text-red-600' : isWarning ? 'text-amber-600' : 'text-emerald-700'
              }`}>
                {paidDate.toLocaleDateString('he-IL')}
                {isExpired && ' (פג תוקף)'}
                {isWarning && ` (${daysLeft} ימים)`}
              </span>
            </div>
          );
        }
        return null;
      })()}

      {billing ? (
        <div className="space-y-3">
          {billing.plan_id && (
            <div className="bg-slate-50 rounded-md p-3 space-y-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-semibold text-slate-500">חבילת שירות:</span>
                <span className="font-semibold text-sm text-slate-800">{getPlanLabel(billing.plan_id)}</span>
                <PlanBadge planId={billing.plan_id} />
              </div>
            </div>
          )}

          <div className="bg-slate-50 rounded-md p-3 space-y-2">
            <div className="text-xs font-semibold text-slate-500 mb-1">פירוק עלות חודשי לפרויקט</div>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">עלות חבילה</span>
                <span className="font-medium text-slate-700">{formatCurrency(billing.project_fee_snapshot)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">מדרגת יחידות ({getTierLabel(billing.tier_code)})</span>
                <span className="font-medium text-slate-700">{formatCurrency(billing.tier_fee_snapshot)}</span>
              </div>
              <div className="flex justify-between items-center gap-2 text-sm">
                <span className="text-slate-500">יחידות לחיוב</span>
                <span className="font-medium text-slate-700">{billing.contracted_units}</span>
              </div>
              <div className="flex justify-between items-center gap-2 text-sm">
                <span className="text-slate-500">יחידות בפועל</span>
                <span className={`font-medium ${warning ? 'text-amber-600' : 'text-slate-700'}`}>{billing.observed_units}</span>
              </div>
            </div>
            <div className="border-t border-slate-200 pt-2 flex items-center justify-between">
              <span className="text-sm text-slate-500">סה״כ חודשי לפרויקט</span>
              <span className="text-lg font-bold text-slate-900">{formatCurrency(billing.monthly_total)}</span>
            </div>
            {warning && (
              <div className="text-xs text-amber-600 bg-amber-50 px-2 py-1.5 rounded">
                {warning}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="text-sm text-slate-400 bg-slate-50 rounded-md p-3">
          לא הוגדר חיוב לפרויקט זה
        </div>
      )}

      {data.org_id && (
        <button
          onClick={() => navigate(getBillingHubUrl({ orgId: data.org_id, projectId }))}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-white font-medium rounded-lg text-sm transition-colors"
        >
          <ExternalLink className="w-4 h-4" />
          מעבר לניהול חיוב
        </button>
      )}
    </div>
  );
}
