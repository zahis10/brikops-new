import React, { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { contractItemsService } from '../../services/contractItemsService';
import ContractItemSheet from './ContractItemSheet';

const fmt = (n) => new Intl.NumberFormat('he-IL', { maximumFractionDigits: 2 }).format(n ?? 0);
const money = (n) => `${fmt(n)} ₪`;
const lump = (line) => line.unit === 'דירה' && Number(line.qty) === 1 && line.unit_price != null;
const dayMonth = (date) => date ? `${Number(date.slice(8, 10))}.${Number(date.slice(5, 7))}` : '';

function ItemRow({ line, editable, projectId, account, onChanged, onEdit }) {
  const [value, setValue] = useState(String(line.this_month_qty ?? 0));
  const [saving, setSaving] = useState(false);
  const pending = useRef(false);
  const saved = useRef(String(line.this_month_qty ?? 0));
  const alive = useRef(true);
  const measured = line.source === 'measured';
  const fixed = !measured && lump(line);
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
      <div className="text-slate-700">
        {fixed ? <><b>{money(line.unit_price)} לדירה</b>{line.price_by_unit_type ? ' · לפי סוג דירה' : ''}</>
          : <><b>{line.description}</b> · {measured ? line.unit : `${fmt(line.qty)} לדירה`}
            {line.unit_price != null ? ` · ${money(line.unit_price)} ל${line.unit}` : ''}</>}
      </div>
      <div className="mt-0.5 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-slate-500">
        <span className="tabular-nums">
          החודש {fixed ? `${line.units_this_month ?? 0} דירות` :
          <>
          {measured && editable ? <input type="number" inputMode="decimal" min="0" step="any"
            value={value} disabled={saving} aria-label="כמות החודש"
            className="w-16 rounded-md border border-amber-200 px-1.5 py-1 text-center font-bold disabled:opacity-50"
            onClick={(event) => event.stopPropagation()} onChange={(event) => setValue(event.target.value)}
            onBlur={saveQuantity} onKeyDown={(event) => {
              event.stopPropagation();
              if (event.key === 'Enter') { event.preventDefault(); event.currentTarget.blur(); }
            }} /> : <b>{fmt(line.this_month_qty)}</b>} {line.unit}
          </>}
          {!measured && line.corrections ? ` (−${line.corrections})` : ''}
        </span>
        <span className="tabular-nums">
          {line.unit_price != null ? <><b>{money(line.this_month_amount)}</b> · מצטבר {money(line.cumulative_amount)}</>
            : <>מצטבר {fmt(line.cumulative_qty)}{measured ? ` ${line.unit}` : ''}</>}
          {!measured && !fixed && line.unit_price == null && line.code && <> · <span dir="ltr" className="font-mono">{line.code}</span></>}
        </span>
      </div>
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
  const edit = (line) => { setItem(line); setOpen(true); };
  if (!lines.length) return stage && editable ? <p className="text-xs text-slate-500">עוד לא הוגדר מה משלמים על השלב — נספר כדירות</p> : null;
  return <div className={!stage ? 'mt-3 border-t border-slate-100 pt-3' : ''}>{!stage && <h3 className="text-xs font-bold text-slate-700">עבודות שמודדים בשטח <span className="font-normal text-slate-500">· לא במטריצה</span></h3>}{lines.map((line) => <ItemRow key={line.item_id} line={line} editable={editable} projectId={projectId} account={account} onChanged={onChanged} onEdit={edit} />)}<ContractItemSheet open={open && editable} onOpenChange={setOpen} projectId={projectId} contractor={contractor} stage={stage} item={item} account={account} onSaved={onChanged} /></div>;
}
