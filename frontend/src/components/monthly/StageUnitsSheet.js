import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { matrixService } from '../../services/matrixService';

const compare = (a, b) => String(a ?? '').localeCompare(String(b ?? ''), 'he', { numeric: true });
const dayMonth = (date) => date ? `${Number(date.slice(8, 10))}.${Number(date.slice(5, 7))}` : '';
const PICKS = [25, 50, 75];
const livePct = (cell) => cell && !['completed', 'not_done', 'not_relevant'].includes(cell.status) && cell.progress_pct > 0 && cell.progress_pct < 100 ? cell.progress_pct : 0;

export default function StageUnitsSheet({ open, onOpenChange, projectId, stage, contractor, account, canWrite, onChanged }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [buildingId, setBuildingId] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [partial, setPartial] = useState(new Map());
  const [picker, setPicker] = useState(null);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const generation = useRef(0);
  const busy = useRef(false);
  const dirty = useRef(false);
  const changeOpen = (next) => {
    if (busy.current) return;
    onOpenChange(next);
    if (!next && dirty.current) { dirty.current = false; onChanged(); }
  };
  const stageId = stage.stage_id;
  const load = useCallback(async () => {
    const token = ++generation.current;
    setLoading(true); setFailed(false); setData(null); setSelected(new Set());
    setPartial(new Map()); setPicker(null); setDraft('');
    try {
      const result = await matrixService.getMatrix(projectId);
      if (generation.current !== token) return;
      const buildings = [...(result.buildings || [])].sort((a, b) => compare(a.name, b.name) || compare(a.id, b.id));
      setData(result);
      setBuildingId((current) => buildings.some((building) => building.id === current) ? current : buildings[0]?.id ?? null);
    } catch (error) {
      if (generation.current === token) {
        setFailed(true);
        toast.error(error.response?.data?.detail || 'לא ניתן לטעון את הדירות');
      }
    } finally {
      if (generation.current === token) setLoading(false);
    }
  }, [projectId]);
  useEffect(() => {
    if (open) { setBuildingId(null); load(); }
    return () => { generation.current += 1; };
  }, [open, stageId, load]);
  const editable = !!(canWrite && account.status === 'open' && data?.permissions?.can_edit);
  const buildings = [...(data?.buildings || [])].sort((a, b) => compare(a.name, b.name) || compare(a.id, b.id));
  const floors = [...(data?.floors || [])].sort((a, b) => compare(a.floor_number, b.floor_number) || compare(a.id, b.id));
  const cells = new Map((data?.cells || []).filter((cell) => cell.stage_id === stageId).map((cell) => [cell.unit_id, cell]));
  const buildingOrder = new Map(buildings.map((building, index) => [building.id, index]));
  const floorOrder = new Map(floors.map((floor, index) => [floor.id, index]));
  const units = [...(data?.units || [])].sort((a, b) =>
    (buildingOrder.get(a.building_id) ?? -1) - (buildingOrder.get(b.building_id) ?? -1) ||
    (floorOrder.get(a.floor_id) ?? -1) - (floorOrder.get(b.floor_id) ?? -1) ||
    compare(a.unit_no, b.unit_no) || compare(a.id, b.id));
  const eligible = (unit) => !['completed', 'not_relevant'].includes(cells.get(unit.id)?.status);
  const done = units.filter((unit) => cells.get(unit.id)?.status === 'completed').length;
  const partialCount = units.filter((unit) => livePct(cells.get(unit.id))).length;
  const toggle = (id) => {
    if (!editable || busy.current) return;
    setPartial((previous) => { const next = new Map(previous); next.delete(id); return next; });
    setSelected((previous) => { const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  };
  const selectFloor = (floorUnits) => {
    if (!editable || busy.current) return;
    setPartial((previous) => { const next = new Map(previous); floorUnits.filter(eligible).forEach((unit) => next.delete(unit.id)); return next; });
    setSelected((previous) => new Set([...previous, ...floorUnits.filter(eligible).map((unit) => unit.id)]));
  };
  const openPicker = (id) => {
    if (!editable || busy.current) return;
    setPicker(id); setDraft(String(partial.get(id) || livePct(cells.get(id)) || ''));
  };
  const pick = (id, pct) => {
    if (!editable || busy.current) return;
    if (!Number.isInteger(pct) || pct < 1 || pct > 99) { toast.error('אחוז בין 1 ל-99'); return; }
    setPartial((previous) => new Map(previous).set(id, pct));
    setSelected((previous) => { const next = new Set(previous); next.delete(id); return next; });
    setPicker(null); setDraft('');
  };
  const chosen = units.filter((unit) => eligible(unit) && (selected.has(unit.id) || (partial.has(unit.id) && partial.get(unit.id) !== livePct(cells.get(unit.id)))));
  const full = chosen.filter((unit) => selected.has(unit.id)).length;
  const part = chosen.length - full;
  const save = async () => {
    if (!editable || busy.current || !chosen.length) return;
    busy.current = true; setSaving(true);
    const token = generation.current;
    let saved = 0;
    let failure = null;
    try {
      for (const unit of chosen) {
        try {
          const cell = cells.get(unit.id);
          const body = selected.has(unit.id)
            ? { status: 'completed', note: cell?.note ?? null }
            : { status: 'partial', progress_pct: partial.get(unit.id), note: cell?.note ?? null };
          await matrixService.updateCell(projectId, unit.id, stageId, body);
          saved += 1;
          dirty.current = true;
        } catch (error) { failure = error; break; }
      }
      if (generation.current !== token) return;
      if (failure) toast.error(`${failure.response?.data?.detail || 'הסימון נכשל'} · נשמרו ${saved} דירות`);
      else toast.success(`סומנו ${saved} דירות — נרשם במטריצה`);
      if (saved > 0) {
        // Refresh only the sheet; the account refreshes once on close.
        setSelected(new Set()); setPartial(new Map());
        await load();
      }
    } finally {
      busy.current = false;
      setSaving(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent dir="rtl" className="max-w-lg max-h-[90vh] overflow-y-auto text-right" aria-describedby={undefined}>
        <DialogHeader className="text-right"><DialogTitle>{stage.title}</DialogTitle></DialogHeader>
        {loading && <div role="status" aria-label="טוען דירות" className="animate-pulse space-y-3">
          <div className="h-8 rounded-lg bg-slate-100" /><div className="h-12 rounded-lg bg-slate-100" /><div className="h-12 rounded-lg bg-slate-100" />
        </div>}
        {!loading && failed && <button type="button" disabled={saving} onClick={() => { if (!busy.current) load(); }}
          className="min-h-[44px] text-amber-700">נסה שוב</button>}
        {!loading && data && <>
          <div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{`${done} בוצעו · ${partialCount} חלקי · ${units.length - done - partialCount} לא`}</span>
            {editable && <p className="mt-3 text-xs text-slate-600">✓ = בוצע, 100% מהמחיר לדירה. חלקי = משחררים חלק עכשיו — נרשם במטריצה ״חלקי N%״ (מי ומתי), וההמשך כשהדירה תסומן ״בוצע״.</p>}
          </div>
          {buildings.length > 1 && <div className="flex flex-wrap gap-2">
            {buildings.map((building) => <button key={building.id} type="button" disabled={saving} aria-pressed={buildingId === building.id}
              onClick={() => { if (!busy.current) setBuildingId(building.id); }}
              className={`min-h-[44px] rounded-full border px-3 text-sm ${buildingId === building.id ? 'border-amber-300 bg-amber-50 text-amber-800' : 'border-slate-200 text-slate-600'}`}>{building.name}</button>)}
          </div>}
          {!units.length && <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">אין דירות להצגה</p>}
          <div className="space-y-4" aria-label={`דירות בשלבי ${contractor.name}`}>
            {floors.filter((floor) => floor.building_id === buildingId).map((floor) => {
              const floorUnits = units.filter((unit) => unit.floor_id === floor.id && unit.building_id === buildingId);
              return <section key={floor.id}>
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-bold text-slate-700">קומה {floor.floor_number}</h3>
                  {editable && <button type="button" disabled={saving || !floorUnits.some(eligible)} onClick={() => selectFloor(floorUnits)}
                    className="min-h-[44px] text-xs text-amber-700 disabled:opacity-50">סמן את כל הקומה</button>}
                </div>
                {floorUnits.map((unit) => {
                  const cell = cells.get(unit.id);
                  const completed = cell?.status === 'completed';
                  const irrelevant = cell?.status === 'not_relevant';
                  return <React.Fragment key={unit.id}><div className="flex min-h-[44px] items-center justify-between gap-3 border-b border-slate-100 py-2 text-xs">
                    <label className="flex items-center gap-2 text-slate-700">
                      {completed ? <span className="text-emerald-600" aria-label="בוצע">✓</span> :
                        !irrelevant && (editable ? <input type="checkbox" checked={selected.has(unit.id)} disabled={saving}
                          onChange={() => toggle(unit.id)} className="h-4 w-4 accent-amber-500" /> : <span className="h-4 w-4 rounded border border-slate-300" />)}
                      דירה {unit.unit_no}
                    </label>
                    <span className="flex items-center gap-2">
                      {completed ? <span className="text-emerald-700">{`בוצע ${dayMonth(cell.last_updated_at)} · ${cell.synced_from_qc ? 'בקרת ביצוע' : 'סימון ידני'}`}</span> :
                        irrelevant ? <span className="text-slate-500">לא רלוונטי</span> : <>
                          {partial.has(unit.id) ? <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 font-bold text-amber-800">◔ {partial.get(unit.id)}%</span> :
                            livePct(cell) ? <><span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 font-bold text-amber-800">◔ חלקי {livePct(cell)}%</span>
                              <span className="text-slate-500">{dayMonth(cell.last_updated_at)} · {cell.last_actor_name || ''}</span></> :
                              <span className="text-slate-500">{cell?.status === 'partial' ? 'חלקי — בלי אחוז' : 'לא בוצע'}</span>}
                          {editable && <button type="button" disabled={saving} onClick={() => openPicker(unit.id)} className="min-h-[44px] text-amber-700 disabled:opacity-50">
                            {partial.has(unit.id) || livePct(cell) ? 'שנה' : 'חלקי %'}</button>}
                        </>}
                    </span>
                  </div>
                    {editable && !completed && !irrelevant && picker === unit.id && <div className="mr-7 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs">
                      <p className="mb-2 font-bold">כמה לשחרר על דירה {unit.unit_no}?</p>
                      <div className="flex flex-wrap items-center gap-2">
                        {PICKS.map((pct) => <button key={pct} type="button" disabled={saving} onClick={() => pick(unit.id, pct)}
                          className="min-h-[36px] rounded-full border border-amber-200 bg-white px-3 font-bold text-amber-800">{pct}%</button>)}
                        <input type="number" inputMode="numeric" min="1" max="99" value={draft} disabled={saving} onChange={(event) => setDraft(event.target.value)} placeholder="אחר" aria-label="אחוז לשחרור"
                          className="w-16 rounded-lg border border-amber-200 px-2 py-1 text-center font-bold" /> %
                        <button type="button" disabled={saving} onClick={() => pick(unit.id, Number(draft))} className="min-h-[36px] font-bold text-amber-800">אישור</button>
                        <button type="button" disabled={saving} onClick={() => { if (!busy.current) setPicker(null); }} className="min-h-[36px] text-slate-500">ביטול</button>
                        {partial.has(unit.id) && <button type="button" disabled={saving} onClick={() => {
                          if (busy.current) return;
                          setPartial((previous) => { const next = new Map(previous); next.delete(unit.id); return next; }); setPicker(null); setDraft('');
                        }} className="min-h-[36px] text-slate-500">הסר</button>}
                      </div>
                    </div>}
                  </React.Fragment>;
                })}
              </section>;
            })}
          </div>
        </>}
        {!loading && data && <div className="sticky bottom-0 -mx-6 -mb-6 border-t border-slate-100 bg-white px-6 py-2">
          {!!chosen.length && <p className="mb-2 text-xs text-slate-500">{`נבחרו ${chosen.length} דירות: ${full} בוצע · ${part} חלקי`}</p>}
          {editable && <button type="button" onClick={save} disabled={!chosen.length || saving}
            className="min-h-[48px] w-full rounded-lg bg-amber-500 font-bold text-white disabled:opacity-50">
            {chosen.length ? `סמן ${chosen.length} דירות במטריצה` : 'בחר דירות ברשימה כדי לסמן'}</button>}
          <button type="button" disabled={saving} onClick={() => { if (!busy.current) { changeOpen(false); navigate(`/projects/${projectId}/execution-matrix`); } }}
            className="min-h-[44px] w-full text-sm text-amber-700 disabled:opacity-50">לפתוח את המטריצה המלאה ›</button>
        </div>}
      </DialogContent>
    </Dialog>
  );
}
