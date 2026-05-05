import React, { useMemo } from 'react';
import MatrixCell from './MatrixCell';

export default function MatrixGridView({ units, stages, cells, floorsById, buildingsById, onCellClick = null }) {
  const cellsByUnitStage = useMemo(() => {
    const map = {};
    for (const c of cells) {
      const key = `${c.unit_id}::${c.stage_id}`;
      map[key] = c;
    }
    return map;
  }, [cells]);

  if (!units || units.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500" dir="rtl">
        אין דירות בפרויקט
      </div>
    );
  }

  return (
    <div
      className="bg-white rounded-xl border border-slate-200 overflow-auto max-h-[70vh]"
      dir="rtl"
    >
      <table className="border-collapse w-full" style={{ direction: 'rtl' }}>
        <thead className="sticky top-0 z-10 bg-slate-50 border-b border-slate-200">
          <tr>
            <th className="sticky right-0 z-30 bg-slate-50 border-l border-slate-200 px-3 py-2 text-right text-xs font-medium text-slate-700 min-w-[120px] w-[120px]">
              בניין
            </th>
            <th className="sticky right-[120px] z-20 bg-slate-50 border-l border-slate-200 px-3 py-2 text-right text-xs font-medium text-slate-700 min-w-[120px]">
              דירה
            </th>
            {stages.map((stage) => (
              <th
                key={stage.id}
                className="px-2 py-2 text-center text-[11px] font-medium text-slate-700 min-w-[64px] border-l border-slate-100 last:border-l-0"
                title={stage.title}
              >
                <div className="truncate max-w-[80px] mx-auto">{stage.title}</div>
                {stage.source === 'custom' && (
                  <div className="text-[9px] text-violet-600 mt-0.5">מותאם</div>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {units.map((unit, idx) => {
            const floor = floorsById[unit.floor_id];
            return (
              <tr key={unit.id} className={idx % 2 ? 'bg-slate-50/30' : 'bg-white'}>
                <td className="sticky right-0 z-20 bg-inherit border-l border-slate-200 px-3 py-2 text-right text-xs">
                  {(() => {
                    const building = buildingsById?.[unit.building_id];
                    const name = building?.name || '—';
                    return (
                      <span
                        className="inline-block max-w-full truncate px-2 py-1 rounded-md bg-violet-50 text-violet-700 border border-violet-200 font-medium text-[11px] leading-tight"
                        title={name}
                      >
                        {name}
                      </span>
                    );
                  })()}
                </td>
                <td className="sticky right-[120px] z-10 bg-inherit border-l border-slate-200 px-3 py-2 text-right text-xs">
                  <div className="font-medium text-slate-900">דירה {unit.unit_no}</div>
                  {floor && (
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      קומה {floor.floor_number}
                    </div>
                  )}
                </td>
                {stages.map((stage) => {
                  const cell = cellsByUnitStage[`${unit.id}::${stage.id}`];
                  return (
                    <td key={stage.id} className="p-1.5 border-l border-slate-100 last:border-l-0 text-center">
                      <div className="inline-flex">
                        <MatrixCell
                          cell={cell}
                          stage={stage}
                          size="md"
                          onClick={onCellClick ? () => onCellClick(unit, stage, cell) : null}
                        />
                      </div>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
