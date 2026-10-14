import React, { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { MobileSelect } from '../ui/mobile-select';
import { contractItemsService } from '../../services/contractItemsService';

const UNITS = ['קומה', 'יח׳', 'נק׳', 'מ״ר', 'מ״א', 'מ״ק', 'קומפ׳', 'ק״ג', 'טון', 'ש״ע'];
const fmt = (n) => new Intl.NumberFormat('he-IL', { maximumFractionDigits: 2 }).format(n ?? 0);
const money = (n) => `${fmt(n)} ₪`;
const lump = (line) => line.unit === 'דירה' && Number(line.qty) === 1 && line.unit_price != null;
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
  const [createdId, setCreatedId] = useState(null);
  const generation = useRef(0);
  const busy = useRef(false);
  const itemId = item?.item_id;
  const stageId = stage?.stage_id;
  const month = account.month;
  useEffect(() => {
    const token = ++generation.current;
    if (!open) return undefined;
    setLoading(true); setFailed(false); setData(null); setForm(null); setExpanded(false); setSaving(false);
    setCreatedId(null);
    const load = async () => {
      try {
        const result = await contractItemsService.list(projectId);
        if (generation.current !== token) return;
        const raw = itemId ? (result.items || []).find((entry) => entry.id === itemId) : null;
        if (itemId && !raw) throw new Error('התשלום לא נמצא');
        const mode = raw ? (raw.basis === 'floor' ? 'floor' : lump(raw) ? 'fixed' : 'qty')
          : stageId == null ? 'qty' : result.stages?.find((entry) => entry.id === stageId)?.scope === 'floor' ? 'floor' : 'fixed';
        const unit = raw?.unit || (mode === 'floor' ? 'קומה' : mode === 'fixed' ? 'דירה' : stageId != null ? 'יח׳' : 'מ״א');
        const measurement = raw?.measurements?.[month];
        setForm({ mode, code: raw?.code || '', description: raw?.description || '', qty: raw?.qty ?? 1,
          unit, customUnit: !UNITS.includes(unit), price: raw?.unit_price ?? '',
          quantities: { ...(raw?.qty_by_unit_type || {}) }, prices: { ...(raw?.price_by_unit_type || {}) },
          floorQuantities: { ...(raw?.qty_by_floor || {}) }, floorPrices: { ...(raw?.price_by_floor || {}) },
          measuredQty: measurement?.qty ?? 0, note: measurement?.note || '' });
        setData(result);
      } catch (error) {
        if (generation.current === token) {
          setFailed(true);
          toast.error(error.response?.data?.detail || (error.message === 'התשלום לא נמצא' ? 'התשלום לא נמצא' : 'לא ניתן לטעון את התשלום'));
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
    const fixed = !!stage && form.mode === 'fixed';
    const byFloor = !!stage && form.mode === 'floor';
    const qty = stage && !fixed ? Number(form.qty) : 1;
    const price = String(form.price).trim() === '' ? null : Number(form.price);
    const quantities = stage && !fixed ? overrides(byFloor ? form.floorQuantities : form.quantities) : null;
    const prices = stage && price != null ? overrides(byFloor ? form.floorPrices : form.prices) : null;
    const description = byFloor ? form.description.trim() || stage.title : form.description.trim();
    if (fixed && (price == null || !Number.isFinite(price) || price < 0 || price > 10000000)) return toast.error('כמה ₪ לדירה?');
    if (!fixed && (!description || description.length > 120)) return toast.error(byFloor ? 'מה משלמים לקומה?' : stage ? 'מה סופרים?' : 'מה מודדים?');
    if (!Number.isFinite(qty) || qty <= 0 || qty > 1000000 ||
      Object.values(quantities || {}).some((n) => !Number.isFinite(n) || n <= 0 || n > 1000000)) return toast.error('כמות לא תקינה');
    if ((price != null && (!Number.isFinite(price) || price < 0 || price > 10000000)) ||
      Object.values(prices || {}).some((n) => !Number.isFinite(n) || n < 0 || n > 10000000)) return toast.error('מחיר לא תקין');
    if (!stage && (!Number.isFinite(Number(form.measuredQty)) ||
      Number(form.measuredQty) < 0 || Number(form.measuredQty) > 1000000)) return toast.error('כמות לא תקינה');
    busy.current = true; setSaving(true);
    const token = generation.current;
    try {
      const body = { company_id: contractor.company_id, source: stage ? 'stage' : 'measured',
        stage_id: stageId ?? null, basis: byFloor ? 'floor' : 'unit', code: form.code.trim() || null,
        description: fixed ? stage.title : description, unit: fixed ? 'דירה' : form.unit.trim(), qty,
        qty_by_unit_type: byFloor ? null : quantities, unit_price: price, price_by_unit_type: byFloor ? null : prices,
        ...(byFloor ? { qty_by_floor: quantities, price_by_floor: prices } : {}) };
      if (itemId) await contractItemsService.update(projectId, itemId, body);
      else {
        let id = createdId;
        if (!id) { const created = await contractItemsService.create(projectId, body); id = created.id; setCreatedId(id); }
        if (!stage && Number(form.measuredQty) > 0) await contractItemsService.setMeasurement(projectId, id, month, {
          qty: Number(form.measuredQty), note: form.note,
        });
      }
      if (itemId && !stage) await contractItemsService.setMeasurement(projectId, itemId, month, {
        qty: Number(form.measuredQty) || 0, note: form.note,
      });
      if (generation.current !== token) return;
      toast.success('נשמר');
      onOpenChange(false); onSaved();
    } catch (error) {
      if (generation.current === token) toast.error(error.response?.data?.detail || 'לא ניתן לשמור');
    } finally {
      busy.current = false;
      if (generation.current === token) setSaving(false);
    }
  };
  const deactivate = async () => {
    if (!editable || busy.current || !window.confirm('להסיר את התשלום הזה מהחשבונות הבאים? חודשים שנסגרו לא משתנים.')) return;
    busy.current = true; setSaving(true);
    const token = generation.current;
    try {
      await contractItemsService.update(projectId, itemId, { active: false });
      if (generation.current !== token) return;
      toast.success('נשמר'); onOpenChange(false); onSaved();
    } catch (error) {
      if (generation.current === token) toast.error(error.response?.data?.detail || 'לא ניתן לשמור');
    } finally {
      busy.current = false;
      if (generation.current === token) setSaving(false);
    }
  };
  const tags = data?.unit_type_tags || [];
  const scope = data?.stages?.find((entry) => entry.id === stageId)?.scope || stage?.scope;
  const fixed = !!stage && form?.mode === 'fixed';
  const byFloor = !!stage && form?.mode === 'floor';
  const n = stage?.this_month || 0, price = Number(form?.price) || 0, qty = Number(form?.qty) || 0;
  const typeTable = stage && !byFloor && !!tags.length && form && <div className="space-y-2">
    {fixed && <p className="text-sm">סכום שונה לפי סוג דירה</p>}
    <table className="w-full text-xs"><thead><tr><th className="text-right">סוג דירה</th>
      {!fixed && <th>כמות לדירה</th>}{(fixed || String(form.price).trim() !== '') && <th>{fixed ? 'כמה ₪ לדירה' : 'מחיר ליחידה'}</th>}
    </tr></thead><tbody>{tags.map((tag) => <tr key={tag}><td>{tag}</td>
      {!fixed && <td><input aria-label={`כמות ${tag}`} type="number" inputMode="decimal" min="0" step="any"
        className={`${inputClass} min-w-0`} placeholder={String(form.qty)} value={form.quantities[tag] ?? ''}
        onChange={(event) => changeOverride('quantities', tag, event.target.value)} /></td>}
      {(fixed || String(form.price).trim() !== '') && <td><input aria-label={`מחיר ${tag}`} type="number" inputMode="decimal" min="0" step="any"
        className={`${inputClass} min-w-0`} placeholder={String(form.price)} value={form.prices[tag] ?? ''}
        onChange={(event) => changeOverride('prices', tag, event.target.value)} /></td>}
    </tr>)}</tbody></table></div>;
  const floorTable = byFloor && form && <div className="space-y-2">
    <p className="text-sm">חריגי קומות</p>
    <table className="w-full text-xs"><thead><tr><th className="text-right">קומה</th>
      <th>כמות בקומה</th>{String(form.price).trim() !== '' && <th>מחיר</th>}
    </tr></thead><tbody>{(data?.floors || []).map((floor) => <tr key={floor.id}>
      <td>{floor.building_name} · קומה {floor.floor_number}</td>
      <td><input aria-label={`כמות ${floor.building_name} קומה ${floor.floor_number}`} type="number" inputMode="decimal" min="0" step="any"
        className={`${inputClass} min-w-0`} placeholder={String(form.qty)} value={form.floorQuantities[floor.id] ?? ''}
        onChange={(event) => changeOverride('floorQuantities', floor.id, event.target.value)} /></td>
      {String(form.price).trim() !== '' && <td><input aria-label={`מחיר ${floor.building_name} קומה ${floor.floor_number}`} type="number" inputMode="decimal" min="0" step="any"
        className={`${inputClass} min-w-0`} placeholder={String(form.price)} value={form.floorPrices[floor.id] ?? ''}
        onChange={(event) => changeOverride('floorPrices', floor.id, event.target.value)} /></td>}
    </tr>)}</tbody></table></div>;
  return (
    <Dialog open={open} onOpenChange={(next) => { if (!busy.current) onOpenChange(next); }}>
      <DialogContent dir="rtl" className="max-w-lg max-h-[90vh] overflow-y-auto text-right">
        <DialogHeader className="text-right">
          <DialogTitle>{stage ? `מה משלמים על ״${stage.title}״?` : 'עבודה שמודדים בשטח'}</DialogTitle>
          <DialogDescription className="text-right">{stage
            ? `על כל דירה שהשלב מסומן בה ״בוצע״, ${contractor.name} מקבל:`
            : 'עבודה שלא מסומנת במטריצה. כל חודש מקלידים כמה בוצע — והקבלן מקבל לפי זה.'}</DialogDescription>
        </DialogHeader>
        {loading && <div role="status" aria-label="טוען תשלום" className="animate-pulse space-y-3">
          <div className="h-12 rounded-md bg-slate-100" /><div className="h-12 rounded-md bg-slate-100" />
          <div className="h-24 rounded-md bg-slate-100" />
        </div>}
        {!loading && failed && <button type="button" onClick={() => setRetry((value) => value + 1)}
          className="min-h-[44px] text-amber-700">נסה שוב</button>}
        {!loading && form && data && <form noValidate onSubmit={(event) => { event.preventDefault(); save(); }}>
          <fieldset disabled={saving || !editable} className="space-y-4 disabled:opacity-60">
            {stage && <div role="tablist" aria-label="איך משלמים" className="flex rounded-lg bg-slate-100 p-0.5">
              {['fixed', 'qty', 'floor'].map((mode) => <button key={mode} type="button" role="tab" aria-selected={form.mode === mode}
                disabled={!!itemId} title={itemId ? 'אי אפשר לשנות את הבסיס — צור תשלום חדש' : undefined}
                className={`min-h-[44px] flex-1 rounded-md text-sm ${form.mode === mode ? 'bg-white shadow-sm font-bold' : 'text-slate-600'}`}
                onClick={() => setForm((previous) => ({ ...previous, mode,
                  ...(mode === 'floor' && ['דירה', 'יח׳'].includes(previous.unit) ? { unit: 'קומה', qty: 1, customUnit: false }
                    : mode !== 'floor' && (previous.mode === 'floor' || (mode === 'qty' && previous.mode === 'fixed')) ? { unit: 'יח׳', customUnit: false } : {}) }))}>
                {mode === 'fixed' ? 'סכום קבוע לדירה' : mode === 'floor' ? 'לפי קומה' : 'לפי כמות'}
              </button>)}</div>}
            {fixed ? <>
              <label className="block text-sm">כמה ₪ לדירה
                <div className="flex items-center gap-2"><input autoFocus type="number" inputMode="decimal" min="0" step="any"
                  className={`${inputClass} text-xl font-bold`} value={form.price} onChange={(event) => change('price', event.target.value)} /><span>₪</span></div>
              </label>
              <p className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900">
                {n > 0 ? `דוגמה: ${n} דירות שבוצעו החודש × ${money(price)} = ${money(n * price)} לחשבון של ${account.label}`
                  : `כל דירה שתסומן ״בוצע״ ב${account.label} × ${money(price)} — נכנסת לחשבון לבד.`}
              </p>
              <div><button type="button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}
                className="min-h-[44px] text-sm text-slate-600">עוד אפשרויות ▾</button>
                {expanded && <div className="space-y-3">{typeTable}
                  <label className="block text-sm">קוד הסעיף בכתב הכמויות / בפריוריטי (רשות)
                    <input dir="ltr" maxLength={40} className={`${inputClass} font-mono`} value={form.code}
                      onChange={(event) => change('code', event.target.value)} />
                  </label>
                </div>}
              </div>
            </> : <>
              <label className="block text-sm">{byFloor ? 'מה משלמים לקומה?' : stage ? 'מה סופרים?' : 'מה מודדים?'}
                <input required maxLength={120} className={inputClass} value={form.description}
                  placeholder={byFloor ? `למשל: ${stage.title}` : stage ? 'למשל: נקודות חשמל, מ״ר ריצוף' : 'למשל: קירות תמך, חפירה ופינוי'}
                  onChange={(event) => change('description', event.target.value)} />
              </label>
              <div className="flex gap-3">
                {stage && <label className="min-w-0 flex-1 text-sm">{byFloor ? 'כמה בקומה אחת' : 'כמה בדירה אחת'}
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
              <label className="block text-sm">{stage && !byFloor ? 'מחיר ליחידה (רשות — אם החשבון נסגר כאן ולא בפריוריטי)' : 'מחיר ליחידה (רשות)'}
                <div className="flex items-center gap-2"><input type="number" inputMode="decimal" min="0" step="any"
                  className={inputClass} value={form.price} onChange={(event) => change('price', event.target.value)} /><span>₪</span></div>
              </label>
              {stage && <p className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900">
                {byFloor ? `דוגמה: 3 קומות × ${fmt(qty)} ${form.unit}${price ? ` × ${money(price)} = ${money(3 * qty * price)}` : ''} — קומה נספרת לפי חלק הדירות שבוצעו בה`
                  : `דוגמה: ${n || 'למשל 12'} דירות × ${qty} = ${fmt((n || 12) * qty)} ${form.unit} החודש${price ? ` × ${money(price)} = ${money((n || 12) * qty * price)}` : ''}`}
              </p>}
              <div><button type="button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}
                className="min-h-[44px] text-sm text-slate-600">עוד אפשרויות ▾</button>
                {expanded && <div className="space-y-3">
                  <label className="block text-sm">קוד הסעיף בכתב הכמויות / בפריוריטי (רשות)
                    <input dir="ltr" maxLength={40} className={`${inputClass} font-mono`} value={form.code}
                      onChange={(event) => change('code', event.target.value)} />
                  </label>{byFloor ? floorTable : typeTable}
                </div>}
              </div>
            </>}
            {stage && scope === 'floor' && !byFloor && <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
              שלב קומתי: אפשר גם ״לפי קומה״ — קומה יצוקה, בטון לפי קומה.
            </p>}
            {!stage && account.status === 'open' && <section className="space-y-3 border-t border-slate-100 pt-3">
              <label className="block text-sm">כמה בוצע ב{account.label}<input type="number" inputMode="decimal" min="0" step="any"
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
