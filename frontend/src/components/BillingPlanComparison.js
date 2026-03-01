import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { getPlanCatalog, getAllPlanCatalog } from '../utils/billingPlanCatalog';
import { formatCurrency } from '../utils/billingLabels';

export default function BillingPlanComparison({ plans, onLoadPlans, plansLoading }) {
  const [open, setOpen] = useState(false);

  const handleToggle = () => {
    if (!open && (!plans || plans.length === 0) && onLoadPlans) {
      onLoadPlans();
    }
    setOpen(!open);
  };

  const catalogEntries = getAllPlanCatalog();

  const getPlanFee = (planId) => {
    if (!plans || plans.length === 0) return null;
    const p = plans.find(pl => pl.id === planId);
    return p ? p.project_fee_monthly : null;
  };

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <button
        onClick={handleToggle}
        className="w-full flex items-center justify-between px-3 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
      >
        <span>השוואת חבילות</span>
        {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {open && (
        <div className="border-t border-slate-200 p-3 space-y-3">
          {plansLoading ? (
            <div className="text-xs text-slate-400 py-4 text-center">טוען חבילות...</div>
          ) : (
            catalogEntries.map(cat => {
              const fee = getPlanFee(cat.id);
              const isPro = cat.id === 'plan_pro';
              return (
                <div
                  key={cat.id}
                  className={`rounded-lg p-3 space-y-1.5 ${
                    isPro
                      ? 'border-2 border-amber-300 bg-amber-50/50'
                      : 'border border-slate-200 bg-white'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`font-semibold text-sm ${isPro ? 'text-amber-800' : 'text-slate-700'}`}>
                      {cat.label}
                    </span>
                    {cat.badge && (
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        isPro ? 'bg-amber-200 text-amber-800' : 'bg-slate-200 text-slate-600'
                      }`}>
                        {cat.badge}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500">{cat.bestFor}</div>
                  {fee != null && (
                    <div className="text-sm font-bold text-slate-800">
                      {formatCurrency(fee)}<span className="text-xs font-normal text-slate-500">/חודש (עלות חבילה)</span>
                    </div>
                  )}
                </div>
              );
            })
          )}
          <div className="text-xs text-slate-400 text-center">
            המחיר הסופי כולל גם עלות מדרגת יחידות לפי ההסכם
          </div>
        </div>
      )}
    </div>
  );
}
