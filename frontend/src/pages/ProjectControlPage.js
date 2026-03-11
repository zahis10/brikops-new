import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactDOM from 'react-dom';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  projectService, buildingService, floorService, membershipService,
  projectCompanyService, teamInviteService, projectStatsService, excelService, tradeService,
  sortIndexService, versionService, configService, archiveService, stepupService, isStepupError, billingService,
  qcService
} from '../services/api';
import { toast } from 'sonner';
import { formatUnitLabel } from '../utils/formatters';
import { qcFloorStatusLabel } from '../utils/qcLabels';
import QCApproversTab from '../components/QCApproversTab';
import ProjectBillingCard from '../components/ProjectBillingCard';
import {
  X, ChevronDown, ChevronRight, ChevronUp, Loader2, Building2, Layers, DoorOpen,
  Plus, ArrowRight, Users, Briefcase, AlertTriangle, Settings, Phone, Send, MessageSquare,
  RotateCcw, XCircle, Trash2, Edit3, Download, Upload, Eye, BarChart3, Search, FileText,
  Zap, Check, Archive, Undo2, ClipboardCheck, CreditCard
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { tTrade, tRole, tSubRole, t } from '../i18n';
import ProjectSwitcher from '../components/ProjectSwitcher';
import NotificationBell from '../components/NotificationBell';
import UserDrawer from '../components/UserDrawer';
import { MoreVertical } from 'lucide-react';

const normalizeList = (data) => {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  if (data && typeof data === 'object') {
    const arrKey = Object.keys(data).find(k => Array.isArray(data[k]));
    if (arrKey) return data[arrKey];
  }
  return [];
};

const STATUS_BADGES = {
  active: { label: 'פעיל', className: 'bg-green-100 text-green-700' },
  draft: { label: 'טיוטה', className: 'bg-slate-100 text-slate-600' },
  suspended: { label: 'מושהה', className: 'bg-red-100 text-red-700' },
  completed: { label: 'הושלם', className: 'bg-blue-100 text-blue-700' },
};


const KIND_LABELS = {
  residential: 'מגורים',
  technical: 'טכנית',
  service: 'שירות',
  roof: 'גג',
  basement: 'מרתף',
  ground: 'קרקע',
  parking: 'חניה',
  commercial: 'מסחרי',
};

const KIND_COLORS = {
  residential: 'bg-emerald-100 text-emerald-700',
  technical: 'bg-gray-100 text-gray-700',
  service: 'bg-purple-100 text-purple-700',
  roof: 'bg-sky-100 text-sky-700',
  basement: 'bg-stone-100 text-stone-700',
  ground: 'bg-lime-100 text-lime-700',
  parking: 'bg-cyan-100 text-cyan-700',
  commercial: 'bg-orange-100 text-orange-700',
};

const SECONDARY_TABS = [
  { id: 'team', label: 'צוות' },
  { id: 'companies', label: 'חברות' },
  { id: 'settings', label: 'מאשרי QC' },
];

const BILLING_TAB = { id: 'billing', label: 'חיוב' };

const BottomSheetModal = ({ open, onClose, title, children }) => {
  if (!open) return null;
  return ReactDOM.createPortal(
    <div className="fixed inset-0 z-[9998] flex items-end sm:items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" />
      <div
        className="relative w-full max-w-lg bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl max-h-[85vh] flex flex-col"
        dir="rtl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <h3 className="text-lg font-bold text-slate-800">{title}</h3>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded-full">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>
        <div className="p-4 overflow-y-auto flex-1 space-y-4">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
};

const OptionsOverlay = ({ open, options, value, onChange, onClose, label, emptyMessage }) => {
  if (!open) return null;
  return ReactDOM.createPortal(
    <div className="fixed inset-0 z-[9999] flex items-end justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" />
      <div className="relative w-full max-w-lg bg-white rounded-t-2xl shadow-2xl max-h-[60vh] flex flex-col" dir="rtl" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <span className="font-bold text-slate-800">{label || 'בחר'}</span>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded-full"><X className="w-5 h-5" /></button>
        </div>
        <div className="overflow-y-auto flex-1 p-2">
          {options.length === 0 ? (
            <p className="text-center text-slate-400 py-6">{emptyMessage || 'אין אפשרויות'}</p>
          ) : options.map(opt => (
            <button key={opt.value} onClick={() => { onChange(opt.value); onClose(); }}
              className={`w-full text-right p-3 rounded-lg mb-1 transition-colors ${value === opt.value ? 'bg-amber-100 text-amber-800 font-bold' : 'hover:bg-slate-100 text-slate-700'}`}>
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    </div>,
    document.body
  );
};

const SelectField = ({ label, value, options, onChange, error, emptyMessage }) => {
  const [open, setOpen] = useState(false);
  const selected = options.find(o => o.value === value);
  return (
    <div className="space-y-1">
      {label && <label className="block text-sm font-medium text-slate-700">{label}</label>}
      <button type="button" onClick={() => setOpen(true)}
        className={`w-full flex items-center justify-between px-3 py-2.5 border rounded-lg text-sm ${error ? 'border-red-400' : 'border-slate-300'} bg-white`}>
        <span className={selected ? 'text-slate-800' : 'text-slate-400'}>{selected ? selected.label : 'בחר...'}</span>
        <ChevronDown className="w-4 h-4 text-slate-400" />
      </button>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <OptionsOverlay open={open} options={options} value={value} onChange={onChange} onClose={() => setOpen(false)} label={label} emptyMessage={emptyMessage} />
    </div>
  );
};

const InputField = ({ label, value, onChange, placeholder, error, type = 'text', dir = 'rtl', onFocus, inputMode }) => (
  <div className="space-y-1" dir={dir}>
    {label && <label className="block text-sm font-medium text-slate-700">{label}</label>}
    <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
      onFocus={onFocus} inputMode={inputMode}
      className={`w-full px-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500 ${error ? 'border-red-400' : 'border-slate-300'}`} />
    {error && <p className="text-xs text-red-500">{error}</p>}
  </div>
);

const KpiRow = ({ stats }) => {
  if (!stats) return null;
  const items = [
    { label: 'בניינים', value: stats.buildings, color: 'text-amber-600' },
    { label: 'קומות', value: stats.floors, color: 'text-blue-600' },
    { label: 'דירות', value: stats.units, color: 'text-green-600' },
    { label: 'ליקויים פתוחים', value: stats.open_defects, color: 'text-red-600' },
  ];
  return (
    <div className="flex gap-2">
      {items.map(item => (
        <div key={item.label} className="flex-1 bg-white rounded-lg border border-slate-100 py-2 px-1 text-center">
          <p className={`text-base font-bold ${item.color}`}>{item.value ?? 0}</p>
          <p className="text-[10px] text-slate-400 leading-tight">{item.label}</p>
        </div>
      ))}
    </div>
  );
};

const AddBuildingForm = ({ projectId, onClose, onSuccess }) => {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  const handleSubmit = async () => {
    const errs = {};
    if (!name.trim()) errs.name = 'חובה';
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;
    setSubmitting(true);
    try {
      await projectService.createBuilding(projectId, { project_id: projectId, name: name.trim(), code: code.trim() || undefined });
      toast.success('בניין נוצר בהצלחה');
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת בניין');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BottomSheetModal open onClose={onClose} title="הוסף בניין">
      <InputField label="שם בניין *" value={name} onChange={setName} placeholder="למשל: בניין A" error={errors.name} />
      <InputField label="קוד בניין" value={code} onChange={setCode} placeholder="למשל: A" />
      <Button onClick={handleSubmit} disabled={submitting} className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 rounded-lg">
        {submitting ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />יוצר...</span> : 'צור בניין'}
      </Button>
    </BottomSheetModal>
  );
};

const QuickSetupWizard = ({ projectId, onClose, onSuccess }) => {
  const [step, setStep] = useState(1);
  const [buildingName, setBuildingName] = useState('');
  const [buildingCode, setBuildingCode] = useState('');
  const [fromFloor, setFromFloor] = useState('0');
  const [toFloor, setToFloor] = useState('');
  const [defaultUnits, setDefaultUnits] = useState('4');
  const [exceptions, setExceptions] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});
  const [result, setResult] = useState(null);

  const floorCount = fromFloor !== '' && toFloor !== '' ? Math.max(0, Number(toFloor) - Number(fromFloor) + 1) : 0;

  const parseUnitsStr = (s) => { const n = parseInt(s, 10); return isNaN(n) ? 0 : n; };

  const floorsList = [];
  if (fromFloor !== '' && toFloor !== '') {
    for (let i = Number(fromFloor); i <= Number(toFloor); i++) {
      const exc = exceptions.find(e => e.floor === i);
      floorsList.push({ floor: i, units: exc ? parseUnitsStr(exc.units) : parseUnitsStr(defaultUnits) });
    }
  }
  const totalUnits = floorsList.reduce((sum, f) => sum + f.units, 0);
  const floorsWithoutUnits = floorsList.filter(f => f.units === 0).length;

  const handleUnitsChange = (setter) => (val) => {
    const raw = String(val).replace(/[^0-9]/g, '');
    if (raw === '') { setter(''); return; }
    const num = parseInt(raw, 10);
    setter(String(Math.min(num, 50)));
  };

  const handleUnitsFocus = (e) => { e.target.select(); };

  const addException = () => {
    const from = Number(fromFloor);
    const to = Number(toFloor);
    const existingFloors = new Set(exceptions.map(e => e.floor));
    let nextFloor = from;
    for (let i = from; i <= to; i++) {
      if (!existingFloors.has(i)) { nextFloor = i; break; }
    }
    setExceptions(prev => [...prev, { floor: nextFloor, units: '' }]);
  };

  const updateException = (idx, field, value) => {
    const raw = String(value).replace(/[^0-9-]/g, '');
    if (field === 'floor') {
      if (raw === '' || raw === '-') {
        setExceptions(prev => prev.map((e, i) => i === idx ? { ...e, floor: raw } : e));
        return;
      }
      const from = Number(fromFloor);
      const to = Number(toFloor);
      const clamped = Math.max(from, Math.min(to, parseInt(raw, 10)));
      setExceptions(prev => prev.map((e, i) => i === idx ? { ...e, floor: clamped } : e));
    } else {
      const cleaned = String(value).replace(/[^0-9]/g, '');
      if (cleaned === '') {
        setExceptions(prev => prev.map((e, i) => i === idx ? { ...e, units: '' } : e));
        return;
      }
      const parsed = parseInt(cleaned, 10);
      const val = isNaN(parsed) ? '' : String(Math.min(parsed, 50));
      setExceptions(prev => prev.map((e, i) => i === idx ? { ...e, units: val } : e));
    }
  };

  const removeException = (idx) => {
    setExceptions(prev => prev.filter((_, i) => i !== idx));
  };

  const validateStep = () => {
    const errs = {};
    if (step === 1) {
      if (!buildingName.trim()) errs.buildingName = 'חובה';
    } else if (step === 2) {
      if (fromFloor === '') errs.fromFloor = 'חובה';
      if (toFloor === '') errs.toFloor = 'חובה';
      if (fromFloor !== '' && toFloor !== '' && Number(toFloor) < Number(fromFloor)) errs.toFloor = 'חייב להיות גדול מ-"מקומה"';
      if (floorCount > 100) errs.toFloor = 'מקסימום 100 קומות';
    } else if (step === 3) {
      const defVal = defaultUnits.trim();
      if (defVal === '' || isNaN(parseInt(defVal, 10))) { errs.defaultUnits = 'יש להזין מספר'; }
      else if (parseInt(defVal, 10) < 0 || parseInt(defVal, 10) > 50) { errs.defaultUnits = 'בין 0 ל-50'; }
      const from = Number(fromFloor);
      const to = Number(toFloor);
      const seen = new Set();
      for (const exc of exceptions) {
        const excFloor = typeof exc.floor === 'string' ? parseInt(exc.floor, 10) : exc.floor;
        if (isNaN(excFloor)) { errs.exceptions = 'ערך קומה לא תקין'; break; }
        if (excFloor < from || excFloor > to) { errs.exceptions = `קומה ${exc.floor} מחוץ לטווח`; break; }
        if (seen.has(excFloor)) { errs.exceptions = `קומה ${exc.floor} מופיעה פעמיים`; break; }
        seen.add(excFloor);
        const excUnits = exc.units === '' ? null : parseInt(String(exc.units), 10);
        if (excUnits === null || isNaN(excUnits)) { errs.exceptions = `קומה ${exc.floor}: יש להזין מספר דירות`; break; }
        if (excUnits < 0 || excUnits > 50) { errs.exceptions = `קומה ${exc.floor}: מספר דירות בין 0 ל-50`; break; }
      }
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleNext = () => {
    if (!validateStep()) return;
    setStep(s => Math.min(s + 1, 4));
  };

  const handleBack = () => setStep(s => Math.max(s - 1, 1));

  const handleGenerate = async () => {
    setSubmitting(true);
    try {
      const batchId = `qs-${Date.now().toString(36)}`;
      const building = await projectService.createBuilding(projectId, {
        project_id: projectId, name: buildingName.trim(), code: buildingCode.trim() || undefined,
      });
      const buildingId = building.id;

      const floorsRes = await buildingService.bulkCreateFloors({
        project_id: projectId, building_id: buildingId,
        from_floor: Number(fromFloor), to_floor: Number(toFloor),
        batch_id: batchId,
      });
      const createdFloors = floorsRes.created_count || floorCount;

      const hasExceptions = exceptions.length > 0;

      let unitsCreated = 0;
      let unitsRequested = 0;
      let unitErrorDetails = [];
      let floorsNoUnits = 0;

      if (!hasExceptions) {
        const defUnits = parseUnitsStr(defaultUnits);
        if (defUnits > 0) {
          unitsRequested = defUnits * floorCount;
          console.log(`[BULK-UNITS] No exceptions path: defUnits=${defUnits} floorCount=${floorCount} unitsRequested=${unitsRequested}`);
          try {
            const res = await floorService.bulkCreateUnits({
              project_id: projectId, building_id: buildingId,
              from_floor: Number(fromFloor), to_floor: Number(toFloor),
              units_per_floor: defUnits,
              batch_id: batchId,
            });
            unitsCreated = res.created_count || 0;
            console.log(`[BULK-UNITS] Created ${unitsCreated} units`);
          } catch (err) {
            const detail = err.response?.data?.detail || err.message || 'שגיאה לא ידועה';
            unitErrorDetails.push({ floor: 'all', error: detail, count: unitsRequested });
            console.warn('[BULK-UNITS] Bulk units failed:', detail, err);
          }
        } else {
          floorsNoUnits = floorCount;
          console.log(`[BULK-UNITS] All floors with 0 units (no bulkCreateUnits call). floorsNoUnits=${floorsNoUnits}`);
        }
      } else {
        for (const fl of floorsList) {
          const unitCount = fl.units;
          if (unitCount <= 0) {
            floorsNoUnits++;
            console.log(`[BULK-UNITS] Floor ${fl.floor}: 0 units (skipping)`);
            continue;
          }
          unitsRequested += unitCount;
          try {
            const res = await floorService.bulkCreateUnits({
              project_id: projectId, building_id: buildingId,
              from_floor: fl.floor, to_floor: fl.floor,
              units_per_floor: unitCount,
              batch_id: batchId,
            });
            unitsCreated += res.created_count || 0;
            console.log(`[BULK-UNITS] Floor ${fl.floor}: requested=${unitCount} created=${res.created_count || 0}`);
          } catch (err) {
            const detail = err.response?.data?.detail || err.message || 'שגיאה לא ידועה';
            unitErrorDetails.push({ floor: fl.floor, error: detail, count: unitCount });
            console.warn(`[BULK-UNITS] Floor ${fl.floor} failed:`, detail, err);
          }
        }
      }

      const failedUnits = unitsRequested - unitsCreated;
      console.log(`[BULK-UNITS] Summary: floors=${createdFloors} unitsRequested=${unitsRequested} unitsCreated=${unitsCreated} floorsNoUnits=${floorsNoUnits} failed=${failedUnits} errors=${unitErrorDetails.length}`);
      setResult({ building: buildingName, buildingId, floors: createdFloors, units: unitsCreated, unitsRequested, failedUnits, unitErrorDetails, batchId, floorsNoUnits });
      const noUnitsLabel = floorsNoUnits > 0 ? `, ${floorsNoUnits} קומות ללא דירות` : '';
      if (unitErrorDetails.length > 0) {
        toast.warning(`בניין "${buildingName}" נוצר עם ${createdFloors} קומות ו-${unitsCreated} דירות${noUnitsLabel} (${failedUnits} נכשלו)`);
      } else {
        toast.success(`בניין "${buildingName}" נוצר עם ${createdFloors} קומות ו-${unitsCreated} דירות${noUnitsLabel}`);
      }
      onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירה');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUndoBatch = async () => {
    if (!result?.batchId) return;
    try {
      const res = await archiveService.undoBatch(result.batchId);
      toast.success(`בוטל בהצלחה: ${res.archived_count} פריטים הועברו לארכיון`);
      setResult(null);
      setStep(1);
      onSuccess();
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה בביטול';
      toast.error(detail);
    }
  };

  const stepLabels = ['בניין', 'קומות', 'דירות', 'סיכום'];

  return (
    <BottomSheetModal open onClose={onClose} title="הקמה מהירה">
      <div className="flex gap-1 mb-3">
        {stepLabels.map((label, i) => (
          <div key={i} className={`flex-1 text-center py-1.5 text-xs font-medium rounded-lg transition-colors ${i + 1 === step ? 'bg-amber-500 text-white' : i + 1 < step ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-400'}`}>
            {i + 1 < step ? '✓' : ''} {label}
          </div>
        ))}
      </div>

      {result ? (
        result.failedUnits > 0 || result.unitErrorDetails?.length > 0 ? (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 text-center space-y-2">
          <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto" />
          <p className="font-semibold text-amber-800">הקמה נכשלה חלקית</p>
          <p className="text-sm text-amber-700">בניין: {result.building}</p>
          <p className="text-sm text-amber-700">{result.floors} קומות, {result.units} דירות נוצרו{result.floorsNoUnits > 0 ? `, ${result.floorsNoUnits} קומות ללא דירות` : ''}</p>
          <p className="text-sm text-red-600 font-medium">{result.failedUnits} דירות לא נוצרו</p>
          {result.unitErrorDetails?.length > 0 && (
            <details className="text-right mt-2">
              <summary className="text-xs text-amber-700 cursor-pointer font-medium">הצג פרטי שגיאות</summary>
              <div className="mt-1 bg-white border border-amber-200 rounded p-2 text-xs text-slate-700 space-y-1 max-h-32 overflow-y-auto">
                {result.unitErrorDetails.map((e, i) => (
                  <div key={i} className="flex justify-between gap-2">
                    <span className="text-red-600">{e.error}</span>
                    <span className="text-slate-500 shrink-0">{e.floor === 'all' ? 'כל הקומות' : `קומה ${e.floor}`} ({e.count})</span>
                  </div>
                ))}
              </div>
            </details>
          )}
          <div className="flex gap-2 mt-2">
            {result.batchId && (
              <Button onClick={handleUndoBatch} variant="outline" className="flex-1 text-amber-700 border-amber-300 hover:bg-amber-100 text-sm">
                <Undo2 className="w-4 h-4 ml-1" />ביטול הקמה
              </Button>
            )}
            <Button onClick={onClose} className="flex-1 bg-amber-500 hover:bg-amber-600 text-white">סגור</Button>
          </div>
        </div>
        ) : (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center space-y-2">
          <Check className="w-8 h-8 text-green-500 mx-auto" />
          <p className="font-semibold text-green-800">הקמה הושלמה בהצלחה!</p>
          <p className="text-sm text-green-700">בניין: {result.building}</p>
          <p className="text-sm text-green-700">{result.floors} קומות, {result.units} דירות{result.floorsNoUnits > 0 ? `, ${result.floorsNoUnits} קומות ללא דירות` : ''}</p>
          <div className="flex gap-2 mt-2">
            {result.batchId && (
              <Button onClick={handleUndoBatch} variant="outline" className="flex-1 text-red-600 border-red-200 hover:bg-red-50 text-sm">
                <Undo2 className="w-4 h-4 ml-1" />ביטול הקמה
              </Button>
            )}
            <Button onClick={onClose} className="flex-1 bg-green-500 hover:bg-green-600 text-white">סגור</Button>
          </div>
        </div>
        )
      ) : (
        <>
          {step === 1 && (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">הגדר את שם הבניין</p>
              <InputField label="שם בניין *" value={buildingName} onChange={setBuildingName} placeholder="למשל: בניין A" error={errors.buildingName} />
              <InputField label="קוד בניין" value={buildingCode} onChange={setBuildingCode} placeholder="למשל: A (אופציונלי)" />
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">הגדר את טווח הקומות</p>
              <InputField label="מקומה *" value={fromFloor} onChange={v => setFromFloor(v)} placeholder="למשל: -1" type="number" error={errors.fromFloor} dir="ltr" />
              <InputField label="עד קומה *" value={toFloor} onChange={v => setToFloor(v)} placeholder="למשל: 10" type="number" error={errors.toFloor} dir="ltr" />
              {floorCount > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-sm text-amber-800 text-center">
                  סה״כ {floorCount} קומות
                </div>
              )}
            </div>
          )}

          {step === 3 && (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">כמה דירות בכל קומה? (ברירת מחדל, 0 = ללא דירות)</p>
              <InputField label="מס׳ דירות לקומה *" value={defaultUnits} onChange={handleUnitsChange(setDefaultUnits)} onFocus={handleUnitsFocus} placeholder="0" inputMode="numeric" error={errors.defaultUnits} dir="ltr" />
              {exceptions.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-slate-600">חריגים (קומות עם מספר דירות שונה):</p>
                  {exceptions.map((exc, idx) => (
                    <div key={idx} className="flex gap-2 items-center">
                      <input type="number" value={exc.floor} onChange={e => updateException(idx, 'floor', e.target.value)}
                        className="w-20 text-sm border border-slate-200 rounded-lg px-2 py-1.5 text-center" placeholder="קומה" />
                      <span className="text-xs text-slate-400">→</span>
                      <input inputMode="numeric" value={exc.units} onChange={e => updateException(idx, 'units', e.target.value)}
                        onFocus={handleUnitsFocus}
                        className="w-20 text-sm border border-slate-200 rounded-lg px-2 py-1.5 text-center" placeholder="0" />
                      <span className="text-[10px] text-slate-400">דירות</span>
                      <button onClick={() => removeException(idx)} className="text-red-400 hover:text-red-600"><X className="w-4 h-4" /></button>
                    </div>
                  ))}
                </div>
              )}
              <button type="button" onClick={addException}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 text-xs font-medium rounded-lg border border-dashed border-slate-300 text-slate-600 hover:bg-slate-50 active:bg-slate-100">
                <Plus className="w-3.5 h-3.5" />
                הוסף חריג
              </button>
              {errors.exceptions && <p className="text-xs text-red-500 mt-1">{errors.exceptions}</p>}
            </div>
          )}

          {step === 4 && (
            <div className="space-y-3">
              <p className="text-sm text-slate-600">סיכום לפני יצירה</p>
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-1.5 text-sm">
                <p><span className="font-medium">בניין:</span> {buildingName}{buildingCode ? ` (${buildingCode})` : ''}</p>
                <p><span className="font-medium">קומות:</span> {fromFloor} עד {toFloor} ({floorCount} קומות)</p>
                <p><span className="font-medium">דירות לקומה:</span> {defaultUnits} (ברירת מחדל)</p>
                {exceptions.length > 0 && (
                  <div>
                    <span className="font-medium">חריגים:</span>
                    <ul className="mr-4 text-xs text-slate-600 mt-1">
                      {exceptions.map((exc, i) => (
                        <li key={i}>קומה {exc.floor}: {exc.units} דירות</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="border-t pt-1.5 mt-1.5">
                  <p className="font-semibold text-amber-700">סה״כ: {floorCount} קומות, {totalUnits} דירות</p>
                  {floorsWithoutUnits > 0 && (
                    <p className="text-xs text-slate-500 mt-0.5">{floorsWithoutUnits} קומות ללא דירות (חניון/מחסנים)</p>
                  )}
                </div>
              </div>
            </div>
          )}

          <div className="flex gap-2 mt-3">
            {step > 1 && (
              <Button onClick={handleBack} variant="outline" className="flex-1 text-sm" disabled={submitting}>
                חזרה
              </Button>
            )}
            {step < 4 ? (
              <Button onClick={handleNext} className="flex-1 bg-amber-500 hover:bg-amber-600 text-white text-sm">
                הבא
              </Button>
            ) : (
              <Button onClick={handleGenerate} disabled={submitting} className="flex-1 bg-green-500 hover:bg-green-600 text-white text-sm">
                {submitting ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />יוצר...</span> : `צור בניין (${floorCount} קומות, ${totalUnits} דירות)`}
              </Button>
            )}
          </div>
        </>
      )}
    </BottomSheetModal>
  );
};

const BulkFloorsForm = ({ projectId, buildings, onClose, onSuccess }) => {
  const [mode, setMode] = useState('range');
  const [buildingId, setBuildingId] = useState('');
  const [fromFloor, setFromFloor] = useState('');
  const [toFloor, setToFloor] = useState('');
  const [singleName, setSingleName] = useState('');
  const [insertAt, setInsertAt] = useState('');
  const [autoRenumber, setAutoRenumber] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [errors, setErrors] = useState({});
  const [result, setResult] = useState(null);
  const [preview, setPreview] = useState(null);

  const floorCount = fromFloor !== '' && toFloor !== '' ? Math.max(0, Number(toFloor) - Number(fromFloor) + 1) : 0;

  const resetState = () => { setPreview(null); setResult(null); setErrors({}); };
  const switchMode = (m) => { setMode(m); resetState(); };

  const validate = () => {
    const errs = {};
    if (!buildingId) errs.buildingId = 'חובה';
    if (mode === 'range') {
      if (fromFloor === '') errs.fromFloor = 'חובה';
      if (toFloor === '') errs.toFloor = 'חובה';
      if (fromFloor !== '' && toFloor !== '' && Number(toFloor) < Number(fromFloor)) errs.toFloor = 'חייב להיות גדול מ-"מקומה"';
    } else {
      if (!singleName.trim()) errs.singleName = 'חובה';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handlePreview = async () => {
    if (!validate()) return;
    setPreviewing(true);
    try {
      if (mode === 'range') {
        const res = await buildingService.bulkCreateFloors({
          project_id: projectId, building_id: buildingId,
          from_floor: Number(fromFloor), to_floor: Number(toFloor), dry_run: true,
        });
        setPreview(res);
      } else {
        const payload = { building_id: buildingId, name: singleName.trim(), dry_run: true };
        if (insertAt !== '') payload.insert_at_index = Number(insertAt);
        if (autoRenumber) payload.auto_renumber_units = true;
        const res = await sortIndexService.insertFloor(projectId, payload);
        setPreview(res);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה');
    } finally {
      setPreviewing(false);
    }
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    try {
      if (mode === 'range') {
        const res = await buildingService.bulkCreateFloors({
          project_id: projectId, building_id: buildingId,
          from_floor: Number(fromFloor), to_floor: Number(toFloor),
        });
        setResult(res);
        toast.success(res.message || `${res.created_count} קומות נוצרו בהצלחה`);
      } else {
        const payload = { building_id: buildingId, name: singleName.trim() };
        if (insertAt !== '') payload.insert_at_index = Number(insertAt);
        if (autoRenumber) payload.auto_renumber_units = true;
        const res = await sortIndexService.insertFloor(projectId, payload);
        setResult(res);
        toast.success('קומה נוספה בהצלחה');
      }
      onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת קומות');
    } finally {
      setSubmitting(false);
    }
  };

  const buildingOptions = buildings.map(b => ({ value: b.id, label: `${b.name}${b.code ? ` (${b.code})` : ''}` }));

  return (
    <BottomSheetModal open onClose={onClose} title="הוסף קומות">
      <div className="flex gap-1 mb-1">
        <button type="button" onClick={() => switchMode('range')}
          className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${mode === 'range' ? 'bg-amber-500 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
          טווח קומות
        </button>
        <button type="button" onClick={() => switchMode('insert')}
          className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${mode === 'insert' ? 'bg-amber-500 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
          הכנס קומה במיקום
        </button>
      </div>
      <SelectField label="בניין *" value={buildingId} onChange={v => { setBuildingId(v); resetState(); }} options={buildingOptions} error={errors.buildingId} emptyMessage="אין בניינים - הוסף בניין קודם" />
      {mode === 'range' ? (
        <>
          <InputField label="מקומה *" value={fromFloor} onChange={v => { setFromFloor(v); setPreview(null); }} placeholder="למשל: -1" type="number" error={errors.fromFloor} dir="ltr" />
          <InputField label="עד קומה *" value={toFloor} onChange={v => { setToFloor(v); setPreview(null); }} placeholder="למשל: 10" type="number" error={errors.toFloor} dir="ltr" />
          {floorCount > 0 && !preview && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
              טווח: {floorCount} קומות
            </div>
          )}
        </>
      ) : (
        <>
          <InputField label="קומה (מספר או שם) *" value={singleName} onChange={v => { setSingleName(v); setPreview(null); }} placeholder="למשל: 3, -1, גג, מרתף" error={errors.singleName} />
          <InputField label="מיקום הכנסה (sort_index)" value={insertAt} onChange={v => { setInsertAt(v); setPreview(null); }} placeholder="למשל: 5" type="number" dir="ltr" />
          <div className="flex items-center gap-2">
            <input type="checkbox" id="autoRenumber" checked={autoRenumber} onChange={e => { setAutoRenumber(e.target.checked); setPreview(null); }}
              className="w-4 h-4 text-amber-500 border-slate-300 rounded focus:ring-amber-500" />
            <label htmlFor="autoRenumber" className="text-sm text-slate-700">מספור אוטומטי של דירות</label>
          </div>
        </>
      )}
      {preview && mode === 'range' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
          <Eye className="w-4 h-4 inline ml-1" />
          תצוגה מקדימה: {preview.would_create} חדשות, {preview.would_skip} דילוגים
        </div>
      )}
      {preview && mode === 'insert' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800 space-y-1">
          <p className="font-medium"><Eye className="w-4 h-4 inline ml-1" />תצוגה מקדימה:</p>
          <p>קומות שיושפעו: {preview.floors_affected ?? 0}</p>
          <p>דירות שיושפעו: {preview.units_affected ?? 0}</p>
        </div>
      )}
      {result && mode === 'range' && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
          נוצרו {result.created_count}, דולגו {result.skipped_count}
        </div>
      )}
      {result && mode === 'insert' && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
          קומה נוספה בהצלחה
        </div>
      )}
      <div className="flex gap-2">
        <Button onClick={handlePreview} disabled={previewing || submitting} variant="outline" className="flex-1 text-sm">
          {previewing ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Eye className="w-4 h-4 ml-1" />תצוגה מקדימה</>}
        </Button>
        <Button onClick={handleSubmit} disabled={submitting} className="flex-1 bg-amber-500 hover:bg-amber-600 text-white text-sm">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : (mode === 'range' ? 'צור קומות' : 'הוסף קומה')}
        </Button>
      </div>
    </BottomSheetModal>
  );
};

const BulkUnitsForm = ({ projectId, buildings, onClose, onSuccess }) => {
  const [buildingId, setBuildingId] = useState('');
  const [fromFloor, setFromFloor] = useState('');
  const [toFloor, setToFloor] = useState('');
  const [unitsPerFloor, setUnitsPerFloor] = useState('4');
  
  const [submitting, setSubmitting] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [errors, setErrors] = useState({});
  const [result, setResult] = useState(null);
  const [preview, setPreview] = useState(null);

  const floorCount = fromFloor !== '' && toFloor !== '' ? Math.max(0, Number(toFloor) - Number(fromFloor) + 1) : 0;
  const parsedUnitsPerFloor = parseInt(unitsPerFloor, 10);
  const totalUnits = floorCount * (isNaN(parsedUnitsPerFloor) ? 0 : parsedUnitsPerFloor);

  const handleUnitsChange = (val) => {
    const raw = String(val).replace(/[^0-9]/g, '');
    if (raw === '') { setUnitsPerFloor(''); return; }
    const num = parseInt(raw, 10);
    setUnitsPerFloor(String(Math.min(num, 50)));
  };

  const validate = () => {
    const errs = {};
    if (!buildingId) errs.buildingId = 'חובה';
    if (fromFloor === '') errs.fromFloor = 'חובה';
    if (toFloor === '') errs.toFloor = 'חובה';
    if (fromFloor !== '' && toFloor !== '' && Number(toFloor) < Number(fromFloor)) errs.toFloor = 'חייב להיות גדול מ-"מקומה"';
    const uVal = unitsPerFloor.trim();
    if (uVal === '' || isNaN(parseInt(uVal, 10))) { errs.unitsPerFloor = 'יש להזין מספר'; }
    else if (parseInt(uVal, 10) < 1 || parseInt(uVal, 10) > 50) { errs.unitsPerFloor = 'בין 1 ל-50'; }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handlePreview = async () => {
    if (!validate()) return;
    setPreviewing(true);
    try {
      const res = await floorService.bulkCreateUnits({
        project_id: projectId, building_id: buildingId,
        from_floor: Number(fromFloor), to_floor: Number(toFloor),
        units_per_floor: Number(unitsPerFloor),
        dry_run: true,
      });
      setPreview(res);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה');
    } finally {
      setPreviewing(false);
    }
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    try {
      const res = await floorService.bulkCreateUnits({
        project_id: projectId, building_id: buildingId,
        from_floor: Number(fromFloor), to_floor: Number(toFloor),
        units_per_floor: Number(unitsPerFloor),
      });
      setResult(res);
      toast.success(res.message || `${res.created_count} דירות נוצרו בהצלחה`);
      onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת דירות');
    } finally {
      setSubmitting(false);
    }
  };

  const buildingOptions = buildings.map(b => ({ value: b.id, label: `${b.name}${b.code ? ` (${b.code})` : ''}` }));

  return (
    <BottomSheetModal open onClose={onClose} title="הוסף דירות">
      <SelectField label="בניין *" value={buildingId} onChange={v => { setBuildingId(v); setPreview(null); }} options={buildingOptions} error={errors.buildingId} emptyMessage="אין בניינים" />
      <InputField label="מקומה *" value={fromFloor} onChange={v => { setFromFloor(v); setPreview(null); }} placeholder="1" type="number" error={errors.fromFloor} dir="ltr" />
      <InputField label="עד קומה *" value={toFloor} onChange={v => { setToFloor(v); setPreview(null); }} placeholder="10" type="number" error={errors.toFloor} dir="ltr" />
      <InputField label="דירות לקומה *" value={unitsPerFloor} onChange={handleUnitsChange} onFocus={e => e.target.select()} placeholder="4" inputMode="numeric" error={errors.unitsPerFloor} dir="ltr" />
      {totalUnits > 0 && !preview && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
          טווח: {totalUnits} דירות ({floorCount} קומות × {unitsPerFloor} דירות/קומה)
        </div>
      )}
      {preview && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
          <Eye className="w-4 h-4 inline ml-1" />
          תצוגה מקדימה: {preview.would_create} חדשות, {preview.would_skip} דילוגים
        </div>
      )}
      {result && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
          נוצרו {result.created_count} דירות, דולגו {result.skipped_count}
        </div>
      )}
      <div className="flex gap-2">
        <Button onClick={handlePreview} disabled={previewing || submitting} variant="outline" className="flex-1 text-sm">
          {previewing ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Eye className="w-4 h-4 ml-1" />תצוגה מקדימה</>}
        </Button>
        <Button onClick={handleSubmit} disabled={submitting} className="flex-1 bg-amber-500 hover:bg-amber-600 text-white text-sm">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'צור דירות'}
        </Button>
      </div>
    </BottomSheetModal>
  );
};

const AddCompanyForm = ({ projectId, onClose, onSuccess, onCreated }) => {
  const [name, setName] = useState('');
  const [trade, setTrade] = useState('');
  const [contactName, setContactName] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});
  const [tradeOptions, setTradeOptions] = useState([]);
  const [tradesLoading, setTradesLoading] = useState(true);
  const [showNewTrade, setShowNewTrade] = useState(false);
  const [newTradeLabel, setNewTradeLabel] = useState('');
  const [creatingTrade, setCreatingTrade] = useState(false);

  const fetchTrades = useCallback(() => {
    setTradesLoading(true);
    tradeService.listForProject(projectId)
      .then(data => {
        const opts = (data.trades || []).map(t => ({ value: t.key, label: t.label_he }));
        setTradeOptions(opts);
      })
      .catch(() => toast.error('שגיאה בטעינת תחומים'))
      .finally(() => setTradesLoading(false));
  }, [projectId]);

  useEffect(() => { fetchTrades(); }, [fetchTrades]);

  const handleAddTrade = async () => {
    if (!newTradeLabel.trim()) return;
    setCreatingTrade(true);
    try {
      const result = await tradeService.createForProject(projectId, { label_he: newTradeLabel.trim() });
      toast.success('תחום חדש נוצר בהצלחה');
      setNewTradeLabel('');
      setShowNewTrade(false);
      await fetchTrades();
      if (result.key) setTrade(result.key);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת תחום');
    } finally {
      setCreatingTrade(false);
    }
  };

  const allFilled = !!name.trim();

  const handleSubmit = async () => {
    const errs = {};
    if (!name.trim()) errs.name = 'שדה חובה';
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;
    setSubmitting(true);
    try {
      const payload = { name: name.trim() };
      if (trade) payload.trade = trade;
      if (contactName.trim()) payload.contact_name = contactName.trim();
      if (contactPhone.trim()) payload.contact_phone = contactPhone.trim();
      const result = await projectCompanyService.create(projectId, payload);
      toast.success('חברה נוספה בהצלחה');
      onSuccess();
      if (onCreated && result?.id) onCreated(result.id);
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BottomSheetModal open onClose={onClose} title="הוסף חברה חדשה">
      <InputField label="שם חברה *" value={name} onChange={setName} placeholder="למשל: חברת חשמל" error={errors.name} />
      <SelectField label="תחום" value={trade} onChange={setTrade} options={tradeOptions} isLoading={tradesLoading} />
      {!showNewTrade && (
        <button
          type="button"
          onClick={() => setShowNewTrade(true)}
          className="w-full mb-2 flex items-center justify-center gap-1.5 py-2 text-xs font-medium rounded-lg border border-dashed border-amber-300 text-amber-700 hover:bg-amber-50 active:bg-amber-100 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          הוסף תחום חדש
        </button>
      )}
      {showNewTrade && (
        <div className="mb-2 p-2.5 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
          <InputField label="שם תחום בעברית *" value={newTradeLabel} onChange={setNewTradeLabel} placeholder="למשל: מעליות" />
          <div className="flex gap-2">
            <Button onClick={handleAddTrade} disabled={creatingTrade || !newTradeLabel.trim()} className="flex-1 bg-amber-500 hover:bg-amber-600 text-white text-xs py-1.5 rounded-lg">
              {creatingTrade ? <Loader2 className="w-3.5 h-3.5 animate-spin mx-auto" /> : 'שמור'}
            </Button>
            <Button onClick={() => { setShowNewTrade(false); setNewTradeLabel(''); }} className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs py-1.5 rounded-lg">
              ביטול
            </Button>
          </div>
        </div>
      )}
      <InputField label="שם איש קשר" value={contactName} onChange={setContactName} placeholder="שם מלא" />
      <InputField label="טלפון" value={contactPhone} onChange={setContactPhone} placeholder="050-1234567" dir="ltr" />
      <Button onClick={handleSubmit} disabled={submitting || !allFilled} className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 rounded-lg">
        {submitting ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'הוסף חברה'}
      </Button>
    </BottomSheetModal>
  );
};

const AddTeamMemberForm = ({ projectId, companies, onClose, onSuccess, prefillTrade, onRefreshCompanies }) => {
  const [phone, setPhone] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('contractor');
  const [subRole, setSubRole] = useState('');
  const [tradeKey, setTradeKey] = useState(prefillTrade || '');
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});
  const [tradeOptions, setTradeOptions] = useState([]);
  const [showNewTrade, setShowNewTrade] = useState(false);
  const [newTradeLabel, setNewTradeLabel] = useState('');
  const [creatingTrade, setCreatingTrade] = useState(false);
  const [companyId, setCompanyId] = useState('');
  const [showNewCompany, setShowNewCompany] = useState(false);
  const [newCompanyName, setNewCompanyName] = useState('');
  const [creatingCompany, setCreatingCompany] = useState(false);
  const tradeSelectRef = useRef(null);
  const focusTradeTimerRef = useRef(null);

  useEffect(() => {
    return () => { if (focusTradeTimerRef.current) clearTimeout(focusTradeTimerRef.current); };
  }, []);

  const handleAddCompany = async () => {
    if (!newCompanyName.trim()) return;
    setCreatingCompany(true);
    try {
      const result = await projectCompanyService.create(projectId, { name: newCompanyName.trim() });
      toast.success('חברה נוספה בהצלחה');
      setNewCompanyName('');
      setShowNewCompany(false);
      if (onRefreshCompanies) await onRefreshCompanies();
      if (result?.id) setCompanyId(result.id);
      if (focusTradeTimerRef.current) clearTimeout(focusTradeTimerRef.current);
      focusTradeTimerRef.current = setTimeout(() => {
        const btn = tradeSelectRef.current?.querySelector('button');
        if (btn && !tradeKey) {
          btn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          btn.click();
        }
      }, 150);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת חברה');
    } finally {
      setCreatingCompany(false);
    }
  };

  const roleOptions = [
    { value: 'project_manager', label: 'מנהל פרויקט' },
    { value: 'management_team', label: 'צוות ניהולי' },
    { value: 'contractor', label: 'קבלן' },
    { value: 'viewer', label: 'צופה' },
  ];
  const subRoleOptions = [
    { value: 'site_manager', label: 'מנהל אתר' },
    { value: 'execution_engineer', label: 'מהנדס ביצוע' },
    { value: 'safety_assistant', label: 'עוזר בטיחות' },
    { value: 'work_manager', label: 'מנהל עבודה' },
    { value: 'safety_officer', label: 'ממונה בטיחות' },
  ];
  const companyOptions = companies.map(c => ({ value: c.id, label: c.name }));

  const fetchTrades = useCallback(() => {
    tradeService.listForProject(projectId)
      .then(data => {
        const opts = (data.trades || []).map(t => ({ value: t.key, label: t.label_he }));
        setTradeOptions(opts);
      })
      .catch(() => {});
  }, [projectId]);

  useEffect(() => { fetchTrades(); }, [fetchTrades]);

  const handleAddTrade = async () => {
    if (!newTradeLabel.trim()) return;
    setCreatingTrade(true);
    try {
      const result = await tradeService.createForProject(projectId, { label_he: newTradeLabel.trim() });
      toast.success('תחום חדש נוצר בהצלחה');
      setNewTradeLabel('');
      setShowNewTrade(false);
      await fetchTrades();
      if (result.key) setTradeKey(result.key);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת תחום');
    } finally {
      setCreatingTrade(false);
    }
  };

  const allFilled = phone.trim() && fullName.trim() && role
    && (role !== 'management_team' || subRole)
    && (role !== 'contractor' || (tradeKey && companyId));

  const handleSubmit = async () => {
    const errs = {};
    if (!phone.trim()) errs.phone = 'יש להזין מספר נייד ישראלי תקין';
    if (!fullName.trim()) errs.fullName = 'שדה חובה';
    if (!role) errs.role = 'שדה חובה';
    if (role === 'management_team' && !subRole) errs.subRole = 'חובה לבחור תת-תפקיד';
    if (role === 'contractor' && !tradeKey) errs.tradeKey = 'חובה לבחור תחום';
    if (role === 'contractor' && !companyId) errs.companyId = 'חובה לבחור חברה';
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;
    setSubmitting(true);
    try {
      const payload = {
        phone: phone.trim(), full_name: fullName.trim(),
        role,
      };
      if (role === 'management_team' && subRole) payload.sub_role = subRole;
      if (role === 'contractor' && tradeKey) payload.trade_key = tradeKey;
      if (role === 'contractor' && companyId) payload.company_id = companyId;
      const result = await teamInviteService.create(projectId, payload);
      const ns = result?.notification_status;
      if (ns?.channel_used === 'sms' && ns?.wa_skipped) {
        toast.success('הזמנה נשלחה ב-SMS (WhatsApp לא זמין כרגע)');
      } else if (ns?.channel_used === 'sms') {
        toast.success('הזמנה נשלחה בהצלחה ב-SMS');
      } else if (ns?.channel_used === 'whatsapp') {
        toast.success('הזמנה נשלחה בהצלחה ב-WhatsApp');
      } else if (ns?.channel_used === 'none' && ns?.reason) {
        toast.warning(`הזמנה נוצרה, אך שליחת ההודעה נכשלה: ${ns.reason}`);
      } else {
        toast.success('הזמנה נוצרה בהצלחה');
      }
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BottomSheetModal open onClose={onClose} title="הוסף איש צוות">
      <InputField label="טלפון *" value={phone} onChange={setPhone} placeholder="05X-XXXXXXX" error={errors.phone} dir="ltr" type="tel" inputMode="tel" />
      <InputField label="שם מלא *" value={fullName} onChange={setFullName} placeholder="שם מלא" error={errors.fullName} />
      <SelectField label="תפקיד *" value={role} onChange={(val) => { setRole(val); if (val !== 'management_team') setSubRole(''); if (val !== 'contractor') { setTradeKey(prefillTrade || ''); setCompanyId(''); } }} options={roleOptions} error={errors.role} />
      {role === 'management_team' && (
        <SelectField label="תת-תפקיד *" value={subRole} onChange={setSubRole} options={subRoleOptions} error={errors.subRole} />
      )}
      {role === 'contractor' && (
        <>
          <div ref={tradeSelectRef}>
            <SelectField label="תחום *" value={tradeKey} onChange={setTradeKey} options={tradeOptions} placeholder="בחר תחום" error={errors.tradeKey} />
          </div>
          {!showNewTrade && (
            <button
              type="button"
              onClick={() => setShowNewTrade(true)}
              className="w-full mb-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-medium rounded-lg border border-dashed border-amber-300 text-amber-700 hover:bg-amber-50 active:bg-amber-100 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              הוסף תחום חדש
            </button>
          )}
          {showNewTrade && (
            <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
              <InputField label="שם תחום בעברית *" value={newTradeLabel} onChange={setNewTradeLabel} placeholder="למשל: מעליות" />
              <div className="flex gap-2">
                <Button onClick={handleAddTrade} disabled={creatingTrade || !newTradeLabel.trim()} className="flex-1 bg-amber-500 hover:bg-amber-600 text-white text-xs py-1.5 rounded-lg">
                  {creatingTrade ? <Loader2 className="w-3.5 h-3.5 animate-spin mx-auto" /> : 'שמור'}
                </Button>
                <Button onClick={() => { setShowNewTrade(false); setNewTradeLabel(''); }} className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs py-1.5 rounded-lg">
                  ביטול
                </Button>
              </div>
            </div>
          )}
          <SelectField label="חברה *" value={companyId} onChange={setCompanyId} options={companyOptions} error={errors.companyId} emptyMessage="אין חברות – הוסף חברה למטה" />
          {!showNewCompany && (
            <button
              type="button"
              onClick={() => setShowNewCompany(true)}
              className="w-full mb-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-medium rounded-lg border border-dashed border-amber-300 text-amber-700 hover:bg-amber-50 active:bg-amber-100 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              הוסף חברה חדשה
            </button>
          )}
          {showNewCompany && (
            <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
              <InputField label="שם חברה *" value={newCompanyName} onChange={setNewCompanyName} placeholder="למשל: חברת חשמל" />
              <div className="flex gap-2">
                <Button onClick={handleAddCompany} disabled={creatingCompany || !newCompanyName.trim()} className="flex-1 bg-amber-500 hover:bg-amber-600 text-white text-xs py-1.5 rounded-lg">
                  {creatingCompany ? <Loader2 className="w-3.5 h-3.5 animate-spin mx-auto" /> : 'שמור'}
                </Button>
                <Button onClick={() => { setShowNewCompany(false); setNewCompanyName(''); }} className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs py-1.5 rounded-lg">
                  ביטול
                </Button>
              </div>
            </div>
          )}
        </>
      )}
      <Button onClick={handleSubmit} disabled={submitting || !allFilled} className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 rounded-lg">
        {submitting ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : <><Send className="w-4 h-4 inline ml-1" />שלח הזמנה</>}
      </Button>
    </BottomSheetModal>
  );
};

const ExcelImportModal = ({ projectId, onClose, onSuccess }) => {
  const [file, setFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef(null);

  const handleImport = async () => {
    if (!file) { toast.error('בחר קובץ'); return; }
    setImporting(true);
    try {
      const res = await excelService.importFile(projectId, file);
      setResult(res);
      if (res.created_count > 0) {
        toast.success(`יובאו ${res.created_count} רשומות`);
        onSuccess();
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביבוא');
    } finally {
      setImporting(false);
    }
  };

  return (
    <BottomSheetModal open onClose={onClose} title="יבוא מאקסל">
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-center">
        <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
        <p className="text-sm text-slate-600 mb-3">בחר קובץ CSV/XLSX</p>
        <input ref={fileRef} type="file" accept=".csv,.xlsx" className="hidden" onChange={e => setFile(e.target.files[0])} />
        <Button variant="outline" onClick={() => fileRef.current?.click()} className="text-sm">
          {file ? file.name : 'בחר קובץ'}
        </Button>
      </div>
      <Button variant="outline" onClick={() => excelService.downloadTemplate(projectId)} className="w-full text-sm">
        <Download className="w-4 h-4 ml-1" />הורד תבנית
      </Button>
      {result && (
        <div className="space-y-2">
          <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
            נוצרו: {result.created_count}
          </div>
          {result.skipped_count > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
              דולגו: {result.skipped_count}
            </div>
          )}
          {result.error_count > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
              שגיאות: {result.error_count}
              <ul className="mt-1 mr-4 list-disc text-xs">
                {result.details?.errors?.slice(0, 5).map((e, i) => (
                  <li key={i}>שורה {e.row}: {e.error}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      <Button onClick={handleImport} disabled={importing || !file} className="w-full bg-amber-500 hover:bg-amber-600 text-white text-sm">
        {importing ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'יבא'}
      </Button>
    </BottomSheetModal>
  );
};

const QC_BADGE_COLORS = {
  not_started: 'bg-slate-50 text-slate-400',
  in_progress: 'bg-amber-50 text-amber-600',
  pending_review: 'bg-slate-100 text-slate-600',
  submitted: 'bg-slate-100 text-slate-600',
};

const StructureTab = ({ hierarchy, hierarchyLoading, buildings, projectId, onRefresh, onAddBuilding, onQuickSetup, isPM, isSuperAdmin, isManagement, defectsV2Enabled }) => {
  const navigate = useNavigate();
  const [expandedBuildings, setExpandedBuildings] = useState({});
  const [expandedFloors, setExpandedFloors] = useState({});
  const [addingFloorTo, setAddingFloorTo] = useState(null);
  const [newFloorName, setNewFloorName] = useState('');
  const [newUnitCount, setNewUnitCount] = useState('0');
  const [floorSaving, setFloorSaving] = useState(false);
  const [addingUnitTo, setAddingUnitTo] = useState(null);
  const [newUnitNo, setNewUnitNo] = useState('');
  const [unitSaving, setUnitSaving] = useState(false);
  const [showArchive, setShowArchive] = useState(false);
  const [archived, setArchived] = useState(null);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [restoring, setRestoring] = useState({});
  const [archiveSearch, setArchiveSearch] = useState('');
  const [expandedArchiveBuildings, setExpandedArchiveBuildings] = useState({});
  const [hardDeleteTarget, setHardDeleteTarget] = useState(null);
  const [hardDeleteConfirmation, setHardDeleteConfirmation] = useState('');
  const [hardDeleteLoading, setHardDeleteLoading] = useState(false);
  const [stepup, setStepup] = useState(null);
  const [stepupCode, setStepupCode] = useState('');
  const [stepupLoading, setStepupLoading] = useState(false);
  const [qcStatuses, setQcStatuses] = useState({});

  useEffect(() => {
    if (!isManagement || !hierarchy?.length) return;
    const floorIds = [];
    hierarchy.forEach(b => (b.floors || []).forEach(f => floorIds.push(f.id)));
    if (floorIds.length === 0) return;
    qcService.getFloorsBatchStatus(floorIds).then(setQcStatuses).catch(() => {});
  }, [hierarchy, isManagement]);

  const toggleBuilding = (id) => setExpandedBuildings(prev => ({ ...prev, [id]: !prev[id] }));
  const toggleFloor = (id) => setExpandedFloors(prev => ({ ...prev, [id]: !prev[id] }));

  const handleAddFloor = async (buildingId) => {
    if (!newFloorName.trim()) { toast.error('יש להזין קומה (מספר או שם)'); return; }
    setFloorSaving(true);
    try {
      const unitCount = parseInt(newUnitCount) || 0;
      await buildingService.createFloor(buildingId, {
        name: newFloorName.trim(),
        floor_number: 0,
        unit_count: unitCount,
      });
      toast.success('קומה נוספה בהצלחה');
      setAddingFloorTo(null);
      setNewFloorName('');
      setNewUnitCount('0');
      onRefresh();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join(', ') : 'שגיאה בהוספת קומה';
      toast.error(msg);
    } finally {
      setFloorSaving(false);
    }
  };

  const handleAddUnit = async (floorId) => {
    const count = parseInt(newUnitNo) || 0;
    if (count <= 0) { toast.error('יש להזין כמות דירות (מספר חיובי)'); return; }
    setUnitSaving(true);
    try {
      await floorService.createUnit(floorId, { unit_count: count });
      toast.success(`${count} דירות נוספו בהצלחה`);
      setAddingUnitTo(null);
      setNewUnitNo('');
      onRefresh();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join(', ') : 'שגיאה בהוספת דירות';
      toast.error(msg);
    } finally {
      setUnitSaving(false);
    }
  };

  const loadArchived = async () => {
    setArchiveLoading(true);
    try {
      const data = await archiveService.getArchived(projectId);
      setArchived(data);
    } catch (err) {
      toast.error('שגיאה בטעינת ארכיון');
    } finally {
      setArchiveLoading(false);
    }
  };

  const handleRestore = async (type, id, name) => {
    setRestoring(prev => ({ ...prev, [id]: true }));
    try {
      if (type === 'building') await archiveService.restoreBuilding(id);
      else if (type === 'floor') await archiveService.restoreFloor(id);
      else if (type === 'unit') await archiveService.restoreUnit(id);
      toast.success(`"${name}" שוחזר בהצלחה`);
      loadArchived();
      onRefresh();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בשחזור');
    } finally {
      setRestoring(prev => ({ ...prev, [id]: false }));
    }
  };

  const handleArchiveBuilding = async (building) => {
    if (!window.confirm(`לארכב את בניין "${building.name}"? כל הקומות והדירות שלו יועברו לארכיון.`)) return;
    try {
      const res = await archiveService.archiveBuilding(building.id);
      toast.success(`בניין "${building.name}" הועבר לארכיון (${res.cascaded_floors} קומות)`);
      onRefresh();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בארכוב');
    }
  };

  const handleArchiveFloor = async (floor) => {
    if (!window.confirm(`לארכב את "${floor.name || floor.display_label}"? כל הדירות בקומה יועברו לארכיון.`)) return;
    try {
      const res = await archiveService.archiveFloor(floor.id);
      toast.success(`קומה "${floor.name || floor.display_label}" הועברה לארכיון (${res.cascaded_units} דירות)`);
      onRefresh();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בארכוב');
    }
  };

  const handleArchiveUnit = async (unit) => {
    if (!window.confirm(`לארכב את דירה "${unit.effective_label || unit.unit_no}"?`)) return;
    try {
      await archiveService.archiveUnit(unit.id);
      toast.success(`דירה "${unit.effective_label || unit.unit_no}" הועברה לארכיון`);
      onRefresh();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בארכוב');
    }
  };

  const handleHardDelete = async (type, id, name) => {
    setHardDeleteTarget({ type, id, name });
    setHardDeleteConfirmation('');
  };

  const confirmHardDelete = async () => {
    if (!hardDeleteTarget) return;
    if (hardDeleteConfirmation.trim() !== hardDeleteTarget.name.trim()) {
      toast.error(`הקלד "${hardDeleteTarget.name}" לאישור`);
      return;
    }
    setHardDeleteLoading(true);
    try {
      await archiveService.hardDelete(hardDeleteTarget.type, hardDeleteTarget.id, hardDeleteConfirmation);
      toast.success(`"${hardDeleteTarget.name}" נמחק לצמיתות`);
      setHardDeleteTarget(null);
      loadArchived();
      onRefresh();
    } catch (err) {
      if (isStepupError(err)) {
        startStepup(() => confirmHardDelete());
        return;
      }
      toast.error(err.response?.data?.detail || 'שגיאה במחיקה');
    } finally {
      setHardDeleteLoading(false);
    }
  };

  const startStepup = async (retryAction) => {
    setStepupLoading(true);
    try {
      const result = await stepupService.requestChallenge();
      setStepup({ challengeId: result.challenge_id, maskedEmail: result.masked_email, retryAction });
      setStepupCode('');
      toast.success(`קוד אימות נשלח ל-${result.masked_email}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בשליחת קוד אימות');
    } finally {
      setStepupLoading(false);
    }
  };

  const handleStepupVerify = async () => {
    if (!stepup || !stepupCode.trim()) return;
    setStepupLoading(true);
    try {
      await stepupService.verifyChallenge(stepup.challengeId, stepupCode);
      toast.success('אימות הצליח');
      const retry = stepup.retryAction;
      setStepup(null);
      setStepupCode('');
      if (retry) retry();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'קוד לא תקין');
    } finally {
      setStepupLoading(false);
    }
  };

  const renderHardDeleteButton = (item, entityType, entityId, entityName) => {
    if (!isSuperAdmin) return null;
    const tasks = item.dependencies?.tasks || 0;
    if (tasks > 0) {
      return (
        <button
          onClick={(e) => { e.stopPropagation(); toast.error(`לא ניתן למחוק לצמיתות – יש ${tasks} משימות מקושרות. יש למחוק או להעביר אותן קודם.`); }}
          className="p-1.5 text-slate-300 hover:text-slate-400 cursor-pointer transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      );
    }
    const archivedTime = item.archived_at ? new Date(item.archived_at).getTime() : NaN;
    const daysSince = isNaN(archivedTime) ? 0 : Math.floor((Date.now() - archivedTime) / 86400000);
    if (daysSince < 7) {
      const remaining = 7 - daysSince;
      return (
        <button
          onClick={(e) => { e.stopPropagation(); toast(`מחיקה לצמיתות אפשרית רק אחרי 7 ימים בארכיון. נותרו ${remaining} ימים.`, { icon: '🔒' }); }}
          className="p-1.5 text-slate-300 hover:text-slate-400 cursor-pointer transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      );
    }
    return (
      <button
        onClick={(e) => { e.stopPropagation(); handleHardDelete(entityType, entityId, entityName); }}
        className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
        title="מחיקה לצמיתות"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    );
  };

  if (hierarchyLoading) {
    return <div className="flex items-center justify-center py-12"><Loader2 className="w-8 h-8 text-amber-500 animate-spin" /></div>;
  }

  if (hierarchy.length === 0) {
    return (
      <Card className="p-8">
        <div className="flex flex-col items-center justify-center text-slate-400">
          <Building2 className="w-12 h-12 mb-3" />
          <p className="text-lg font-medium text-slate-600">אין בניינים בפרויקט</p>
          <p className="text-sm mt-1 mb-4">התחל בהוספת בניין ראשון לפרויקט</p>
          <div className="flex gap-2">
            {onQuickSetup && (
              <Button
                onClick={onQuickSetup}
                className="bg-green-500 hover:bg-green-600 text-white font-medium px-6 py-2.5 rounded-lg text-sm"
              >
                <Zap className="w-4 h-4 ml-1 inline" />
                הקמה מהירה
              </Button>
            )}
            {onAddBuilding && (
              <Button
                onClick={onAddBuilding}
                variant="outline"
                className="border-amber-300 text-amber-700 font-medium px-6 py-2.5 rounded-lg text-sm"
              >
                <Plus className="w-4 h-4 ml-1 inline" />
                הוסף בניין
              </Button>
            )}
          </div>
        </div>
      </Card>
    );
  }

  if (showArchive) {
    if (!archived && !archiveLoading) loadArchived();
    const totalArchived = (archived?.buildings?.length || 0) + (archived?.floors?.length || 0) + (archived?.units?.length || 0);

    const searchLower = archiveSearch.toLowerCase();
    const matchesSearch = (item, type) => {
      if (!searchLower) return true;
      if (type === 'building') return (item.name || '').toLowerCase().includes(searchLower);
      if (type === 'floor') return (item.name || '').toLowerCase().includes(searchLower) || (item.display_label || '').toLowerCase().includes(searchLower);
      if (type === 'unit') return (item.unit_no || '').toLowerCase().includes(searchLower) || (item.display_label || '').toLowerCase().includes(searchLower);
      return false;
    };

    const archivedBuildingIds = new Set((archived?.buildings || []).map(b => b.id));

    const filteredBuildings = (archived?.buildings || []).filter(b => {
      if (matchesSearch(b, 'building')) return true;
      const bFloors = (archived?.floors || []).filter(f => f.building_id === b.id);
      if (bFloors.some(f => matchesSearch(f, 'floor'))) return true;
      const bUnits = (archived?.units || []).filter(u => bFloors.some(f => f.id === u.floor_id));
      if (bUnits.some(u => matchesSearch(u, 'unit'))) return true;
      return false;
    });

    const archivedFloorIdsInBuildings = new Set(
      (archived?.floors || []).filter(f => archivedBuildingIds.has(f.building_id)).map(f => f.id)
    );

    const standaloneFloors = (archived?.floors || []).filter(f =>
      !archivedBuildingIds.has(f.building_id) && matchesSearch(f, 'floor')
    );

    const standaloneUnits = (archived?.units || []).filter(u => {
      const floorIds = new Set((archived?.floors || []).map(f => f.id));
      if (archivedFloorIdsInBuildings.has(u.floor_id)) return false;
      if (floorIds.has(u.floor_id)) return false;
      return matchesSearch(u, 'unit');
    });

    const toggleArchiveBuilding = (id) => setExpandedArchiveBuildings(prev => ({ ...prev, [id]: !prev[id] }));

    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <Button onClick={() => { setShowArchive(false); setArchived(null); setArchiveSearch(''); }} variant="outline" className="text-sm flex-shrink-0">
            <ArrowRight className="w-4 h-4 ml-1" />חזרה למבנה
          </Button>
          <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2 flex-shrink-0">
            <Archive className="w-4 h-4" />ארכיון ({totalArchived})
          </h3>
        </div>
        <div className="relative">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={archiveSearch}
            onChange={e => setArchiveSearch(e.target.value)}
            placeholder="חיפוש בארכיון..."
            className="w-full pr-9 pl-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>
        {archiveLoading ? (
          <div className="flex items-center justify-center py-8"><Loader2 className="w-6 h-6 text-amber-500 animate-spin" /></div>
        ) : totalArchived === 0 ? (
          <Card className="p-6 text-center text-slate-400">
            <Archive className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">אין פריטים בארכיון</p>
          </Card>
        ) : (
          <div className="space-y-2">
            {filteredBuildings.map(b => {
              const isExp = expandedArchiveBuildings[b.id];
              const bFloors = (archived?.floors || []).filter(f => f.building_id === b.id);
              const bUnits = (archived?.units || []).filter(u => bFloors.some(f => f.id === u.floor_id));
              return (
                <Card key={b.id} className="overflow-hidden">
                  <div className="flex items-center gap-2 p-3">
                    <button onClick={() => toggleArchiveBuilding(b.id)} className="flex-1 flex items-center gap-2 text-right min-w-0">
                      {isExp ? <ChevronUp className="w-4 h-4 text-slate-400 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />}
                      <Building2 className="w-4 h-4 text-amber-500 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-700 truncate">{b.name}</p>
                        <p className="text-[11px] text-slate-400">ארכוב: {b.archived_at ? new Date(b.archived_at).toLocaleDateString('he-IL') : ''}</p>
                      </div>
                    </button>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {renderHardDeleteButton(b, 'building', b.id, b.name)}
                      <Button
                        onClick={() => handleRestore('building', b.id, b.name)}
                        disabled={restoring[b.id]}
                        size="sm" variant="outline"
                        className="text-green-600 border-green-200 hover:bg-green-50 text-xs"
                      >
                        {restoring[b.id] ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <><RotateCcw className="w-3.5 h-3.5 ml-1" />שחזר</>}
                      </Button>
                    </div>
                  </div>
                  {isExp && (bFloors.length > 0 || bUnits.length > 0) && (
                    <div className="border-t border-slate-100 px-3 py-2 space-y-2">
                      {bFloors.map(f => {
                        const fUnits = bUnits.filter(u => u.floor_id === f.id);
                        return (
                          <div key={f.id} className="bg-slate-50 rounded-lg p-2">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Layers className="w-3.5 h-3.5 text-blue-500" />
                                <span className="text-sm text-slate-700">{f.display_label || f.name}</span>
                              </div>
                              <div className="flex items-center gap-1">
                                {renderHardDeleteButton(f, 'floor', f.id, f.display_label || f.name)}
                                <Button
                                  onClick={() => handleRestore('floor', f.id, f.display_label || f.name)}
                                  disabled={restoring[f.id]}
                                  size="sm" variant="ghost"
                                  className="text-green-600 hover:bg-green-50 text-xs h-7 px-2"
                                >
                                  {restoring[f.id] ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                                </Button>
                              </div>
                            </div>
                            {fUnits.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-1.5 mr-6">
                                {fUnits.map(u => (
                                  <div key={u.id} className="flex items-center gap-1 bg-white rounded px-1.5 py-0.5 border border-slate-200 text-xs text-slate-600">
                                    <span>{u.display_label || u.unit_no}</span>
                                    <div className="flex items-center gap-0.5">
                                      {renderHardDeleteButton(u, 'unit', u.id, u.display_label || u.unit_no)}
                                      <button
                                        onClick={() => handleRestore('unit', u.id, u.display_label || u.unit_no)}
                                        disabled={restoring[u.id]}
                                        className="text-green-500 hover:text-green-700 disabled:opacity-50"
                                      >
                                        {restoring[u.id] ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                                      </button>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </Card>
              );
            })}
            {standaloneFloors.length > 0 && (
              <Card className="p-3">
                <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1"><Layers className="w-3.5 h-3.5" />קומות עצמאיות ({standaloneFloors.length})</p>
                <div className="space-y-1.5">
                  {standaloneFloors.map(f => (
                    <div key={f.id} className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2">
                      <div>
                        <p className="text-sm font-medium text-slate-700">{f.display_label || f.name}</p>
                        <p className="text-[11px] text-slate-400">ארכוב: {f.archived_at ? new Date(f.archived_at).toLocaleDateString('he-IL') : ''}</p>
                      </div>
                      <div className="flex items-center gap-1">
                        {renderHardDeleteButton(f, 'floor', f.id, f.display_label || f.name)}
                        <Button
                          onClick={() => handleRestore('floor', f.id, f.display_label || f.name)}
                          disabled={restoring[f.id]}
                          size="sm" variant="outline"
                          className="text-green-600 border-green-200 hover:bg-green-50 text-xs"
                        >
                          {restoring[f.id] ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <><RotateCcw className="w-3.5 h-3.5 ml-1" />שחזר</>}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}
            {standaloneUnits.length > 0 && (
              <Card className="p-3">
                <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1"><DoorOpen className="w-3.5 h-3.5" />דירות עצמאיות ({standaloneUnits.length})</p>
                <div className="flex flex-wrap gap-1.5">
                  {standaloneUnits.map(u => (
                    <div key={u.id} className="flex items-center gap-1.5 bg-slate-50 rounded-md px-2 py-1 border border-slate-200">
                      <span className="text-xs text-slate-600">{u.display_label || u.unit_no}</span>
                      <div className="flex items-center gap-0.5">
                        {renderHardDeleteButton(u, 'unit', u.id, u.display_label || u.unit_no)}
                        <button
                          onClick={() => handleRestore('unit', u.id, u.display_label || u.unit_no)}
                          disabled={restoring[u.id]}
                          className="text-green-500 hover:text-green-700 disabled:opacity-50"
                        >
                          {restoring[u.id] ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}
            {filteredBuildings.length === 0 && standaloneFloors.length === 0 && standaloneUnits.length === 0 && archiveSearch && (
              <Card className="p-6 text-center text-slate-400">
                <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">לא נמצאו תוצאות עבור "{archiveSearch}"</p>
              </Card>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {isPM && (
        <div className="flex justify-end mb-1">
          <Button onClick={() => setShowArchive(true)} variant="ghost" className="text-xs text-slate-400 hover:text-slate-600">
            <Archive className="w-3.5 h-3.5 ml-1" />ארכיון
          </Button>
        </div>
      )}
      {hardDeleteTarget && ReactDOM.createPortal(
        <div className="fixed inset-0 bg-black/60 z-[9999] flex items-center justify-center p-4" onClick={() => setHardDeleteTarget(null)}>
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6" dir="rtl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-red-700">מחיקה לצמיתות</h3>
              <button onClick={() => setHardDeleteTarget(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-red-600 mb-3">פעולה זו בלתי הפיכה. כל הנתונים ימחקו לצמיתות.</p>
            <p className="text-sm text-slate-700 mb-4">פריט: <span className="font-bold">{hardDeleteTarget.name}</span></p>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-slate-700">הקלד "{hardDeleteTarget.name}" לאישור</label>
                <input
                  type="text"
                  value={hardDeleteConfirmation}
                  onChange={e => setHardDeleteConfirmation(e.target.value)}
                  className="w-full mt-1 px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-red-500"
                  placeholder={hardDeleteTarget.name}
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={() => setHardDeleteTarget(null)} variant="outline" className="flex-1">ביטול</Button>
                <Button
                  onClick={confirmHardDelete}
                  disabled={hardDeleteLoading || hardDeleteConfirmation.trim() !== hardDeleteTarget.name.trim()}
                  className="flex-1 bg-red-600 hover:bg-red-700 text-white"
                >
                  {hardDeleteLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'מחק לצמיתות'}
                </Button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
      {stepup && ReactDOM.createPortal(
        <div className="fixed inset-0 bg-black/60 z-[9999] flex items-center justify-center p-4" onClick={() => setStepup(null)}>
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6" dir="rtl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold text-slate-800">אימות נדרש</h3>
              <button onClick={() => setStepup(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-slate-600 mb-4">קוד נשלח ל-{stepup.maskedEmail}</p>
            <div className="space-y-3">
              <input
                type="text"
                value={stepupCode}
                onChange={e => setStepupCode(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500 text-center tracking-widest"
                placeholder="קוד אימות"
                onKeyDown={e => e.key === 'Enter' && handleStepupVerify()}
              />
              <Button
                onClick={handleStepupVerify}
                disabled={stepupLoading || !stepupCode.trim()}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white"
              >
                {stepupLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'אמת'}
              </Button>
            </div>
          </div>
        </div>,
        document.body
      )}
      {hierarchy.map(building => {
        const isExpanded = expandedBuildings[building.id];
        const floors = building.floors || [];
        return (
          <Card key={building.id} className="overflow-hidden rounded-xl border-slate-200">
            <div className="flex items-center">
              <button onClick={() => toggleBuilding(building.id)}
                className="flex-1 flex items-center gap-3 p-3.5 hover:bg-slate-50 transition-colors text-right">
                {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />}
                <div className="w-9 h-9 bg-amber-50 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Building2 className="w-5 h-5 text-amber-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-base font-bold text-slate-800 truncate">
                    {building.name}
                    {building.code && <span className="text-slate-400 font-normal mr-2">({building.code})</span>}
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">{floors.length} קומות{(() => { const unitCount = floors.reduce((sum, f) => sum + (f.units || []).length, 0); return unitCount > 0 ? ` · ${unitCount} דירות` : ''; })()}{(() => { if (!isManagement || !floors.length) return null; const total = floors.length; const active = floors.filter(f => { const raw = qcStatuses[f.id]; const badge = typeof raw === 'string' ? raw : raw?.badge || 'not_started'; return badge !== 'not_started'; }).length; return active > 0 ? <span className="text-amber-600 font-medium">{` · בקרה: ${active}/${total}`}</span> : null; })()}</p>
                </div>
              </button>
              {isPM && (
                <button
                  onClick={(e) => { e.stopPropagation(); handleArchiveBuilding(building); }}
                  className="p-2.5 text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors border-r border-slate-50"
                  title="ארכב בניין"
                >
                  <Archive className="w-4 h-4" />
                </button>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); setAddingFloorTo(addingFloorTo === building.id ? null : building.id); setNewFloorName(''); setNewUnitCount('0'); if (!isExpanded) toggleBuilding(building.id); }}
                className="p-2.5 text-amber-600 hover:bg-amber-50 transition-colors border-r border-slate-50"
                title="הוסף קומה"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            {isExpanded && (
              <div className="border-t border-slate-100">
                {addingFloorTo === building.id && (
                  <div className="p-3 bg-amber-50 border-b border-amber-100">
                    <p className="text-xs font-medium text-amber-700 mb-2">הוסף קומה ל{building.name}</p>
                    <div className="flex gap-2 items-start flex-wrap">
                      <div className="flex-1 min-w-[120px]">
                        <label className="block text-[11px] font-medium text-amber-800 mb-1">שם/מספר קומה</label>
                        <input
                          type="text"
                          value={newFloorName}
                          onChange={e => setNewFloorName(e.target.value)}
                          placeholder="למשל: 1, -1, גג"
                          className="w-full text-sm border border-amber-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400"
                          onKeyDown={e => e.key === 'Enter' && handleAddFloor(building.id)}
                          autoFocus
                        />
                      </div>
                      <div className="w-28">
                        <label className="block text-[11px] font-medium text-amber-800 mb-1">מס׳ דירות בקומה</label>
                        <input
                          type="number"
                          min="0"
                          value={newUnitCount}
                          onChange={e => setNewUnitCount(e.target.value)}
                          placeholder="0"
                          className="w-full text-sm border border-amber-200 rounded-lg px-2 py-2 focus:outline-none focus:ring-2 focus:ring-amber-400 text-center"
                          onKeyDown={e => e.key === 'Enter' && handleAddFloor(building.id)}
                        />
                      </div>
                      <button
                        onClick={() => handleAddFloor(building.id)}
                        disabled={floorSaving}
                        className="bg-amber-500 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-amber-600 disabled:opacity-50 flex-shrink-0"
                      >
                        {floorSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'הוסף'}
                      </button>
                      <button onClick={() => setAddingFloorTo(null)} className="text-slate-400 hover:text-slate-600 flex-shrink-0">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
                {floors.map(floor => {
                  const isFloorExpanded = expandedFloors[floor.id];
                  const units = floor.units || [];
                  return (
                    <div key={floor.id}>
                      <div className="flex items-center border-b border-slate-50 last:border-0">
                        <button onClick={() => toggleFloor(floor.id)}
                          className="flex-1 flex items-center gap-3 py-2.5 pr-10 pl-3 hover:bg-slate-50 transition-colors text-right">
                          {isFloorExpanded ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
                          <Layers className="w-4 h-4 text-blue-500 flex-shrink-0" />
                          <span className="text-sm text-slate-700 flex-1">
                            {floor.display_label || floor.name}
                            {floor.kind && KIND_LABELS[floor.kind] && (
                              <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full mr-2 ${KIND_COLORS[floor.kind] || 'bg-slate-100 text-slate-600'}`}>
                                {KIND_LABELS[floor.kind]}
                              </span>
                            )}
                          </span>
                          <span className="text-xs text-slate-400">{units.length} דירות</span>
                        </button>
                        {isPM && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleArchiveFloor(floor); }}
                            className="p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
                            title="ארכב קומה"
                          >
                            <Archive className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {isManagement && qcStatuses[floor.id] && (() => {
                          const raw = qcStatuses[floor.id];
                          const badge = typeof raw === 'string' ? raw : raw?.badge || 'not_started';
                          return badge !== 'not_started' ? (
                            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${QC_BADGE_COLORS[badge] || QC_BADGE_COLORS.not_started}`}>
                              {qcFloorStatusLabel(badge)}
                            </span>
                          ) : null;
                        })()}
                        <button
                          onClick={(e) => { e.stopPropagation(); setAddingUnitTo(addingUnitTo === floor.id ? null : floor.id); setNewUnitNo(''); if (!isFloorExpanded) toggleFloor(floor.id); }}
                          className="p-2 ml-1 text-blue-500 hover:bg-blue-50 rounded-md transition-colors"
                          title="הוסף דירה"
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      {isFloorExpanded && (
                        <div className="pr-16 pl-3 pb-2">
                          {addingUnitTo === floor.id && (
                            <div className="flex gap-2 items-center mb-2 bg-blue-50 p-2 rounded-lg">
                              <input
                                type="number"
                                min="1"
                                value={newUnitNo}
                                onChange={e => setNewUnitNo(e.target.value)}
                                placeholder="כמות דירות"
                                className="flex-1 text-sm border border-blue-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400"
                                onKeyDown={e => e.key === 'Enter' && handleAddUnit(floor.id)}
                                autoFocus
                              />
                              <button
                                onClick={() => handleAddUnit(floor.id)}
                                disabled={unitSaving}
                                className="bg-blue-500 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
                              >
                                {unitSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'הוסף'}
                              </button>
                              <button onClick={() => setAddingUnitTo(null)} className="text-slate-400 hover:text-slate-600">
                                <X className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          )}
                          {units.length > 0 && (
                            <div className="flex flex-wrap gap-1.5">
                              {units.map(unit => (
                                <div key={unit.id} className="flex items-center gap-0.5 bg-green-50 rounded-md border border-green-200">
                                  <button
                                    onClick={() => {
                                      if (!unit.id || !projectId) return;
                                      navigate(`/projects/${projectId}/units/${unit.id}`);
                                    }}
                                    className="text-xs text-green-700 px-2 py-1 hover:bg-green-100 hover:border-green-300 active:bg-green-200 transition-colors cursor-pointer rounded-r-md"
                                  >
                                    {formatUnitLabel(unit.effective_label || unit.unit_no)}
                                  </button>
                                  {isPM && (
                                    <button
                                      onClick={(e) => { e.stopPropagation(); handleArchiveUnit(unit); }}
                                      className="p-1 text-slate-400 hover:text-red-500 transition-colors"
                                      title="ארכב דירה"
                                    >
                                      <Archive className="w-3 h-3" />
                                    </button>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                          {units.length === 0 && addingUnitTo !== floor.id && (
                            <p className="text-xs text-slate-400 py-1">אין דירות — לחץ + להוספה</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
                {floors.length === 0 && addingFloorTo !== building.id && (
                  <p className="text-xs text-slate-400 p-3 text-center">אין קומות — לחץ + להוספה</p>
                )}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
};

const formatIsraeliPhone = (phone) => {
  if (!phone) return '';
  const p = String(phone);
  if (p.startsWith('+972') && p.length === 13) {
    const d = p.slice(4);
    return `0${d.slice(0,2)}-${d.slice(2,5)}-${d.slice(5)}`;
  }
  return p;
};

const TEAM_FILTERS = [
  { key: 'all', labelKey: 'filterAll' },
  { key: 'management_team', labelKey: 'filterManagement' },
  { key: 'contractor', labelKey: 'filterContractors' },
  { key: 'project_manager', labelKey: 'filterPM' },
];

const TeamTab = ({ projectId, companies, prefillTrade, myRole, isOrgOwner, trades, onRefreshCompanies }) => {
  const { user: currentUser } = useAuth();
  const [invites, setInvites] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(!!prefillTrade);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [smsLoading, setSmsLoading] = useState({});
  const [resendLoading, setResendLoading] = useState({});
  const [drawerMember, setDrawerMember] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [invRes, memRes] = await Promise.all([
        teamInviteService.list(projectId),
        projectService.getMemberships(projectId),
      ]);
      setInvites(Array.isArray(invRes) ? invRes : []);
      setMembers(Array.isArray(memRes) ? memRes : []);
    } catch (err) {
      console.error('[TeamTab] loadData FAILED', {
        status: err?.response?.status,
        url: err?.config?.url,
        detail: err?.response?.data?.detail,
        message: err?.message,
      });
      toast.error('שגיאה בטעינת צוות');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const silentRefresh = useCallback(async () => {
    try {
      const [invRes, memRes] = await Promise.all([
        teamInviteService.list(projectId),
        projectService.getMemberships(projectId),
      ]);
      setInvites(Array.isArray(invRes) ? invRes : []);
      setMembers(Array.isArray(memRes) ? memRes : []);
    } catch (err) {
      console.warn('[TeamTab] silentRefresh FAILED (after successful action)', {
        status: err?.response?.status,
        url: err?.config?.url,
        detail: err?.response?.data?.detail,
        message: err?.message,
      });
      toast('רענון הרשימה נכשל – נסה לרענן', { icon: '⚠️', duration: 4000 });
    }
  }, [projectId]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleResend = async (inviteId) => {
    setResendLoading(prev => ({ ...prev, [inviteId]: true }));
    try {
      const result = await teamInviteService.resend(projectId, inviteId);
      const ns = result?.notification_status;
      const ds = ns?.delivery_status;
      if (ns?.channel_used === 'sms' && (ds === 'sent' || ds === 'queued')) {
        toast.success(ns?.wa_skipped ? 'נשלח ב-SMS (WhatsApp לא זמין כרגע)' : 'הזמנה נשלחה ב-SMS');
      } else if (ns?.channel_used === 'whatsapp' && ds === 'accepted') {
        toast('ממתין למסירה ב-WhatsApp...', { icon: '⏳' });
      } else if (ds === 'failed') {
        toast.error('שליחה נכשלה: ' + (ns?.reason || 'שגיאה'));
      } else {
        toast('הזמנה נשלחה מחדש', { icon: '📨' });
      }
      await silentRefresh();
    } catch (err) {
      console.error('[TeamTab] handleResend FAILED', {
        status: err?.response?.status,
        url: err?.config?.url,
        detail: err?.response?.data?.detail,
      });
      toast.error(err.response?.data?.detail || 'שגיאה בשליחה חוזרת');
    } finally {
      setTimeout(() => setResendLoading(prev => ({ ...prev, [inviteId]: false })), 3000);
    }
  };

  const handleResendSms = async (inviteId) => {
    setSmsLoading(prev => ({ ...prev, [inviteId]: true }));
    try {
      const result = await teamInviteService.resendSms(projectId, inviteId);
      const ns = result?.notification_status;
      if (ns?.delivery_status === 'sent') {
        toast.success('SMS נשלח בהצלחה');
      } else {
        toast.error('שליחת SMS נכשלה: ' + (ns?.reason || 'שגיאה'));
      }
      await silentRefresh();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 429) {
        toast.error(typeof detail === 'string' ? detail : 'נסה שוב בעוד דקה');
      } else {
        toast.error(detail || 'שגיאה בשליחת SMS');
      }
    } finally {
      setSmsLoading(prev => ({ ...prev, [inviteId]: false }));
    }
  };

  const handleCancel = async (inviteId) => {
    try {
      await teamInviteService.cancel(projectId, inviteId);
      toast.success('הזמנה בוטלה');
      await silentRefresh();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה');
    }
  };

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 text-amber-500 animate-spin" /></div>;

  const INVITE_STATUS = {
    pending: { label: 'ממתין', className: 'bg-amber-100 text-amber-700' },
    accepted: { label: 'אושר', className: 'bg-green-100 text-green-700' },
    cancelled: { label: 'בוטל', className: 'bg-red-100 text-red-700' },
  };

  const searchLower = search.toLowerCase();
  const filteredMembers = members.filter(m => {
    if (filter !== 'all' && m.role !== filter) return false;
    if (searchLower) {
      const name = (m.user_name || '').toLowerCase();
      const phone = (m.user_phone || '').toLowerCase();
      const company = (m.company_name || '').toLowerCase();
      if (!name.includes(searchLower) && !phone.includes(searchLower) && !company.includes(searchLower)) return false;
    }
    return true;
  });

  return (
    <div className="space-y-4">
      <Button onClick={() => setShowAddForm(true)} className="bg-amber-500 hover:bg-amber-600 text-white text-sm" size="sm">
        <Plus className="w-4 h-4 ml-1" />{t('teamTab', 'addMember')}
      </Button>

      <div className="flex gap-2 flex-wrap">
        {TEAM_FILTERS.map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${filter === f.key ? 'bg-amber-500 text-white' : 'border border-slate-300 text-slate-600 hover:bg-slate-50'}`}>
            {t('teamTab', f.labelKey)}
          </button>
        ))}
      </div>

      <div className="relative">
        <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder={t('teamTab', 'searchPlaceholder')}
          className="w-full pr-9 pl-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
        />
      </div>

      {filteredMembers.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-600 mb-2">{t('teamTab', 'members')} ({filteredMembers.length})</h3>
          <div className="space-y-2">
            {filteredMembers.map(m => (
              <Card key={m.user_id || m.id} className="p-3 flex items-center gap-3 cursor-pointer hover:bg-slate-50 active:bg-slate-100 transition-colors" onClick={() => setDrawerMember(m)}>
                <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
                  <Users className="w-4 h-4 text-amber-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <p className="text-sm font-medium text-slate-800 truncate">{m.user_name || m.user_id}</p>
                    {m.is_org_owner && (
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 shrink-0">בעלים</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500">
                    {tRole(m.role)}
                    {m.role === 'management_team' && m.sub_role && ` · ${tSubRole(m.sub_role)}`}
                  </p>
                  {m.role === 'contractor' && (
                    <p className="text-xs text-slate-400">
                      {m.contractor_trade_key && tTrade(m.contractor_trade_key)}
                      {m.contractor_trade_key && m.company_name && ' · '}
                      {m.company_name || ''}
                    </p>
                  )}
                  {m.user_phone && (
                    <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                      <Phone className="w-3 h-3" /><bdi className="font-mono" dir="ltr">{formatIsraeliPhone(m.user_phone)}</bdi>
                    </p>
                  )}
                </div>
                <button className="p-1.5 rounded-full hover:bg-slate-200 shrink-0" onClick={(e) => { e.stopPropagation(); setDrawerMember(m); }}>
                  <MoreVertical className="w-4 h-4 text-slate-400" />
                </button>
              </Card>
            ))}
          </div>
        </div>
      )}

      {filteredMembers.length === 0 && members.length > 0 && (
        <Card className="p-6">
          <div className="flex flex-col items-center text-slate-400">
            <Search className="w-8 h-8 mb-2" />
            <p className="text-sm font-medium">{t('teamTab', 'noResults')}</p>
          </div>
        </Card>
      )}

      {invites.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-600 mb-2">{t('teamTab', 'invites')} ({invites.length})</h3>
          <div className="space-y-2">
            {invites.map(inv => {
              const status = INVITE_STATUS[inv.status] || INVITE_STATUS.pending;
              return (
                <Card key={inv.id} className="p-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center">
                      <Phone className="w-4 h-4 text-slate-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-800 truncate">{inv.full_name || inv.target_phone || inv.phone}</p>
                      <p className="text-xs text-slate-500"><bdi className="font-mono" dir="ltr">{formatIsraeliPhone(inv.target_phone || inv.phone)}</bdi> · {tRole(inv.role)}</p>
                    </div>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${status.className}`}>{status.label}</span>
                  </div>
                  {inv.status === 'pending' && (
                    <div className="flex gap-2 mt-2 mr-11 flex-wrap">
                      <button onClick={() => handleResend(inv.id)} disabled={resendLoading[inv.id]}
                        className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 disabled:opacity-50">
                        {resendLoading[inv.id] ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                        שלח מחדש
                      </button>
                      {(currentUser?.platform_role === 'super_admin' || currentUser?.project_role === 'project_manager' || currentUser?.role === 'project_manager') && (
                        <button onClick={() => handleResendSms(inv.id)} disabled={smsLoading[inv.id]}
                          className="text-xs text-green-600 hover:text-green-700 flex items-center gap-1 disabled:opacity-50">
                          {smsLoading[inv.id] ? <Loader2 className="w-3 h-3 animate-spin" /> : <MessageSquare className="w-3 h-3" />}
                          שלח ב-SMS
                        </button>
                      )}
                      <button onClick={() => handleCancel(inv.id)} className="text-xs text-red-600 hover:text-red-700 flex items-center gap-1">
                        <XCircle className="w-3 h-3" />בטל
                      </button>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {members.length === 0 && invites.length === 0 && (
        <Card className="p-8">
          <div className="flex flex-col items-center text-slate-400">
            <Users className="w-12 h-12 mb-3" />
            <p className="text-lg font-medium">{t('teamTab', 'noMembers')}</p>
            <p className="text-sm mt-1">{t('teamTab', 'noMembersHint')}</p>
          </div>
        </Card>
      )}

      {showAddForm && (
        <AddTeamMemberForm projectId={projectId} companies={companies} onClose={() => setShowAddForm(false)} onSuccess={loadData} prefillTrade={prefillTrade} onRefreshCompanies={onRefreshCompanies} />
      )}

      <UserDrawer
        open={!!drawerMember}
        onClose={() => setDrawerMember(null)}
        member={drawerMember}
        projectId={projectId}
        currentUserRole={myRole || currentUser?.project_role}
        isCurrentUserOrgOwner={!!isOrgOwner}
        currentUserId={currentUser?.id}
        currentUserPlatformRole={currentUser?.platform_role}
        onRefresh={silentRefresh}
        companies={companies}
        trades={trades}
        onRefreshCompanies={onRefreshCompanies}
      />
    </div>
  );
};

const CompaniesTab = ({ projectId }) => {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [tradeMap, setTradeMap] = useState({});

  const loadCompanies = useCallback(async () => {
    setLoading(true);
    try {
      const [data, tradesData] = await Promise.all([
        projectCompanyService.list(projectId),
        tradeService.listForProject(projectId),
      ]);
      setCompanies(Array.isArray(data) ? data : []);
      const map = {};
      (tradesData.trades || []).forEach(t => { map[t.key] = t.label_he; });
      setTradeMap(map);
    } catch {
      toast.error('שגיאה בטעינת חברות');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadCompanies(); }, [loadCompanies]);

  const handleDelete = async (companyId) => {
    if (deleting) return;
    setDeleting(companyId);
    try {
      await projectCompanyService.remove(projectId, companyId);
      toast.success('חברה נמחקה');
      loadCompanies();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה');
    } finally {
      setDeleting(null);
    }
  };

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 text-amber-500 animate-spin" /></div>;

  return (
    <div className="space-y-4">
      <Button onClick={() => setShowAddForm(true)} className="bg-amber-500 hover:bg-amber-600 text-white text-sm" size="sm">
        <Plus className="w-4 h-4 ml-1" />הוסף חברה חדשה
      </Button>

      {companies.length === 0 ? (
        <Card className="p-8">
          <div className="flex flex-col items-center text-slate-400">
            <Briefcase className="w-12 h-12 mb-3" />
            <p className="text-lg font-medium">אין חברות</p>
            <p className="text-sm mt-1">לחץ "הוסף חברה חדשה" להתחיל</p>
          </div>
        </Card>
      ) : (
        <div className="space-y-2">
          {companies.map(c => (
            <Card key={c.id} className="p-3 flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center">
                <Briefcase className="w-4 h-4 text-indigo-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{c.name}</p>
                <p className="text-xs text-slate-500">
                  {c.trade ? (tradeMap[c.trade] || tTrade(c.trade)) : ''}
                  {c.contact_name ? ` · ${c.contact_name}` : ''}
                  {c.contact_phone ? ` · ${c.contact_phone}` : ''}
                </p>
              </div>
              <button onClick={() => handleDelete(c.id)} disabled={deleting === c.id}
                className="p-1.5 hover:bg-red-50 rounded-lg text-red-500 transition-colors">
                {deleting === c.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              </button>
            </Card>
          ))}
        </div>
      )}

      {showAddForm && <AddCompanyForm projectId={projectId} onClose={() => setShowAddForm(false)} onSuccess={loadCompanies} />}
    </div>
  );
};

const ProjectControlPage = () => {
  const { projectId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [project, setProject] = useState(null);
  const [hierarchy, setHierarchy] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hierarchyLoading, setHierarchyLoading] = useState(true);
  const [accessChecked, setAccessChecked] = useState(false);
  const [myRole, setMyRole] = useState(null);
  const [stats, setStats] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [trades, setTrades] = useState([]);
  const [showAddBuilding, setShowAddBuilding] = useState(false);
  const [showQuickSetup, setShowQuickSetup] = useState(false);
  const [showBulkFloors, setShowBulkFloors] = useState(false);
  const [showBulkUnits, setShowBulkUnits] = useState(false);
  const [showExcelImport, setShowExcelImport] = useState(false);
  const [openInviteTriggered, setOpenInviteTriggered] = useState(false);
  const [gitSha, setGitSha] = useState('');
  const [billingEnabled, setBillingEnabled] = useState(false);
  const [defectsV2Enabled, setDefectsV2Enabled] = useState(false);
  const [isOrgOwner, setIsOrgOwner] = useState(false);

  const [workMode, setWorkMode] = useState(() => {
    try {
      const saved = localStorage.getItem(`brikops_workMode_${projectId}`);
      return (saved === 'structure' || saved === 'defects') ? saved : 'structure';
    } catch { return 'structure'; }
  });
  const [showFab, setShowFab] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(`brikops_workMode_${projectId}`);
      setWorkMode((saved === 'structure' || saved === 'defects') ? saved : 'structure');
    } catch { setWorkMode('structure'); }
  }, [projectId]);

  const MGMT_TABS = billingEnabled ? [...SECONDARY_TABS, BILLING_TAB] : SECONDARY_TABS;
  const VALID_TABS = MGMT_TABS.map(t => t.id);
  const rawTab = searchParams.get('tab') || '';
  const activeTab = VALID_TABS.includes(rawTab) ? rawTab : '';
  const setActiveTab = (tab) => { setSearchParams(prev => { const next = new URLSearchParams(prev); if (tab) next.set('tab', tab); else next.delete('tab'); return next; }, { replace: true }); };

  useEffect(() => {
    const checkAccess = async () => {
      if (!user) return;
      try {
        const proj = await projectService.get(projectId);
        const role = proj.my_role;
        setMyRole(role);
        const managementRoles = ['owner', 'admin', 'project_manager', 'management_team'];
        if (!managementRoles.includes(role)) {
          toast.error('אין הרשאה למרכז ניהול — הפנייה לליקויים');
          navigate(`/projects/${projectId}/tasks`);
          return;
        }
        setAccessChecked(true);
        billingService.me().then(b => setIsOrgOwner(!!b?.is_owner)).catch(() => {});
      } catch (err) {
        if (err?.response?.status === 403) {
          toast.error('אין לך גישה לפרויקט זה');
        } else {
          toast.error('שגיאה בבדיקת הרשאות');
        }
        navigate('/projects');
      }
    };
    checkAccess();
  }, [user, projectId, navigate]);

  useEffect(() => {
    if (openInviteTriggered) return;
    const shouldOpenInvite = searchParams.get('openInvite');
    if (shouldOpenInvite === '1' && !loading) {
      setOpenInviteTriggered(true);
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        next.delete('openInvite');
        next.set('tab', 'team');
        return next;
      }, { replace: true });
    }
  }, [searchParams, loading, openInviteTriggered, setSearchParams]);

  const loadProject = useCallback(async () => {
    try {
      const data = await projectService.get(projectId);
      setProject(data);
      localStorage.setItem('lastProjectId', projectId);
    } catch {
      toast.error('שגיאה בטעינת פרויקט');
      navigate('/projects');
    } finally {
      setLoading(false);
    }
  }, [projectId, navigate]);

  const loadHierarchy = useCallback(async () => {
    setHierarchyLoading(true);
    try {
      const data = await projectService.getHierarchy(projectId);
      setHierarchy(normalizeList(data));
    } catch {
      setHierarchy([]);
    } finally {
      setHierarchyLoading(false);
    }
  }, [projectId]);

  const loadStats = useCallback(async () => {
    try {
      const data = await projectStatsService.get(projectId);
      setStats(data);
    } catch {}
  }, [projectId]);

  const loadCompanies = useCallback(async () => {
    try {
      const data = await projectCompanyService.list(projectId);
      setCompanies(Array.isArray(data) ? data : []);
    } catch {}
  }, [projectId]);

  const loadTrades = useCallback(async () => {
    try {
      const data = await tradeService.listForProject(projectId);
      setTrades((data.trades || []).map(t => ({ value: t.key, label: t.label_he })));
    } catch {}
  }, [projectId]);

  useEffect(() => {
    if (accessChecked) {
      loadProject();
      loadHierarchy();
      loadStats();
      loadCompanies();
      loadTrades();
    }
  }, [accessChecked, loadProject, loadHierarchy, loadStats, loadCompanies, loadTrades]);

  useEffect(() => {
    configService.getFeatures().then(data => {
      setBillingEnabled(!!data.feature_flags?.billing_v1_enabled);
      setDefectsV2Enabled(!!data.feature_flags?.defects_v2);
    }).catch(() => {});
    versionService.get().then(data => {
      setGitSha(data.git_sha || data.sha || data.version || '');
    }).catch(() => {});
  }, []);

  const handleRefresh = useCallback(() => {
    loadHierarchy();
    loadStats();
    loadCompanies();
    loadTrades();
  }, [loadHierarchy, loadStats, loadCompanies, loadTrades]);

  if (loading || !accessChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-amber-500 animate-spin mx-auto" />
          <p className="text-slate-500 mt-4">טוען...</p>
        </div>
      </div>
    );
  }

  if (!project) return null;

  const buildings = hierarchy;

  const workTabs = [
    { id: 'structure', label: 'מבנה', icon: Building2 },
    { id: 'qc', label: 'בקרת ביצוע', icon: ClipboardCheck, hidden: !['owner', 'admin', 'project_manager', 'management_team'].includes(myRole) },
    { id: 'defects', label: 'ליקויים', icon: AlertTriangle },
    { id: 'plans', label: 'תוכניות', icon: FileText },
  ].filter(t => !t.hidden);

  const handleWorkTab = (id) => {
    if (id === 'qc') { navigate(`/projects/${projectId}/qc`); return; }
    if (id === 'plans') { navigate(`/projects/${projectId}/plans`); return; }
    setWorkMode(id);
    if (id !== 'structure') setActiveTab('');
    try { localStorage.setItem(`brikops_workMode_${projectId}`, id); } catch {}
  };

  return (
    <div className="min-h-screen bg-slate-50 pb-20" dir="rtl">
      <header className="bg-slate-800 text-white sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-2 flex items-center gap-2">
          <button onClick={() => navigate('/projects')} className="p-1 hover:bg-slate-700 rounded-lg transition-colors" title="חזרה לפרויקטים">
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <ProjectSwitcher currentProjectId={projectId} currentProjectName={project.name} />
          </div>
          <NotificationBell />
          <button onClick={() => navigate('/settings/account')} className="p-1 hover:bg-slate-700 rounded-lg transition-colors" title="הגדרות חשבון">
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="sticky top-[40px] z-40 bg-white border-b border-slate-200">
        <div className="max-w-4xl mx-auto flex" dir="rtl">
          {workTabs.map(wt => {
            const Icon = wt.icon;
            const isActive = workMode === wt.id;
            return (
              <button key={wt.id} onClick={() => handleWorkTab(wt.id)}
                className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-sm font-semibold transition-all touch-manipulation ${isActive ? 'text-amber-700 border-b-[3px] border-amber-500' : 'text-slate-500 hover:text-slate-700 border-b-[3px] border-transparent'}`}>
                <Icon className="w-4 h-4" />
                {wt.label}
              </button>
            );
          })}
        </div>
      </div>

      {workMode === 'structure' && (
        <div className="max-w-4xl mx-auto px-4 pt-2 space-y-2">
          <KpiRow stats={stats} />

          <div className="flex gap-1 overflow-x-auto">
            {MGMT_TABS.map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(activeTab === tab.id ? '' : tab.id)}
                className={`px-3.5 py-2 rounded-full text-xs font-medium whitespace-nowrap transition-all border ${activeTab === tab.id ? 'bg-amber-100 text-amber-700 border-amber-300' : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'}`}>
                {tab.label}
              </button>
            ))}
          </div>

          {!activeTab && (
            <StructureTab hierarchy={hierarchy} hierarchyLoading={hierarchyLoading} buildings={buildings} projectId={projectId} onRefresh={handleRefresh} onAddBuilding={() => setShowAddBuilding(true)} onQuickSetup={() => setShowQuickSetup(true)} isPM={['owner', 'admin', 'project_manager'].includes(myRole)} isSuperAdmin={user?.platform_role === 'super_admin'} isManagement={['owner', 'admin', 'project_manager', 'management_team'].includes(myRole)} defectsV2Enabled={defectsV2Enabled} />
          )}

          {activeTab === 'team' && <TeamTab projectId={projectId} companies={companies} trades={trades} prefillTrade={searchParams.get('prefillTrade') || ''} myRole={myRole} isOrgOwner={isOrgOwner} onRefreshCompanies={loadCompanies} />}

          {activeTab === 'companies' && <CompaniesTab projectId={projectId} />}

          {activeTab === 'settings' && (
            <QCApproversTab projectId={projectId} canManageApprovers={['owner', 'admin', 'project_manager'].includes(myRole) || user?.platform_role === 'super_admin'} />
          )}

          {activeTab === 'billing' && billingEnabled && (
            <ProjectBillingCard projectId={projectId} userRole={myRole} canEdit={['owner', 'admin', 'project_manager'].includes(myRole) || user?.platform_role === 'super_admin'} />
          )}
        </div>
      )}

      {workMode === 'defects' && (
        <div className="max-w-4xl mx-auto px-4 pt-4 space-y-2">
          <p className="text-sm font-semibold text-slate-600 mb-3">בחר בניין לצפייה בליקויים</p>
          {hierarchyLoading ? (
            <div className="flex items-center justify-center py-12"><Loader2 className="w-8 h-8 text-amber-500 animate-spin" /></div>
          ) : hierarchy.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <Building2 className="w-10 h-10 mx-auto mb-2 opacity-50" />
              <p className="text-sm">אין בניינים בפרויקט</p>
            </div>
          ) : hierarchy.map(building => (
            <button key={building.id} onClick={() => navigate(`/projects/${projectId}/buildings/${building.id}/defects`)}
              className="w-full flex items-center gap-3 p-3.5 bg-white rounded-xl border border-slate-200 hover:border-amber-300 hover:bg-amber-50 transition-all text-right active:scale-[0.98]">
              <div className="w-9 h-9 bg-amber-50 rounded-lg flex items-center justify-center flex-shrink-0">
                <Building2 className="w-5 h-5 text-amber-500" />
              </div>
              <span className="flex-1 text-sm font-bold text-slate-800">{building.name}{building.code ? ` (${building.code})` : ''}</span>
              <ChevronRight className="w-4 h-4 text-amber-400 rotate-180" />
            </button>
          ))}
        </div>
      )}

      {showFab && <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setShowFab(false)} />}
      <div className={`fixed bottom-20 left-5 z-50 flex flex-col gap-2 transition-all ${showFab ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none'}`}>
        <button onClick={() => { setShowAddBuilding(true); setShowFab(false); }} className="flex items-center gap-2 bg-white rounded-full px-4 py-2.5 shadow-lg border border-slate-200 text-sm font-medium text-slate-700 hover:bg-amber-50 whitespace-nowrap">
          <Building2 className="w-4 h-4 text-amber-500" />הוסף בניין
        </button>
        <button onClick={() => { setShowBulkFloors(true); setShowFab(false); }} className="flex items-center gap-2 bg-white rounded-full px-4 py-2.5 shadow-lg border border-slate-200 text-sm font-medium text-slate-700 hover:bg-amber-50 whitespace-nowrap">
          <Layers className="w-4 h-4 text-blue-500" />הוסף קומות
        </button>
        <button onClick={() => { setShowBulkUnits(true); setShowFab(false); }} className="flex items-center gap-2 bg-white rounded-full px-4 py-2.5 shadow-lg border border-slate-200 text-sm font-medium text-slate-700 hover:bg-amber-50 whitespace-nowrap">
          <DoorOpen className="w-4 h-4 text-green-500" />הוסף דירות
        </button>
        <button onClick={() => { setShowExcelImport(true); setShowFab(false); }} className="flex items-center gap-2 bg-white rounded-full px-4 py-2.5 shadow-lg border border-slate-200 text-sm font-medium text-slate-700 hover:bg-amber-50 whitespace-nowrap">
          <Upload className="w-4 h-4 text-slate-500" />יבוא אקסל
        </button>
        {hierarchy.length === 0 && (
          <button onClick={() => { setShowQuickSetup(true); setShowFab(false); }} className="flex items-center gap-2 bg-green-500 rounded-full px-4 py-2.5 shadow-lg text-sm font-medium text-white hover:bg-green-600 whitespace-nowrap">
            <Zap className="w-4 h-4" />הקמה מהירה
          </button>
        )}
      </div>
      <button onClick={() => setShowFab(prev => !prev)} className={`fixed bottom-6 left-5 z-50 w-12 h-12 rounded-full flex items-center justify-center shadow-lg transition-all ${showFab ? 'bg-slate-600 rotate-45' : 'bg-amber-500 hover:bg-amber-600'}`}>
        <Plus className="w-6 h-6 text-white" />
      </button>

      {showQuickSetup && <QuickSetupWizard projectId={projectId} onClose={() => setShowQuickSetup(false)} onSuccess={handleRefresh} />}
      {showAddBuilding && <AddBuildingForm projectId={projectId} onClose={() => setShowAddBuilding(false)} onSuccess={handleRefresh} />}
      {showBulkFloors && <BulkFloorsForm projectId={projectId} buildings={buildings} onClose={() => setShowBulkFloors(false)} onSuccess={handleRefresh} />}
      {showBulkUnits && <BulkUnitsForm projectId={projectId} buildings={buildings} onClose={() => setShowBulkUnits(false)} onSuccess={handleRefresh} />}
      {showExcelImport && <ExcelImportModal projectId={projectId} onClose={() => setShowExcelImport(false)} onSuccess={handleRefresh} />}
    </div>
  );
};

export default ProjectControlPage;
