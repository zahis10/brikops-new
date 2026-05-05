import React, { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import MatrixCell from './MatrixCell';

export default function MatrixListView({ units, stages, cells, floorsById, buildingsById, onCellClick = null }) {
  const cellsByUnitStage = useMemo(() => {
    const map = {};
    for (const c of cells) {
      const key = `${c.unit_id}::${c.stage_id}`;
      map[key] = c;
    }
    return map;
  }, [cells]);

  // #490 — per-unit expanded state. Default all collapsed. Multiple
  // units may be expanded simultaneously (useful for comparing 2-3).
  const [expandedUnits, setExpandedUnits] = useState(new Set());
  const toggleUnit = (unitId) => {
    setExpandedUnits((prev) => {
      const next = new Set(prev);
      if (next.has(unitId)) next.delete(unitId);
      else next.add(unitId);
      return next;
    });
  };

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
        const isExpanded = expandedUnits.has(unit.id);
        return (
          <div
            key={unit.id}
            className="bg-white rounded-xl border border-slate-200 overflow-hidden"
          >
            {/* Header — entire row is the tap target (≥56px). */}
            <button
              type="button"
              onClick={() => toggleUnit(unit.id)}
              className="w-full px-3 py-3 hover:bg-slate-50 active:bg-slate-100 transition-colors text-right"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 min-w-0">
                  {(() => {
                    const building = buildingsById?.[unit.building_id];
                    if (!building) return null;
                    return (
                      <span
                        className="inline-flex items-center px-2 py-0.5 rounded-md bg-violet-50 text-violet-700 border border-violet-200 font-medium text-[11px] shrink-0 max-w-[120px] truncate"
                        title={building.name}
                      >
                        {building.name}
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
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs font-medium text-slate-600">
                    {completed}/{total}
                  </span>
                  {isExpanded
                    ? <ChevronUp className="w-4 h-4 text-slate-400" />
                    : <ChevronDown className="w-4 h-4 text-slate-400" />}
                </div>
              </div>

              {/* Progress bar — visible in both collapsed + expanded states. */}
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </button>

            {/* Expanded body — vertical stage list, full names, 32×32 icons. */}
            {isExpanded && (
              <div className="border-t border-slate-100 px-3 py-2">
                {stages.map((stage, idx) => {
                  const cell = cellsByUnitStage[`${unit.id}::${stage.id}`];
                  return (
                    <div
                      key={stage.id}
                      className={`flex items-center justify-between gap-3 py-3 ${
                        idx < stages.length - 1 ? 'border-b border-slate-50' : ''
                      }`}
                    >
                      <span className="text-[13px] text-slate-700 leading-snug min-w-0 flex-1">
                        {stage.title}
                      </span>
                      <div className="shrink-0">
                        <MatrixCell
                          cell={cell}
                          stage={stage}
                          size="sm"
                          onClick={onCellClick ? () => onCellClick(unit, stage, cell) : null}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
