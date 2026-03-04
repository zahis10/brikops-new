import React, { useState, useEffect, useMemo } from 'react';
import { billingService } from '../services/api';
import { getAllPlanCatalog } from '../utils/billingPlanCatalog';
import { formatCurrency } from '../utils/billingLabels';
import { toast } from 'sonner';
import { Loader2, Check } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from './ui/dialog';

const CLIENT_TIERS = [
  { code: 'tier_s', label: 'עד 50 יחידות', max_units: 50, monthly_fee: 900 },
  { code: 'tier_m', label: '51-200 יחידות', max_units: 200, monthly_fee: 2400 },
  { code: 'tier_l', label: '201-500 יחידות', max_units: 500, monthly_fee: 4800 },
  { code: 'tier_xl', label: '501+ יחידות', max_units: null, monthly_fee: 8500 },
];

function resolveTier(units) {
  for (const tier of CLIENT_TIERS) {
    if (tier.max_units === null || units <= tier.max_units) return tier;
  }
  return CLIENT_TIERS[CLIENT_TIERS.length - 1];
}

// TODO: plan downgrade deferral (pending_plan_id) — currently all plan changes are immediate

export default function ProjectBillingEditModal({ open, onClose, projectBilling, onSaved }) {
  const plans = getAllPlanCatalog();
  const [selectedPlanId, setSelectedPlanId] = useState('');
  const [units, setUnits] = useState(0);
  const [saving, setSaving] = useState(false);
  const [serverPlans, setServerPlans] = useState(null);

  const originalPlanId = projectBilling?.plan_id || '';
  const originalUnits = projectBilling?.contracted_units || 0;

  useEffect(() => {
    if (open && projectBilling) {
      setSelectedPlanId(projectBilling.plan_id || '');
      setUnits(projectBilling.contracted_units || 0);
    }
  }, [open, projectBilling]);

  useEffect(() => {
    if (open) {
      billingService.listActivePlans().then(data => {
        if (data?.plans) setServerPlans(data.plans);
      }).catch(() => {});
    }
  }, [open]);

  const preview = useMemo(() => {
    if (!selectedPlanId || !units || units < 1) return null;
    const serverPlan = serverPlans?.find(p => p.id === selectedPlanId);
    let projectFee = 0;
    let tierFee = 0;
    let tierLabel = '';
    if (serverPlan) {
      projectFee = serverPlan.project_fee_monthly || 0;
      const tiers = serverPlan.unit_tiers || CLIENT_TIERS;
      for (const t of tiers) {
        if (t.max_units === null || units <= t.max_units) {
          tierFee = t.monthly_fee;
          tierLabel = t.label;
          break;
        }
      }
      if (!tierLabel && tiers.length > 0) {
        const last = tiers[tiers.length - 1];
        tierFee = last.monthly_fee;
        tierLabel = last.label;
      }
    } else {
      const catalog = plans.find(p => p.id === selectedPlanId);
      const tier = resolveTier(units);
      projectFee = catalog ? { plan_basic: 1200, plan_pro: 2000, plan_xl: 3500 }[selectedPlanId] || 0 : 0;
      tierFee = tier.monthly_fee;
      tierLabel = tier.label;
    }
    return { projectFee, tierFee, tierLabel, total: projectFee + tierFee };
  }, [selectedPlanId, units, serverPlans, plans]);

  const hasChanges = selectedPlanId !== originalPlanId || units !== originalUnits;

  const handleSave = async () => {
    if (!hasChanges) return;
    setSaving(true);
    try {
      const payload = {};
      if (selectedPlanId !== originalPlanId) payload.plan_id = selectedPlanId;
      if (units !== originalUnits) payload.contracted_units = units;

      const response = await billingService.updateProjectBilling(projectBilling.project_id, payload);

      if (response.pending_contracted_units != null) {
        const dateStr = response.pending_effective_from
          ? new Date(response.pending_effective_from).toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit' })
          : '';
        toast(`הירידה תיכנס לתוקף ב-${dateStr}. עד אז החיוב לפי הכמות הנוכחית.`, { icon: '📅' });
      } else if (units > originalUnits) {
        toast('ההגדלה פעילה מיד. החיוב יתעדכן לפי השיא החודשי.', { icon: '⬆️' });
      } else if (selectedPlanId !== originalPlanId && units === originalUnits) {
        toast.success('החבילה עודכנה בהצלחה.');
      } else {
        toast.success('השינויים נשמרו בהצלחה.');
      }

      onSaved?.(response);
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה בשמירת שינויים';
      toast.error(detail);
    } finally {
      setSaving(false);
    }
  };

  if (!projectBilling) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-lg" dir="rtl">
        <DialogHeader>
          <DialogTitle className="text-right">עריכת תמחור פרויקט</DialogTitle>
          <DialogDescription className="text-right text-sm text-slate-500">
            {projectBilling.project_name}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 mt-2">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">חבילת שירות</label>
            <div className="grid grid-cols-1 gap-2">
              {plans.map(plan => {
                const isSelected = selectedPlanId === plan.id;
                return (
                  <button
                    key={plan.id}
                    type="button"
                    onClick={() => setSelectedPlanId(plan.id)}
                    className={`w-full text-right p-3 rounded-lg border-2 transition-all ${
                      isSelected
                        ? 'border-amber-500 bg-amber-50'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm text-slate-800">{plan.label}</span>
                        {plan.badge && (
                          <span className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-amber-200 text-amber-800">
                            {plan.badge}
                          </span>
                        )}
                      </div>
                      {isSelected && <Check className="w-4 h-4 text-amber-600" />}
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{plan.shortDescription}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">כמות יחידות לחיוב</label>
            <input
              type="number"
              min={1}
              value={units}
              onChange={(e) => setUnits(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              dir="ltr"
            />
          </div>

          {preview && (
            <div className="bg-slate-50 rounded-lg p-3 space-y-2">
              <div className="text-xs text-slate-500 font-medium">הערכה בלבד — הסכום הסופי ייקבע לאחר שמירה</div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">עלות חבילה</span>
                <span className="font-medium text-slate-700">{formatCurrency(preview.projectFee)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">מדרגת יחידות ({preview.tierLabel})</span>
                <span className="font-medium text-slate-700">{formatCurrency(preview.tierFee)}</span>
              </div>
              <div className="border-t border-slate-200 pt-2 flex justify-between">
                <span className="text-sm font-medium text-slate-700">סה״כ חודשי (הערכה)</span>
                <span className="text-lg font-bold text-slate-900">{formatCurrency(preview.total)}</span>
              </div>
            </div>
          )}

          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
          >
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            שמור שינויים
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
