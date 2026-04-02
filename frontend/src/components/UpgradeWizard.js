import React, { useState, useEffect, useMemo } from 'react';
import { billingService } from '../services/api';
import { formatCurrency } from '../utils/billingLabels';
import { toast } from 'sonner';
import { Loader2, Check, ChevronDown, ChevronUp, Info, CreditCard } from 'lucide-react';
const LICENSE_FIRST = 900;
const LICENSE_ADDITIONAL = 450;
const PRICE_PER_UNIT = 20;

export default function UpgradeWizard({ orgId, projects, canManageBilling, onPaymentRequested, renewalCycle, onCycleChange, selectedPlan: externalSelectedPlan }) {
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [units, setUnits] = useState('');
  const [saving, setSaving] = useState(false);
  const [serverPricing, setServerPricing] = useState(null);
  const [step, setStep] = useState(1);
  const [result, setResult] = useState(null);
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);
  const selectedPlan = externalSelectedPlan;

  const projectList = useMemo(() => projects || [], [projects]);
  const singleProject = projectList.length === 1;

  useEffect(() => {
    billingService.listActivePlans().then(data => {
      const plans = Array.isArray(data) ? data : data?.plans;
      if (plans?.length > 0) setServerPricing(plans[0]);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (singleProject) {
      setSelectedProjectId(projectList[0].project_id);
    } else if (projectList.length > 1) {
      const noBilling = projectList.find(p => !p.plan_id);
      if (noBilling) {
        setSelectedProjectId(noBilling.project_id);
      }
    }
  }, [projectList, singleProject]);

  useEffect(() => {
    if (!selectedProjectId) return;
    const proj = projectList.find(p => p.project_id === selectedProjectId);
    if (proj?.contracted_units) {
      setUnits(String(proj.contracted_units || ''));
    } else {
      setUnits('');
    }
  }, [selectedProjectId, projectList]);

  const selectedProject = projectList.find(p => p.project_id === selectedProjectId);

  const parsedUnits = parseInt(units) || 0;

  const preview = useMemo(() => {
    if (parsedUnits < 1) return null;
    const lf = serverPricing?.license_first ?? LICENSE_FIRST;
    const la = serverPricing?.license_additional ?? LICENSE_ADDITIONAL;
    const ppu = serverPricing?.price_per_unit ?? PRICE_PER_UNIT;
    const licenseFee = lf;
    const unitCost = parsedUnits * ppu;
    return { licenseFee, unitCost, total: licenseFee + unitCost, pricePerUnit: ppu, licenseAdditional: la };
  }, [parsedUnits, serverPricing]);

  const canProceedToStep2 = !!selectedProjectId;
  const canProceedToStep3 = parsedUnits >= 1;

  const isFounderSelected = selectedPlan === 'founder';

  const handleFounderSubmit = async () => {
    setSaving(true);
    try {
      const result = await billingService.checkout(orgId, renewalCycle || 'monthly', 'founder');
      if (result.payment_page_link) {
        window.location.href = result.payment_page_link;
      } else {
        toast.error('לא התקבל קישור תשלום');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת טופס תשלום');
    } finally {
      setSaving(false);
    }
  };

  const handleStandardSubmit = async () => {
    if (!selectedProjectId || parsedUnits < 1) return;
    setSaving(true);
    try {
      const payload = { plan_id: 'standard', contracted_units: parsedUnits };
      await billingService.updateProjectBilling(selectedProjectId, payload);

      const result = await billingService.checkout(orgId, renewalCycle || 'monthly', 'standard');
      if (result.payment_page_link) {
        window.location.href = result.payment_page_link;
      } else {
        toast.error('לא התקבל קישור תשלום');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת טופס תשלום');
    } finally {
      setSaving(false);
    }
  };

  const handlePaymentRequest = async () => {
    if (!selectedProjectId || parsedUnits < 1) return;
    setSaving(true);
    try {
      const payload = { plan_id: 'standard', contracted_units: parsedUnits };
      await billingService.updateProjectBilling(selectedProjectId, payload);

      const cycle = renewalCycle || 'monthly';
      const paymentResult = await billingService.createPaymentRequest(orgId, cycle);
      setResult(paymentResult);

      if (paymentResult.existing_open) {
        toast('כבר קיימת בקשת תשלום פתוחה — עדכנו את התמחור', { icon: 'ℹ️' });
      } else {
        toast.success('בקשת התשלום נשלחה בהצלחה');
      }

      onPaymentRequested?.(paymentResult);
      setStep(4);
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה בשליחת הבקשה';
      toast.error(detail);
    } finally {
      setSaving(false);
    }
  };

  if (!canManageBilling) return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm text-slate-600 flex items-center gap-2">
      <Info className="w-4 h-4 text-slate-400 shrink-0" />
      אין לך הרשאה לניהול חיוב. פנה לבעלי הארגון.
    </div>
  );
  if (projectList.length === 0) return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm text-slate-600 flex items-center gap-2">
      <Info className="w-4 h-4 text-slate-400 shrink-0" />
      אין פרויקטים עם חיוב. יש ליצור פרויקט ולהגדיר תמחור.
    </div>
  );

  if (isFounderSelected) {
    return (
      <div className="space-y-4">
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-3">
          <div className="text-sm font-bold text-slate-800">תוכנית מייסדים</div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500">מחיר חודשי</span>
            <span className="font-bold text-slate-900">₪500</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500">תקופת התחייבות</span>
            <span className="font-medium text-slate-700">6 חודשים</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500">פרויקטים</span>
            <span className="font-medium text-slate-700">1</span>
          </div>
        </div>

        <button
          onClick={handleFounderSubmit}
          disabled={saving}
          className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-medium py-3 rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
          {saving ? 'מעביר לתשלום...' : 'שלם באשראי — תוכנית מייסדים'}
        </button>
        <p className="text-xs text-slate-400 text-center">תועבר לדף תשלום מאובטח</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 mb-2">
        {[1, 2, 3].map(s => (
          <div key={s} className="flex items-center gap-1.5">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
              step > s ? 'bg-emerald-500 text-white'
                : step === s ? 'bg-amber-500 text-white'
                  : 'bg-slate-200 text-slate-500'
            }`}>
              {step > s ? <Check className="w-3.5 h-3.5" /> : s}
            </div>
            <span className={`text-xs font-medium hidden sm:inline ${step === s ? 'text-amber-700' : 'text-slate-400'}`}>
              {s === 1 ? 'פרויקט' : s === 2 ? 'יחידות' : 'סיכום'}
            </span>
            {s < 3 && <div className={`w-6 h-0.5 ${step > s ? 'bg-emerald-300' : 'bg-slate-200'}`} />}
          </div>
        ))}
      </div>

      {step === 1 && (
        <div className="space-y-3">
          <label className="block text-sm font-medium text-slate-700">בחר פרויקט</label>
          {singleProject ? (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center justify-between">
              <span className="font-medium text-slate-700">{selectedProject?.project_name || selectedProjectId}</span>
            </div>
          ) : (
            <div className="relative">
              <button
                type="button"
                onClick={() => setProjectDropdownOpen(!projectDropdownOpen)}
                className="w-full text-right bg-white border border-slate-300 rounded-lg px-3 py-2.5 text-sm flex items-center justify-between focus:outline-none focus:ring-2 focus:ring-amber-500"
              >
                <span className={selectedProjectId ? 'text-slate-800' : 'text-slate-400'}>
                  {selectedProject?.project_name || 'בחר פרויקט...'}
                </span>
                {projectDropdownOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>
              {projectDropdownOpen && (
                <div className="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                  {projectList.map(p => (
                    <button
                      key={p.project_id}
                      type="button"
                      onClick={() => {
                        setSelectedProjectId(p.project_id);
                        setProjectDropdownOpen(false);
                      }}
                      className={`w-full text-right px-3 py-2.5 text-sm hover:bg-amber-50 transition-colors flex items-center justify-between ${
                        selectedProjectId === p.project_id ? 'bg-amber-50 font-medium' : ''
                      }`}
                    >
                      <span>{p.project_name || p.project_id}</span>
                      <span className="text-xs text-slate-400">
                        {p.contracted_units ? `${p.contracted_units} יחידות` : 'ללא תמחור'}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          <button
            onClick={() => { if (canProceedToStep2) setStep(2); }}
            disabled={!canProceedToStep2}
            className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
          >
            המשך
          </button>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="block text-sm font-medium text-slate-700">הגדר יחידות</label>
            <button onClick={() => setStep(1)} className="text-xs text-amber-600 hover:text-amber-800">← חזרה</button>
          </div>
          <div className="text-xs text-slate-500 bg-slate-50 rounded px-2 py-1">
            פרויקט: <span className="font-medium text-slate-700">{selectedProject?.project_name}</span>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">כמות יחידות לחיוב</label>
            <input
              type="number"
              min={1}
              value={units}
              onChange={(e) => setUnits(e.target.value)}
              onBlur={() => { if (!units || parseInt(units) < 1) setUnits('1'); }}
              placeholder="הזן מספר יחידות"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              dir="ltr"
            />
          </div>
          {preview && (
            <div className="bg-slate-50 rounded-lg p-3 space-y-2">
              <div className="text-xs text-slate-500 font-medium">הערכה לפרויקט ראשון</div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">רישיון פרויקט</span>
                <span className="font-medium text-slate-700">{formatCurrency(preview.licenseFee)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">{parsedUnits} יחידות × {formatCurrency(preview.pricePerUnit)}</span>
                <span className="font-medium text-slate-700">{formatCurrency(preview.unitCost)}</span>
              </div>
              <div className="border-t border-slate-200 pt-2 flex justify-between">
                <span className="text-sm font-medium text-slate-700">סה״כ חודשי (הערכה)</span>
                <span className="text-lg font-bold text-slate-900">{formatCurrency(preview.total)}</span>
              </div>
              <div className="text-xs text-slate-400">פרויקט נוסף: רישיון {formatCurrency(preview.licenseAdditional)}</div>
            </div>
          )}
          <button
            onClick={() => { if (canProceedToStep3) setStep(3); }}
            disabled={!canProceedToStep3}
            className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
          >
            המשך לסיכום
          </button>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="block text-sm font-medium text-slate-700">סיכום ושליחה</label>
            <button onClick={() => setStep(2)} className="text-xs text-amber-600 hover:text-amber-800">← חזרה</button>
          </div>

          <div className="bg-slate-50 rounded-lg p-4 space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">פרויקט</span>
              <span className="font-medium text-slate-700">{selectedProject?.project_name}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-500">יחידות</span>
              <span className="font-medium text-slate-700">{parsedUnits}</span>
            </div>
            {preview && (
              <>
                <div className="border-t border-slate-200 pt-2 space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-500">רישיון פרויקט</span>
                    <span className="text-slate-700">{formatCurrency(preview.licenseFee)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-500">{parsedUnits} יחידות × {formatCurrency(preview.pricePerUnit)}</span>
                    <span className="text-slate-700">{formatCurrency(preview.unitCost)}</span>
                  </div>
                </div>
                <div className="border-t border-slate-200 pt-2 flex justify-between">
                  <span className="text-sm font-medium text-slate-700">סה״כ חודשי (הערכה)</span>
                  <span className="text-lg font-bold text-slate-900">{formatCurrency(preview.total)}</span>
                </div>
              </>
            )}
          </div>

          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-600">מחזור חיוב:</span>
            <div className="flex rounded-lg border border-slate-200 overflow-hidden">
              <button
                onClick={() => onCycleChange?.('monthly')}
                className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                  renewalCycle === 'monthly'
                    ? 'bg-amber-500 text-white'
                    : 'bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                חודשי
              </button>
              <button
                onClick={() => onCycleChange?.('yearly')}
                className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                  renewalCycle === 'yearly'
                    ? 'bg-amber-500 text-white'
                    : 'bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                שנתי
              </button>
            </div>
          </div>

          <button
            onClick={handleStandardSubmit}
            disabled={saving}
            className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-medium py-3 rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
            {saving ? 'מעביר לתשלום...' : `שלם באשראי — ₪${preview ? preview.total.toLocaleString() : ''}`}
          </button>
        </div>
      )}

      {step === 4 && result && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2 text-emerald-700 text-sm font-medium">
            <Check className="w-4 h-4" />
            <span>בקשת התשלום נשלחה בהצלחה</span>
          </div>
          <div className="text-xs text-slate-600 space-y-1">
            <div>מזהה בקשה: <span className="font-mono">{result.request_id?.slice(0, 8)}...</span></div>
            {result.requested_paid_until_display && (
              <div>תוקף לאחר תשלום: <span className="font-bold">{result.requested_paid_until_display}</span></div>
            )}
            {result.amount_ils != null && (
              <div>סכום: <span className="font-bold">₪{result.amount_ils}</span></div>
            )}
          </div>
          <button
            onClick={() => { setStep(1); setResult(null); }}
            className="text-xs text-amber-600 hover:text-amber-800 underline"
          >
            שלח בקשה נוספת
          </button>
        </div>
      )}
    </div>
  );
}
