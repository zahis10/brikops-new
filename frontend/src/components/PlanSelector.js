import React from 'react';
import { Check, Crown, Building2 } from 'lucide-react';

export default function PlanSelector({ plans, onSelect, currentPlan, loading, selectedPlan }) {
  if (!plans) return null;

  const founder = plans.founder;
  const standard = plans.standard;
  const founderAvailable = founder?.available;
  const founderReason = founder?.reason;

  const reasonText = {
    slots_full: 'התוכנית מלאה',
    too_many_projects: 'מוגבלת לפרויקט אחד',
    disabled: 'התוכנית אינה זמינה',
  };

  const isCurrentFounder = currentPlan === 'founder_6m';
  const isCurrentStandard = currentPlan === 'standard';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <button
        type="button"
        disabled={!founderAvailable || isCurrentFounder || loading}
        onClick={() => onSelect?.('founder')}
        className={`relative text-right rounded-xl border-2 p-4 transition-all ${
          selectedPlan === 'founder'
            ? 'border-amber-500 bg-amber-50 shadow-md'
            : founderAvailable && !isCurrentFounder
              ? 'border-slate-200 bg-white hover:border-amber-300 hover:shadow-sm'
              : 'border-slate-100 bg-slate-50 opacity-60 cursor-not-allowed'
        }`}
      >
        {isCurrentFounder && (
          <span className="absolute top-2 left-2 text-[10px] bg-amber-500 text-white px-2 py-0.5 rounded-full font-medium">
            התוכנית הנוכחית שלך
          </span>
        )}
        <div className="flex items-center gap-2 mb-2">
          <Crown className="w-5 h-5 text-amber-500" />
          <span className="font-bold text-slate-800">תוכנית מייסדים</span>
        </div>
        <div className="text-lg font-bold text-slate-900 mb-1">₪500<span className="text-sm font-normal text-slate-500">/חודש × 6 חודשים</span></div>
        <div className="text-xs text-slate-500 mb-2">פרויקט אחד, כל הפיצ׳רים</div>
        {founder?.slots_remaining != null && (
          <div className="text-xs text-amber-700 bg-amber-100 rounded px-2 py-1 inline-block">
            נשארו {founder.slots_remaining} מקומות
          </div>
        )}
        {!founderAvailable && founderReason && (
          <div className="text-xs text-red-600 mt-1">{reasonText[founderReason] || 'לא זמין'}</div>
        )}
        {selectedPlan === 'founder' && (
          <div className="absolute top-2 left-2">
            <Check className="w-5 h-5 text-amber-600" />
          </div>
        )}
      </button>

      <button
        type="button"
        disabled={isCurrentStandard || loading}
        onClick={() => onSelect?.('standard')}
        className={`relative text-right rounded-xl border-2 p-4 transition-all ${
          selectedPlan === 'standard'
            ? 'border-emerald-500 bg-emerald-50 shadow-md'
            : !isCurrentStandard
              ? 'border-slate-200 bg-white hover:border-emerald-300 hover:shadow-sm'
              : 'border-slate-100 bg-slate-50 opacity-60 cursor-not-allowed'
        }`}
      >
        {isCurrentStandard && (
          <span className="absolute top-2 left-2 text-[10px] bg-emerald-500 text-white px-2 py-0.5 rounded-full font-medium">
            התוכנית הנוכחית שלך
          </span>
        )}
        <div className="flex items-center gap-2 mb-2">
          <Building2 className="w-5 h-5 text-emerald-500" />
          <span className="font-bold text-slate-800">תוכנית רגילה</span>
        </div>
        <div className="text-lg font-bold text-slate-900 mb-1">₪900<span className="text-sm font-normal text-slate-500"> רישיון + ₪20/יחידה לחודש</span></div>
        <div className="text-xs text-slate-500 mb-2">ללא הגבלת פרויקטים ויחידות</div>
        {selectedPlan === 'standard' && (
          <div className="absolute top-2 left-2">
            <Check className="w-5 h-5 text-emerald-600" />
          </div>
        )}
      </button>
    </div>
  );
}
