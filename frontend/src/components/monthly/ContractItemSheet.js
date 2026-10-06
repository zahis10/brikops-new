import React, { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { MobileSelect } from '../ui/mobile-select';
import { contractItemsService } from '../../services/contractItemsService';

const UNITS = ['דירה', 'יח׳', 'קומפ׳', 'נק׳', 'מ״ר', 'מ״א', 'מ״ק', 'ק״ג', 'טון', 'ש״ע'];
const inputClass = 'min-h-[44px] w-full rounded-md border border-slate-200 px-3 py-2';
const overrides = (values) => {
  const entries = Object.entries(values || {}).filter(([, value]) => String(value).trim() !== '');
  return entries.length ? Object.fromEntries(entries.map(([tag, value]) => [tag, Number(value)])) : null;
};

export default function ContractItemSheet({ open, onOpenChange, projectId, contractor, stage, item, account, onSaved }) {
  const [data, setData] = useState(null);
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [retry, setRetry] = useState(0);
  const generation = useRef(0);
  const busy = useRef(false);
  const itemId = item?.item_id;
  const stageId = stage?.stage_id;
  const month = account.month;
  useEffect(() => {
    const token = ++generation.current;
    if (!open) return undefined;
    setLoading(true); setFailed(false); setData(null); setForm(null); setExpanded(false); setSaving(false);
    const load = async () => {
      try {
        const result = await contractItemsService.list(projectId);
        if (generation.current !== token) return;
        const raw = itemId ? (result.items || []).find((entry) => entry.id === itemId) : null;
        if (itemId && !raw) throw new Error('הסעיף לא נמצא');
        const unit = raw?.unit || (stageId ? 'דירה' : 'יח׳');
        const measurement = raw?.measurements?.[month];
        setForm({ code: raw?.code || '', description: raw?.description || '', qty: raw?.qty ?? 1,
          unit, customUnit: !UNITS.includes(unit), price: raw?.unit_price ?? '',
          quantities: { ...(raw?.qty_by_unit_type || {}) }, prices: { ...(raw?.price_by_unit_type || {}) },
          measuredQty: measurement?.qty ?? 0, note: measurement?.note || '' });
        setData(result);
      } catch (error) {
        if (generation.current === token) {
          setFailed(true);
          toast.error(error.response?.data?.detail || (error.message === 'הסעיף לא נמצא' ? 'הסעיף לא נמצא' : 'לא ניתן לטעון את הסעיף'));
        }
      } finally {
        if (generation.current === token) setLoading(false);
      }
    };
    load();
    return () => { generation.current += 1; };
  }, [open, projectId, itemId, stageId, month, retry]);
  const change = (key, value) => setForm((previous) => ({ ...previous, [key]: value }));
  const changeOverride = (key, tag, value) => setForm((previous) => ({
    ...previous, [key]: { ...previous[key], [tag]: value },
  }));
  const editable = account.status === 'open' && data?.can_write;
  const save = async () => {
    if (!form || !editable || busy.current) return;
    const qty = stage ? Number(form.qty) : 1;
    const price = String(form.price).trim() === '' ? null : Number(form.price);
    const quantities = stage ? overrides(form.quantities) : null;
    const prices = stage && price != null ? overrides(form.prices) : null;
    if (!form.description.trim() || form.description.trim().length > 120) return toast.error('נדרש תיאור לסעיף');
    if (!Number.isFinite(qty) || qty <= 0 || qty > 1000000 ||
      Object.values(quantities || {}).some((n) => !Number.isFinite(n) || n <= 0 || n > 1000000)) return toast.error('כמות לא תקינה');
    if ((price != null && (!Number.isFinite(price) || price < 0 || price > 10000000)) ||
      Object.values(prices || {}).some((n) => !Number.isFinite(n) || n < 0 || n > 10000000)) return toast.error('מחיר לא תקין');
    if (itemId && !stage && (!Number.isFinite(Number(form.measuredQty)) ||
      Number(form.measuredQty) < 0 || Number(form.measuredQty) > 1000000)) return toast.error('כמות לא תקינה');
    busy.current = true; setSaving(true);
    const token = generation.current;
    try {
      const body = { company_id: contractor.company_id, source: stage ? 'stage' : 'measured',
        stage_id: stageId ?? null, basis: 'unit', code: form.code.trim() || null,
        description: form.description.trim(), unit: form.unit.trim(), qty,
        qty_by_unit_type: quantities, unit_price: price, price_by_unit_type: prices };
      if (itemId) await contractItemsService.update(projectId, itemId, body);
      else await contractItemsService.create(projectId, body);
      if (itemId && !stage) await contractItemsService.setMeasurement(projectId, itemId, month, {
        qty: Number(form.measuredQty) || 0, note: form.note,
      });
      if (generation.current !== token) return;
      toast.success(itemId ? 'הסעיף עודכן' : 'הסעיף נוסף');
      onOpenChange(false); onSaved();
    } catch (error) {
      if (generation.current === token) toast.error(error.response?.data?.detail || 'לא ניתן לשמור את הסעיף');
    } finally {
      busy.current = false;
      if (generation.current === token) setSaving(false);
    }
  };
  const deactivate = async () => {
    if (!editable || busy.current || !window.confirm('להסיר את הסעיף מהחשבונות הבאים? חודשים שנסגרו לא משתנים.')) return;
    busy.current = true; setSaving(true);
    const token = generation.current;
    try {
      await contractItemsService.update(projectId, itemId, { active: false });
      if (generation.current !== token) return;
      toast.success('הסעיף עודכן'); onOpenChange(false); onSaved();
    } catch (error) {
      if (generation.current === token) toast.error(error.response?.data?.detail || 'לא ניתן לשמור את הסעיף');
    } finally {
      busy.current = false;
      if (generation.current === token) setSaving(false);
    }
  };
  const tags = data?.unit_type_tags || [];
  const scope = data?.stages?.find((entry) => entry.id === stageId)?.scope || stage?.scope;
  return (
    <Dialog open={open} onOpenChange={(next) => { if (!busy.current) onOpenChange(next); }}>
      <DialogContent dir="rtl" className="max-w-lg max-h-[90vh] overflow-y-auto text-right">
        <DialogHeader className="text-right">
          <DialogTitle>{item ? 'עריכת סעיף' : stage ? `סעיף לשלב ״${stage.title}״` : 'סעיף נמדד'}</DialogTitle>
          <DialogDescription className="text-right">{stage
            ? 'כל דירה שהשלב מסומן בה ״בוצע״ מוסיפה את הכמות לסעיף.'
            : 'הכמות מוקלדת כל חודש בכרטיס הקבלן. מה שלא במטריצה — נכנס לחשבון מכאן.'}</DialogDescription>
        </DialogHeader>
        {loading && <div role="status" aria-label="טוען סעיף" className="animate-pulse space-y-3">
          <div className="h-12 rounded-md bg-slate-100" /><div className="h-12 rounded-md bg-slate-100" />
          <div className="h-24 rounded-md bg-slate-100" />
        </div>}
        {!loading && failed && <button type="button" onClick={() => setRetry((value) => value + 1)}
          className="min-h-[44px] text-amber-700">נסה שוב</button>}
        {!loading && form && data && <form noValidate onSubmit={(event) => { event.preventDefault(); save(); }}>
          <fieldset disabled={saving || !editable} className="space-y-4 disabled:opacity-60">
            <label className="block text-sm">קוד הסעיף — כמו בחוזה / בפריוריטי (רשות)
              <input dir="ltr" maxLength={40} className={`${inputClass} font-mono`} value={form.code}
                onChange={(event) => change('code', event.target.value)} />
            </label>
            <label className="block text-sm">תיאור
              <input required maxLength={120} className={inputClass} value={form.description}
                onChange={(event) => change('description', event.target.value)} />
            </label>
            <div className="flex gap-3">
              {stage && <label className="min-w-0 flex-1 text-sm">כמות לדירה
                <input type="number" inputMode="decimal" step="any" min="0" className={inputClass}
                  value={form.qty} onChange={(event) => change('qty', event.target.value)} />
              </label>}
              <div className="min-w-0 flex-1 text-sm"><span>יחידה</span>
                <MobileSelect value={form.customUnit ? 'other' : form.unit}
                  options={[...UNITS.map((unit) => ({ value: unit, label: unit })), { value: 'other', label: 'אחר…' }]}
                  onChange={(event) => setForm((previous) => ({ ...previous,
                    customUnit: event.target.value === 'other', unit: event.target.value === 'other' ? '' : event.target.value }))} />
                {form.customUnit && <input aria-label="יחידה" maxLength={20} className={`${inputClass} mt-2`}
                  value={form.unit} onChange={(event) => change('unit', event.target.value)} />}
              </div>
            </div>
            <label className="block text-sm">מחיר ליחידה (רשות — רק אם החשבון נסגר ב-BrikOps)
              <div className="flex items-center gap-2"><input type="number" inputMode="decimal" min="0" step="any"
                className={inputClass} value={form.price} onChange={(event) => change('price', event.target.value)} /><span>₪</span></div>
            </label>
            {stage && scope === 'floor' && <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
              שלב קומתי — כאן הכמות היא לדירה. כמות לקומה (בטון, קומה יצוקה) מגיעה בשלב הבא.
            </p>}
            {stage && !!tags.length && <div>
              <button type="button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}
                className="min-h-[44px] text-sm text-slate-600">עוד אפשרויות ▾</button>
              {expanded && <table className="w-full text-xs"><thead><tr><th className="text-right">סוג דירה</th>
                <th>כמות לדירה</th>{String(form.price).trim() !== '' && <th>מחיר ליחידה</th>}</tr></thead>
                <tbody>{tags.map((tag) => <tr key={tag}><td>{tag}</td><td>
                  <input aria-label={`כמות ${tag}`} type="number" inputMode="decimal" min="0" step="any"
                    className={`${inputClass} min-w-0`} placeholder={String(form.qty)} value={form.quantities[tag] ?? ''}
                    onChange={(event) => changeOverride('quantities', tag, event.target.value)} />
                </td>{String(form.price).trim() !== '' && <td>
                  <input aria-label={`מחיר ${tag}`} type="number" inputMode="decimal" min="0" step="any"
                    className={`${inputClass} min-w-0`} placeholder={String(form.price)} value={form.prices[tag] ?? ''}
                    onChange={(event) => changeOverride('prices', tag, event.target.value)} />
                </td>}</tr>)}</tbody></table>}
            </div>}
            {itemId && !stage && account.status === 'open' && <section className="space-y-3 border-t border-slate-100 pt-3">
              <label className="block text-sm">כמות {account.label}<input type="number" inputMode="decimal" min="0" step="any"
                className={inputClass} value={form.measuredQty} onChange={(event) => change('measuredQty', event.target.value)} /></label>
              <label className="block text-sm">הערה (רשות)<input maxLength={300} className={inputClass}
                value={form.note} onChange={(event) => change('note', event.target.value)} /></label>
            </section>}
            <button type="submit" className="min-h-[44px] w-full rounded-lg bg-amber-500 font-bold text-white">שמור</button>
            {itemId && <button type="button" onClick={deactivate} className="min-h-[44px] text-sm text-slate-500">
              הסר מהחשבונות הבאים
            </button>}
          </fieldset>
        </form>}
      </DialogContent>
    </Dialog>
  );
}
