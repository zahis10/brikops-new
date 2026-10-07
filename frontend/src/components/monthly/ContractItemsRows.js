import React, { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { contractItemsService } from '../../services/contractItemsService';
import ContractItemSheet from './ContractItemSheet';

const fmt = (n) => new Intl.NumberFormat('he-IL', { maximumFractionDigits: 2 }).format(n ?? 0);
const money = (n) => `${fmt(n)} ₪`;
const dayMonth = (date) => date ? `${Number(date.slice(8, 10))}.${Number(date.slice(5, 7))}` : '';

function ItemRow({ line, editable, projectId, account, onChanged, onEdit }) {
  const [value, setValue] = useState(String(line.this_month_qty ?? 0));
  const [saving, setSaving] = useState(false);
  const pending = useRef(false);
  const saved = useRef(String(line.this_month_qty ?? 0));
  const alive = useRef(true);
  const measured = line.source === 'measured';
  useEffect(() => {
    saved.current = String(line.this_month_qty ?? 0);
    setValue(saved.current);
  }, [line.this_month_qty, account.month]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const saveQuantity = async () => {
    if (!editable || pending.current || Number(value || 0) === Number(saved.current)) return;
    const qty = Number(value || 0);
    if (!Number.isFinite(qty) || qty < 0 || qty > 1000000) {
      toast.error('כמות לא תקינה');
      return;
    }
    pending.current = true;
    setSaving(true);
    try {
      await contractItemsService.setMeasurement(projectId, line.item_id, account.month, {
        qty, note: line.measurement?.note || '',
      });
      if (!alive.current) return;
      saved.current = String(qty);
      toast.success('הכמות נשמרה');
      onChanged();
    } catch (error) {
      if (alive.current) toast.error(error.response?.data?.detail || 'לא ניתן לשמור את הכמות');
    } finally {
      pending.current = false;
      if (alive.current) setSaving(false);
    }
  };
  return (
    <div role={editable ? 'button' : undefined} tabIndex={editable ? 0 : undefined}
      onClick={editable ? () => { if (!pending.current) onEdit(line); } : undefined}
      onKeyDown={editable ? (event) => {
        if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault();
          if (!pending.current) onEdit(line);
        }
      } : undefined}
      className={`rounded-lg bg-slate-50 border border-slate-100 px-2.5 py-1.5 text-xs mt-1.5 ${editable ? 'cursor-pointer' : ''}`}>
      <div className="flex items-center gap-2">
        <span className="font-mono font-bold" dir="ltr">{line.code || '—'}</span>
        <span className="flex-1 truncate text-slate-700">{line.description}</span>
        <span className="text-slate-500" dir={measured ? undefined : 'ltr'}>{measured ? line.unit : `×${fmt(line.qty)}`}</span>
        <span className="tabular-nums whitespace-nowrap">
          {measured && editable ? <input type="number" inputMode="decimal" min="0" step="any"
            value={value} disabled={saving} aria-label="כמות החודש"
            className="w-16 rounded-md border border-amber-200 px-1.5 py-1 text-center font-bold disabled:opacity-50"
            onClick={(event) => event.stopPropagation()} onChange={(event) => setValue(event.target.value)}
            onBlur={saveQuantity} onKeyDown={(event) => {
              event.stopPropagation();
              if (event.key === 'Enter') { event.preventDefault(); event.currentTarget.blur(); }
            }} /> : <b>{fmt(line.this_month_qty)}</b>}
          {line.corrections ? ` (−${line.corrections})` : ''} · {fmt(line.cumulative_qty)} {line.unit}
        </span>
      </div>
      {line.unit_price != null && <div className="flex justify-between text-[11px] text-slate-500 mt-0.5">
        <span>{money(line.unit_price)} ל{line.unit}{line.price_by_unit_type ? ' · לפי סוג דירה' : ''}</span>
        <span><b>{money(line.this_month_amount)}</b> החודש · {money(line.cumulative_amount)} מצטבר</span>
      </div>}
      {measured && <div className="flex justify-between text-[11px] text-slate-500 mt-0.5">
        <span>{line.measurement ? `הוקלד ${dayMonth(line.measurement.at)} · ${line.measurement.by?.name || ''}` : 'לא הוקלד החודש = 0'}</span>
        {editable && <span>✎ הערה</span>}
      </div>}
    </div>
  );
}

export default function ContractItemsRows({ contractor, stage, account, projectId, canWrite, onChanged }) {
  const [open, setOpen] = useState(false);
  const [item, setItem] = useState(null);
  const editable = canWrite && account.status === 'open';
  const lines = (contractor.items || []).filter((line) => stage
    ? line.source === 'stage' && line.stage_id === stage.stage_id : line.source === 'measured');
  const edit = (line = null) => { setItem(line); setOpen(true); };
  if (!lines.length && !editable) return null;
  const addText = stage
    ? (lines.length ? '+ סעיף' : contractor.has_items ? 'בלי סעיף — נכנס לחשבון כ״דירות״ · + סעיף' : '+ סעיף')
    : (lines.length ? '+ סעיף נמדד' : '+ סעיף נמדד · למה שלא במטריצה');
  return (
    <div className={!stage && lines.length ? 'mt-3 border-t border-slate-100 pt-3' : ''}>
      {!stage && !!lines.length && <h3 className="text-xs font-bold text-slate-700">
        נמדד ידנית <span className="font-normal text-slate-500">· מקלידים כל חודש</span>
      </h3>}
      {lines.map((line) => <ItemRow key={line.item_id} line={line} editable={editable}
        projectId={projectId} account={account} onChanged={onChanged} onEdit={edit} />)}
      {editable && <button type="button" onClick={() => edit()}
        className="min-h-[44px] text-amber-700 font-bold text-xs">{addText}</button>}
      <ContractItemSheet open={open && editable} onOpenChange={setOpen} projectId={projectId}
        contractor={contractor} stage={stage} item={item} account={account} onSaved={onChanged} />
    </div>
  );
}
