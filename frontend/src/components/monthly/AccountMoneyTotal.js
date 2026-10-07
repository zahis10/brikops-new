import React from 'react';

const money = (n) => `${new Intl.NumberFormat('he-IL', { maximumFractionDigits: 2 }).format(n ?? 0)} ₪`;

export default function AccountMoneyTotal({ contractor, account }) {
  if (!contractor.totals_money) return null;
  return (
    <div className="mt-3 flex items-baseline justify-between flex-wrap rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
      <span>לתשלום החודש</span>
      <span><b>{money(contractor.totals_money.this_month)}</b>{' '}
        <span className="text-[11px] text-amber-800">לפני מע״מ · לפני עכבון</span>
      </span>
      <div className="mt-0.5 w-full text-[11px] text-amber-800">מצטבר {money(contractor.totals_money.cumulative)}</div>
    </div>
  );
}
