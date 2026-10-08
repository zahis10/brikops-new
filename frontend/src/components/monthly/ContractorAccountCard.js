import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Download, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import ContractItemsRows from './ContractItemsRows';
import AccountMoneyTotal from './AccountMoneyTotal';
import AccountAddSheet from './AccountAddSheet';
import StageUnitsSheet from './StageUnitsSheet';
import ContractItemSheet from './ContractItemSheet';

const MONTHS = ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר'];
const label = (month) => month === 'baseline' ? 'לפני החשבון הראשון ב-BrikOps' :
  month && /^\d{4}-(0[1-9]|1[0-2])$/.test(month) ? `${MONTHS[Number(month.slice(5)) - 1]} ${month.slice(0, 4)}` : '';
// Dates arrive already formatted in Israel on the server; do not parse through a browser timezone.
const dayMonth = (date) => date ? `${Number(date.slice(8, 10))}.${Number(date.slice(5, 7))}` : '';

export default function ContractorAccountCard({ contractor, month, projectId, canExport, onExport, canWrite = false, onChanged = () => {} }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [expanded, setExpanded] = useState((canWrite && month.status === 'open') || (contractor.totals?.this_month || 0) > 0 || !!contractor.corrections?.length);
  const [fullStages, setFullStages] = useState({});
  const [exporting, setExporting] = useState(false);
  const [adding, setAdding] = useState(false);
  const [unitsStage, setUnitsStage] = useState(null);
  const [create, setCreate] = useState(null);
  const rows = contractor.stages || [];
  const corrections = contractor.corrections || [];
  const cumulative = contractor.totals?.cumulative ?? rows.reduce((sum, stage) => sum + (stage.cumulative || 0), 0);
  const exportFile = async () => {
    setExporting(true);
    try {
      await onExport(contractor.company_id);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'לא ניתן לייצא את הדוח');
    } finally {
      setExporting(false);
    }
  };
  const openEvidence = (evidence, stage) => {
    const path = evidence.source === 'qc' && evidence.qc_run_id && evidence.floor_id
      ? `/projects/${projectId}/floors/${evidence.floor_id}/qc/${evidence.qc_run_id}/stage/${stage.stage_id}?unitId=${evidence.unit_id}`
      : `/projects/${projectId}/execution-matrix`;
    const returnTo = encodeURIComponent(location.pathname + location.search);
    navigate(`${path}${path.includes('?') ? '&' : '?'}returnTo=${returnTo}`);
  };
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <button type="button" onClick={() => setExpanded((value) => !value)}
        className="flex min-h-[44px] w-full items-center justify-between gap-2 text-right">
        <span className="flex items-center gap-2 font-bold text-slate-900">
          {contractor.name} <ChevronDown className={`h-4 w-4 text-slate-400 ${expanded ? 'rotate-180' : ''}`} />
        </span>
        <span className={`rounded-full px-2 py-1 text-xs font-bold ${contractor.totals?.this_month ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>
          {expanded || contractor.totals?.this_month ? `החודש ${contractor.totals?.this_month || 0}` : `מצטבר ${cumulative}`}
        </span>
      </button>
      {expanded && <>
        {rows.map((stage) => (
          <section key={stage.stage_id} className="border-t border-slate-100 py-4">
            <div className="flex flex-wrap items-center justify-between gap-1 text-sm">
              <button type="button" onClick={() => setUnitsStage(stage)} className="font-bold text-amber-800 underline decoration-dotted underline-offset-4 text-right">{stage.title} ›</button>
              <span className="text-slate-600">החודש <b>{stage.this_month}</b> · מצטבר {stage.cumulative}/{stage.total_units}</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
              {!!stage.qc_count && <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-800">{stage.qc_count} אושרו בבקרת ביצוע</span>}
              {!!stage.manual_count && <span className="rounded-full bg-amber-50 px-2 py-1 text-amber-800">{stage.manual_count} סומנו ידנית</span>}
              <span className="text-slate-500">{stage.pct}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-emerald-500" style={{ width: `${Math.max(0, Math.min(stage.pct || 0, 100))}%` }} />
            </div>
            <ContractItemsRows contractor={contractor} stage={stage} account={month} projectId={projectId} canWrite={canWrite} onChanged={onChanged} />
            {!!stage.evidence?.length && <div className="mt-3 rounded-lg bg-slate-50 p-2 text-xs">
              <div className={fullStages[stage.stage_id] ? 'max-h-60 space-y-2 overflow-y-auto' : 'space-y-2'}>
                {(fullStages[stage.stage_id] ? stage.evidence : stage.evidence.slice(0, 3)).map((evidence, index) => (
                  <button type="button" key={`${evidence.unit_id}-${index}`} onClick={() => openEvidence(evidence, stage)}
                    className="block w-full rounded p-1 text-right hover:bg-slate-100">
                    דירה {evidence.unit_no} · {dayMonth(evidence.completed_date_il)} · {evidence.actor_name}
                    <span className={`mr-2 rounded px-1.5 py-0.5 ${evidence.source === 'qc' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                      {evidence.source === 'qc' ? 'בקרת ביצוע' : 'סימון ידני'}
                    </span>
                    {evidence.late_from_month && <span className="text-slate-500"> · אחרי סגירת {label(evidence.late_from_month)}</span>}
                  </button>
                ))}
              </div>
              {stage.evidence.length > 3 && <button type="button"
                onClick={() => setFullStages((previous) => ({ ...previous, [stage.stage_id]: !previous[stage.stage_id] }))}
                className="mt-2 font-semibold text-amber-700">
                {fullStages[stage.stage_id] ? 'הצג פחות' : `עוד ${stage.evidence.length - 3} ›`}
              </button>}
            </div>}
          </section>
        ))}
        <ContractItemsRows contractor={contractor} stage={null} account={month} projectId={projectId} canWrite={canWrite} onChanged={onChanged} />
        {canWrite && month.status === 'open' && <button type="button" onClick={() => setAdding(true)} className="mt-3 min-h-[44px] w-full rounded-xl border border-dashed border-amber-300 bg-white font-bold text-amber-700">+ הוספה לחשבון</button>}
        {corrections.map((correction, index) => (
          <div key={`${correction.stage_id}-${correction.unit_id}-${index}`}
            className="my-2 rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-900">
            ⚠ תיקון: −1 · דירה {correction.unit_no} נפתחה מחדש בבקרת הביצוע ({correction.counted_in_month === 'baseline'
              ? 'נספרה לפני החשבון הראשון ב-BrikOps' : `נספרה ב-${label(correction.counted_in_month)}`})
          </div>
        ))}
        <AccountMoneyTotal contractor={contractor} account={month} />
        {canExport && <button type="button" onClick={exportFile} disabled={exporting}
          className="mt-3 flex min-h-[44px] w-full items-center justify-center gap-2 rounded-lg border border-slate-200 text-sm font-semibold text-slate-700 disabled:opacity-50">
          <Download className="h-4 w-4" />
          {exporting ? 'מייצא…' : `אקסל — ${contractor.name} · ${month.label}`}
        </button>}
        <AccountAddSheet open={adding} onOpenChange={setAdding} contractor={contractor} onUnits={(s) => setUnitsStage(s)} onTerms={(s) => setCreate({ stage: s })} onMeasured={() => setCreate({ stage: null })} />
        {unitsStage && <StageUnitsSheet open onOpenChange={(o) => { if (!o) setUnitsStage(null); }} projectId={projectId} stage={unitsStage} contractor={contractor} account={month} canWrite={canWrite} onChanged={onChanged} />}
        {create && <ContractItemSheet open onOpenChange={(o) => { if (!o) setCreate(null); }} projectId={projectId} contractor={contractor} stage={create.stage} item={null} account={month} onSaved={onChanged} />}
      </>}
    </article>
  );
}