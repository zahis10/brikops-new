import React, { useMemo } from 'react';
import MatrixCell from './MatrixCell';

export default function MatrixListView({ units, stages, cells, floorsById, buildingsById }) {
  const cellsByUnitStage = useMemo(() => {
    const map = {};
    for (const c of cells) {
      const key = `${c.unit_id}::${c.stage_id}`;
      map[key] = c;
    }
    return map;
  }, [cells]);

  const progressForUnit = (unitId) => {
    let completed = 0;
    let total = 0;
    for (const stage of stages) {
      if (stage.type !== 'status') continue;
      total += 1;
      const c = cellsByUnitStage[`${unitId}::${stage.id}`];
      if (c?.status === 'completed' || c?.status === 'no_findings') {
        completed += 1;
      }
    }
    return { completed, total, pct: total ? Math.round((completed / total) * 100) : 0 };
  };

  if (!units || units.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500" dir="rtl">
        אין דירות בפרויקט
      </div>
    );
  }

  return (
    <div className="space-y-3" dir="rtl">
      {units.map((unit) => {
        const floor = floorsById[unit.floor_id];
        const { completed, total, pct } = progressForUnit(unit.id);
        return (
          <div
            key={unit.id}
            className="bg-white rounded-xl border border-slate-200 p-3"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 min-w-0">
                {(() => {
                  const building = buildingsById?.[unit.building_id];
                  if (!building) return null;
                  const badgeText =
                    building.sort_index != null
                      ? String(building.sort_index)
                      : (building.name || '?').trim().charAt(0) || '?';
                  return (
                    <span
                      className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-violet-50 text-violet-700 border border-violet-200 font-medium text-[10px] shrink-0"
                      title={building.name}
                    >
                      {badgeText}
                    </span>
                  );
                })()}
                <span className="text-sm font-bold text-slate-900 shrink-0">
                  דירה {unit.unit_no}
                </span>
                {floor && (
                  <span className="text-xs text-slate-500 truncate">
                    • קומה {floor.floor_number}
                    {unit.room_count != null && ` • ${unit.room_count} ח'`}
                  </span>
                )}
              </div>
              <span className="text-xs font-medium text-slate-600 shrink-0">
                {completed}/{total}
              </span>
            </div>

            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mb-3">
              <div
                className="h-full bg-emerald-500 transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>

            <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-1 px-1">
              {stages.map((stage) => {
                const cell = cellsByUnitStage[`${unit.id}::${stage.id}`];
                return (
                  <div key={stage.id} className="flex flex-col items-center shrink-0 w-12">
                    <MatrixCell cell={cell} stage={stage} size="sm" />
                    <span className="text-[9px] text-slate-500 mt-1 text-center leading-tight w-full truncate" title={stage.title}>
                      {stage.title}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
