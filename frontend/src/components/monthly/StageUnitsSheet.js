import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { matrixService } from '../../services/matrixService';

const compare = (a, b) => String(a ?? '').localeCompare(String(b ?? ''), 'he', { numeric: true });
const dayMonth = (date) => date ? `${Number(date.slice(8, 10))}.${Number(date.slice(5, 7))}` : '';

export default function StageUnitsSheet({ open, onOpenChange, projectId, stage, contractor, account, canWrite, onChanged }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [buildingId, setBuildingId] = useState(null);
  const [selected, setSelected] = useState(new Set());
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
  const toggle = (id) => {
    if (!editable || busy.current) return;
    setSelected((previous) => { const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  };
  const selectFloor = (floorUnits) => {
    if (!editable || busy.current) return;
    setSelected((previous) => new Set([...previous, ...floorUnits.filter(eligible).map((unit) => unit.id)]));
  };
  const chosen = units.filter((unit) => selected.has(unit.id) && eligible(unit));
  const save = async () => {
    if (!editable || busy.current || !chosen.length) return;
    busy.current = true; setSaving(true);
    const token = generation.current;
    let saved = 0;
    let failure = null;
    try {
      for (const unit of chosen) {
        try {
          await matrixService.updateCell(projectId, unit.id, stageId, { status: 'completed' });
          saved += 1;
          dirty.current = true;
        } catch (error) { failure = error; break; }
      }
      if (generation.current !== token) return;
      if (failure) toast.error(`${failure.response?.data?.detail || 'הסימון נכשל'} · נשמרו ${saved} דירות`);
      else toast.success(`סומנו ${saved} דירות — נרשם במטריצה`);
      if (saved > 0) {
        // Refresh only the sheet; the account refreshes once on close.
        setSelected(new Set());
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
          <div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{`${done} בוצעו · ${units.length - done} לא`}</span>
            {editable && <p className="mt-3 text-xs text-slate-600">דירה שתסמן כאן נרשמת במטריצה כסימון ידני (מי ומתי) ונכנסת לחשבון של {account.label}.</p>}
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
                  return <div key={unit.id} className="flex min-h-[44px] items-center justify-between gap-3 border-b border-slate-100 py-2 text-xs">
                    <label className="flex items-center gap-2 text-slate-700">
                      {completed ? <span className="text-emerald-600" aria-label="בוצע">✓</span> :
                        !irrelevant && (editable ? <input type="checkbox" checked={selected.has(unit.id)} disabled={saving}
                          onChange={() => toggle(unit.id)} className="h-4 w-4 accent-amber-500" /> : <span className="h-4 w-4 rounded border border-slate-300" />)}
                      דירה {unit.unit_no}
                    </label>
                    <span className={completed ? 'text-emerald-700' : 'text-slate-500'}>
                      {completed ? `בוצע ${dayMonth(cell.last_updated_at)} · ${cell.synced_from_qc ? 'בקרת ביצוע' : 'סימון ידני'}` : irrelevant ? 'לא רלוונטי' : 'לא בוצע'}
                    </span>
                  </div>;
                })}
              </section>;
            })}
          </div>
          {editable && <button type="button" onClick={save} disabled={!chosen.length || saving}
            className="min-h-[44px] w-full rounded-lg bg-amber-500 font-bold text-white disabled:opacity-50">{`סמן ${chosen.length} דירות כבוצע במטריצה`}</button>}
        </>}
        <button type="button" disabled={saving} onClick={() => { if (!busy.current) { changeOpen(false); navigate(`/projects/${projectId}/execution-matrix`); } }}
          className="min-h-[44px] text-sm text-amber-700 disabled:opacity-50">לפתוח את המטריצה המלאה ›</button>
      </DialogContent>
    </Dialog>
  );
}
