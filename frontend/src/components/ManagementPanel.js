import React, { useState, useEffect, useCallback } from 'react';
import { projectService, buildingService, floorService, companyService, userService, membershipService, inviteService, tradeService } from '../services/api';
import { toast } from 'sonner';
import { formatUnitLabel } from '../utils/formatters';
import {
  X, ChevronDown, ChevronRight, Loader2, Building2, Layers, DoorOpen,
  Check, Plus, Search, MoreVertical, FolderPlus, UserPlus, Briefcase,
  GitBranch, Settings, Eye, EyeOff, Phone, Send, RefreshCw, XCircle
} from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { tRole, tSubRole } from '../i18n';
import { Sheet, SheetPortal, SheetOverlay, SheetClose, SheetTitle, SheetDescription } from './ui/sheet';
import * as SheetPrimitive from '@radix-ui/react-dialog';

const normalizeList = (data) => {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  if (data && typeof data === 'object') {
    const arrKey = Object.keys(data).find(k => Array.isArray(data[k]));
    if (arrKey) return data[arrKey];
  }
  return [];
};


const PROJECT_STATUSES = [
  { value: '', label: 'הכל' },
  { value: 'active', label: 'פעיל' },
  { value: 'draft', label: 'טיוטה' },
  { value: 'suspended', label: 'מושהה' },
];

const OptionsOverlay = ({ open, options, value, onChange, onClose, label, emptyMessage }) => {
  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <SheetPortal>
        <SheetOverlay className="fixed inset-0 z-[9999] bg-black/40" />
        <SheetPrimitive.Content
          className="fixed inset-x-0 bottom-0 z-[9999] w-full max-w-lg mx-auto bg-white rounded-t-2xl shadow-2xl max-h-[60vh] flex flex-col outline-none"
          dir="rtl"
        >
          <SheetTitle className="sr-only">{label || 'בחר אפשרות'}</SheetTitle>
          <SheetDescription className="sr-only">בחירת ערך מתוך רשימת אפשרויות</SheetDescription>
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
            <SheetClose asChild>
              <button type="button" className="p-1 text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </SheetClose>
            <h3 className="text-sm font-semibold text-slate-700">{label}</h3>
            <div className="w-6" />
          </div>
          <div className="overflow-y-auto flex-1 overscroll-contain">
            {options.length === 0 ? (
              <div className="px-4 py-8 text-sm text-slate-400 text-center">
                {emptyMessage || 'אין אפשרויות'}
              </div>
            ) : (
              options.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => { onChange(opt.value); onClose(); }}
                  className={`w-full px-4 py-3 text-sm text-right flex items-center justify-between border-b border-slate-100 last:border-0 active:bg-amber-50 ${opt.value === value ? 'bg-amber-50 text-amber-700 font-medium' : 'text-slate-700'}`}
                >
                  {opt.label}
                  {opt.value === value && <Check className="w-4 h-4 text-amber-600 flex-shrink-0" />}
                </button>
              ))
            )}
          </div>
        </SheetPrimitive.Content>
      </SheetPortal>
    </Sheet>
  );
};

const SelectField = ({ label, value, onChange, options, error, icon: Icon, placeholder, isLoading, disabled, emptyMessage }) => {
  const [open, setOpen] = useState(false);
  const selectedLabel = options.find(o => o.value === value)?.label;
  const isDisabled = disabled || isLoading;
  const displayText = isLoading ? 'טוען...' : (disabled ? 'בחר שדה אב קודם' : (selectedLabel || placeholder));
  return (
    <div className="space-y-1" dir="rtl">
      {label && <label className="block text-sm font-medium text-slate-700">{label}</label>}
      <div className="relative">
        {Icon && <Icon className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none z-10" />}
        <button
          type="button"
          onClick={() => { if (!isDisabled) setOpen(true); }}
          className={`w-full ${Icon ? 'pr-10' : 'pr-3'} pl-8 py-2.5 border rounded-lg bg-white text-sm text-right ${error ? 'border-red-400' : 'border-slate-300'} ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} ${!selectedLabel && !isLoading && !disabled ? 'text-slate-400' : 'text-slate-900'}`}
        >
          {displayText}
        </button>
        {isLoading ? (
          <Loader2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-amber-500 animate-spin pointer-events-none" />
        ) : (
          <ChevronDown className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        )}
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <OptionsOverlay
        open={open}
        options={options}
        value={value}
        onChange={onChange}
        onClose={() => setOpen(false)}
        label={label || placeholder || ''}
        emptyMessage={emptyMessage}
      />
    </div>
  );
};

const BottomSheetModal = ({ isOpen, onClose, title, children }) => {
  return (
    <Sheet open={isOpen} onOpenChange={(v) => { if (!v) onClose(); }}>
      <SheetPortal>
        <SheetOverlay className="fixed inset-0 z-[9998] bg-black/50" />
        <SheetPrimitive.Content
          className="fixed inset-x-0 bottom-0 z-[9998] w-full max-w-lg mx-auto bg-white rounded-t-2xl shadow-2xl max-h-[85vh] flex flex-col outline-none"
          dir="rtl"
        >
          <SheetTitle className="sr-only">{title}</SheetTitle>
          <SheetDescription className="sr-only">טופס ניהול</SheetDescription>
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-amber-500 text-white rounded-t-2xl">
            <SheetClose asChild>
              <button type="button" className="p-1 hover:bg-amber-600 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </SheetClose>
            <h2 className="text-base font-bold">{title}</h2>
            <div className="w-6" />
          </div>
          <div className="overflow-y-auto flex-1 p-4 space-y-4 overscroll-contain">
            {children}
          </div>
        </SheetPrimitive.Content>
      </SheetPortal>
    </Sheet>
  );
};

const InputField = ({ label, value, onChange, placeholder, error, type = 'text', icon: Icon, dir = 'rtl' }) => (
  <div className="space-y-1" dir={dir}>
    {label && <label className="block text-sm font-medium text-slate-700">{label}</label>}
    <div className="relative">
      {Icon && <Icon className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none z-10" />}
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full ${Icon ? 'pr-10' : 'pr-3'} pl-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500 ${error ? 'border-red-400' : 'border-slate-300'}`}
      />
    </div>
    {error && <p className="text-xs text-red-500">{error}</p>}
  </div>
);

const TextareaField = ({ label, value, onChange, placeholder, error, rows = 3 }) => (
  <div className="space-y-1" dir="rtl">
    {label && <label className="block text-sm font-medium text-slate-700">{label}</label>}
    <textarea
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      className={`w-full px-3 py-2.5 border rounded-lg text-sm resize-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 ${error ? 'border-red-400' : 'border-slate-300'}`}
    />
    {error && <p className="text-xs text-red-500">{error}</p>}
  </div>
);

export const ManagementToggle = ({ isManageMode, setManageMode, isOwner, isPM }) => {
  if (!isOwner && !isPM) return null;
  return (
    <button
      onClick={() => setManageMode(!isManageMode)}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
        isManageMode
          ? 'bg-amber-500 text-white hover:bg-amber-600'
          : 'bg-slate-200 text-slate-600 hover:bg-slate-300'
      }`}
    >
      <Settings className="w-3.5 h-3.5" />
      {isManageMode ? 'מצב ניהול' : 'מצב עבודה'}
    </button>
  );
};

export const ProjectFilters = ({ searchQuery, setSearchQuery, statusFilter, setStatusFilter, hideTestProjects, setHideTestProjects }) => {
  return (
    <div className="space-y-2" dir="rtl">
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="חיפוש פרויקטים..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full h-10 pr-9 pl-3 text-sm text-right bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50"
          />
        </div>
        <div className="w-32">
          <SelectField
            value={statusFilter}
            onChange={setStatusFilter}
            options={PROJECT_STATUSES}
            placeholder="סטטוס"
          />
        </div>
      </div>
      <button
        type="button"
        onClick={() => setHideTestProjects(!hideTestProjects)}
        className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg transition-colors ${
          hideTestProjects
            ? 'bg-amber-100 text-amber-700'
            : 'bg-slate-100 text-slate-500'
        }`}
      >
        {hideTestProjects ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
        הסתר פרויקטי בדיקה
      </button>
    </div>
  );
};

export const ManagementFAB = ({ isManageMode, isOwner, isPM, onAction }) => {
  const [open, setOpen] = useState(false);

  if (!isManageMode) return null;

  const actions = [
    ...(isOwner ? [{ key: 'createProject', label: 'יצירת פרויקט', icon: FolderPlus }] : []),
    { key: 'addBuilding', label: 'הוספת בניין', icon: Building2 },
    { key: 'bulkFloors', label: 'הוסף קומות', icon: Layers },
    { key: 'bulkUnits', label: 'הוסף דירות', icon: DoorOpen },
    { key: 'assignPM', label: 'מינוי מנהל פרויקט', icon: UserPlus },
    { key: 'manageInvites', label: 'ניהול הזמנות', icon: Send },
    { key: 'addCompany', label: 'הוספת חברת קבלן', icon: Briefcase },
    { key: 'viewHierarchy', label: 'צפייה במבנה פרויקט', icon: GitBranch },
  ];

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 left-6 w-14 h-14 bg-amber-500 hover:bg-amber-600 text-white rounded-full shadow-lg flex items-center justify-center transition-colors z-40"
      >
        <Plus className="w-6 h-6" />
      </button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetPortal>
          <SheetOverlay className="fixed inset-0 z-[9998] bg-black/40" />
          <SheetPrimitive.Content
            className="fixed inset-x-0 bottom-0 z-[9998] w-full max-w-lg mx-auto bg-white rounded-t-2xl shadow-2xl max-h-[60vh] flex flex-col outline-none"
            dir="rtl"
          >
            <SheetTitle className="sr-only">פעולות ניהול</SheetTitle>
            <SheetDescription className="sr-only">בחירת פעולת ניהול</SheetDescription>
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-amber-500 text-white rounded-t-2xl">
              <SheetClose asChild>
                <button type="button" className="p-1 hover:bg-amber-600 rounded-lg">
                  <X className="w-5 h-5" />
                </button>
              </SheetClose>
              <h3 className="text-sm font-bold">פעולות ניהול</h3>
              <div className="w-6" />
            </div>
            <div className="overflow-y-auto flex-1 overscroll-contain">
              {actions.map(action => (
                <button
                  key={action.key}
                  type="button"
                  onClick={() => { setOpen(false); onAction(action.key); }}
                  className="w-full px-4 py-3.5 text-sm text-right flex items-center gap-3 border-b border-slate-100 last:border-0 active:bg-amber-50 text-slate-700 hover:bg-slate-50"
                >
                  <action.icon className="w-5 h-5 text-amber-500 flex-shrink-0" />
                  {action.label}
                </button>
              ))}
            </div>
          </SheetPrimitive.Content>
        </SheetPortal>
      </Sheet>
    </>
  );
};

export const ProjectCardMenu = ({ project, isOwner, isPM, canManage, onAction }) => {
  const [open, setOpen] = useState(false);

  if (!canManage) return null;

  const actions = [
    { key: 'addBuilding', label: 'הוסף בניין', icon: Building2 },
    { key: 'bulkFloors', label: 'הוסף קומות', icon: Layers },
    { key: 'bulkUnits', label: 'הוסף דירות', icon: DoorOpen },
    ...(isOwner ? [{ key: 'assignPM', label: 'מינוי PM', icon: UserPlus }] : []),
    { key: 'manageInvites', label: 'ניהול הזמנות', icon: Send },
    { key: 'manageCompanies', label: 'ניהול חברות', icon: Briefcase },
    { key: 'viewHierarchy', label: 'צפייה במבנה', icon: GitBranch },
  ];

  return (
    <>
      <button
        type="button"
        onClick={e => { e.stopPropagation(); setOpen(true); }}
        className="p-1.5 rounded-lg hover:bg-slate-200 transition-colors"
      >
        <MoreVertical className="w-4 h-4 text-slate-500" />
      </button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetPortal>
          <SheetOverlay className="fixed inset-0 z-[9998] bg-black/40" />
          <SheetPrimitive.Content
            className="fixed inset-x-0 bottom-0 z-[9998] w-full max-w-lg mx-auto bg-white rounded-t-2xl shadow-2xl max-h-[60vh] flex flex-col outline-none"
            dir="rtl"
          >
            <SheetTitle className="sr-only">{project.name}</SheetTitle>
            <SheetDescription className="sr-only">פעולות ניהול לפרויקט</SheetDescription>
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-amber-500 text-white rounded-t-2xl">
              <SheetClose asChild>
                <button type="button" className="p-1 hover:bg-amber-600 rounded-lg">
                  <X className="w-5 h-5" />
                </button>
              </SheetClose>
              <h3 className="text-sm font-bold">{project.name}</h3>
              <div className="w-6" />
            </div>
            <div className="overflow-y-auto flex-1 overscroll-contain">
              {actions.map(action => (
                <button
                  key={action.key}
                  type="button"
                  onClick={() => { setOpen(false); onAction(action.key, project); }}
                  className="w-full px-4 py-3.5 text-sm text-right flex items-center gap-3 border-b border-slate-100 last:border-0 active:bg-amber-50 text-slate-700 hover:bg-slate-50"
                >
                  <action.icon className="w-5 h-5 text-amber-500 flex-shrink-0" />
                  {action.label}
                </button>
              ))}
            </div>
          </SheetPrimitive.Content>
        </SheetPortal>
      </Sheet>
    </>
  );
};

const CreateProjectForm = ({ onClose, onSuccess }) => {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [description, setDescription] = useState('');
  const [clientName, setClientName] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  const handleSubmit = async () => {
    const errs = {};
    if (!name.trim()) errs.name = 'חובה';
    if (!code.trim()) errs.code = 'חובה';
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setSubmitting(true);
    try {
      await projectService.create({
        name: name.trim(),
        code: code.trim(),
        description: description.trim(),
        client_name: clientName.trim(),
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      toast.success('פרויקט נוצר בהצלחה');
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת פרויקט');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BottomSheetModal isOpen onClose={onClose} title="יצירת פרויקט">
      <InputField label="שם פרויקט *" value={name} onChange={setName} placeholder="הזן שם פרויקט" error={errors.name} />
      <InputField label="קוד פרויקט *" value={code} onChange={setCode} placeholder="למשל: PRJ-001" error={errors.code} />
      <TextareaField label="תיאור" value={description} onChange={setDescription} placeholder="תיאור הפרויקט" />
      <InputField label="שם לקוח" value={clientName} onChange={setClientName} placeholder="שם הלקוח" />
      <InputField label="תאריך התחלה" value={startDate} onChange={setStartDate} type="date" dir="ltr" />
      <InputField label="תאריך סיום" value={endDate} onChange={setEndDate} type="date" dir="ltr" />
      <Button
        onClick={handleSubmit}
        disabled={submitting}
        className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 rounded-lg"
      >
        {submitting ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />יוצר...</span> : 'צור פרויקט'}
      </Button>
    </BottomSheetModal>
  );
};

const AddBuildingForm = ({ modalProject, onClose, onSuccess }) => {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState(modalProject?.id || '');
  const [buildingName, setBuildingName] = useState('');
  const [buildingCode, setBuildingCode] = useState('');
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    setLoadingProjects(true);
    projectService.list()
      .then(data => setProjects(normalizeList(data)))
      .catch(() => toast.error('שגיאה בטעינת פרויקטים'))
      .finally(() => setLoadingProjects(false));
  }, []);

  const handleSubmit = async () => {
    const errs = {};
    if (!projectId) errs.projectId = 'חובה';
    if (!buildingName.trim()) errs.name = 'חובה';
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setSubmitting(true);
    try {
      await projectService.createBuilding(projectId, {
        name: buildingName.trim(),
        code: buildingCode.trim() || undefined,
      });
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
    <BottomSheetModal isOpen onClose={onClose} title="הוספת בניין">
      <SelectField
        label="פרויקט *"
        value={projectId}
        onChange={setProjectId}
        options={projects.map(p => ({ value: p.id, label: `${p.name} (${p.code})` }))}
        placeholder="בחר פרויקט"
        isLoading={loadingProjects}
        error={errors.projectId}
        icon={FolderPlus}
      />
      <InputField label="שם בניין *" value={buildingName} onChange={setBuildingName} placeholder="למשל: בניין A" error={errors.name} icon={Building2} />
      <InputField label="קוד בניין" value={buildingCode} onChange={setBuildingCode} placeholder="למשל: A" />
      <Button
        onClick={handleSubmit}
        disabled={submitting}
        className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 rounded-lg"
      >
        {submitting ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />יוצר...</span> : 'צור בניין'}
      </Button>
    </BottomSheetModal>
  );
};

const BulkFloorsForm = ({ modalProject, onClose, onSuccess }) => {
  const [projects, setProjects] = useState([]);
  const [buildings, setBuildings] = useState([]);
  const [projectId, setProjectId] = useState(modalProject?.id || '');
  const [buildingId, setBuildingId] = useState('');
  const [fromFloor, setFromFloor] = useState('');
  const [toFloor, setToFloor] = useState('');
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingBuildings, setLoadingBuildings] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    setLoadingProjects(true);
    projectService.list()
      .then(data => setProjects(normalizeList(data)))
      .catch(() => toast.error('שגיאה בטעינת פרויקטים'))
      .finally(() => setLoadingProjects(false));
  }, []);

  useEffect(() => {
    if (modalProject?.id) {
      setLoadingBuildings(true);
      projectService.getBuildings(modalProject.id)
        .then(data => setBuildings(normalizeList(data)))
        .catch(() => toast.error('שגיאה בטעינת בניינים'))
        .finally(() => setLoadingBuildings(false));
    }
  }, [modalProject]);

  const handleProjectSelect = useCallback((pid) => {
    setProjectId(pid);
    setBuildingId('');
    setBuildings([]);
    if (pid) {
      setLoadingBuildings(true);
      projectService.getBuildings(pid)
        .then(data => setBuildings(normalizeList(data)))
        .catch(() => toast.error('שגיאה בטעינת בניינים'))
        .finally(() => setLoadingBuildings(false));
    }
  }, []);

  const floorCount = fromFloor !== '' && toFloor !== '' ? Math.max(0, Number(toFloor) - Number(fromFloor) + 1) : 0;

  const handleSubmit = async () => {
    const errs = {};
    if (!projectId) errs.projectId = 'חובה';
    if (!buildingId) errs.buildingId = 'חובה';
    if (fromFloor === '') errs.fromFloor = 'חובה';
    if (toFloor === '') errs.toFloor = 'חובה';
    if (fromFloor !== '' && toFloor !== '' && Number(toFloor) < Number(fromFloor)) errs.toFloor = 'חייב להיות גדול מ-"מקומה"';
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setSubmitting(true);
    try {
      const result = await buildingService.bulkCreateFloors({
        project_id: projectId,
        building_id: buildingId,
        from_floor: Number(fromFloor),
        to_floor: Number(toFloor),
      });
      toast.success(result.message || `${floorCount} קומות נוצרו בהצלחה`);
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת קומות');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BottomSheetModal isOpen onClose={onClose} title="הוסף קומות">
      <SelectField
        label="פרויקט *"
        value={projectId}
        onChange={handleProjectSelect}
        options={projects.map(p => ({ value: p.id, label: `${p.name} (${p.code})` }))}
        placeholder="בחר פרויקט"
        isLoading={loadingProjects}
        error={errors.projectId}
        icon={FolderPlus}
      />
      <SelectField
        label="בניין *"
        value={buildingId}
        onChange={setBuildingId}
        options={buildings.map(b => ({ value: b.id, label: b.name }))}
        placeholder="בחר בניין"
        isLoading={loadingBuildings}
        disabled={!projectId}
        error={errors.buildingId}
        icon={Building2}
        emptyMessage="אין בניינים לפרויקט זה"
      />
      <div className="grid grid-cols-2 gap-3">
        <InputField label="מקומה *" value={fromFloor} onChange={setFromFloor} placeholder="למשל: 1" type="number" error={errors.fromFloor} />
        <InputField label="עד קומה *" value={toFloor} onChange={setToFloor} placeholder="למשל: 10" type="number" error={errors.toFloor} />
      </div>
      {floorCount > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-sm text-amber-700 text-center">
          הולכים ליצור {floorCount} קומות
        </div>
      )}
      <Button
        onClick={handleSubmit}
        disabled={submitting}
        className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 rounded-lg"
      >
        {submitting ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />יוצר...</span> : 'צור קומות'}
      </Button>
    </BottomSheetModal>
  );
};

const BulkUnitsForm = ({ modalProject, onClose, onSuccess }) => {
  const [projects, setProjects] = useState([]);
  const [buildings, setBuildings] = useState([]);
  const [projectId, setProjectId] = useState(modalProject?.id || '');
  const [buildingId, setBuildingId] = useState('');
  const [fromFloor, setFromFloor] = useState('');
  const [toFloor, setToFloor] = useState('');
  const [unitsPerFloor, setUnitsPerFloor] = useState('');
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingBuildings, setLoadingBuildings] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    setLoadingProjects(true);
    projectService.list()
      .then(data => setProjects(normalizeList(data)))
      .catch(() => toast.error('שגיאה בטעינת פרויקטים'))
      .finally(() => setLoadingProjects(false));
  }, []);

  useEffect(() => {
    if (modalProject?.id) {
      setLoadingBuildings(true);
      projectService.getBuildings(modalProject.id)
        .then(data => setBuildings(normalizeList(data)))
        .catch(() => toast.error('שגיאה בטעינת בניינים'))
        .finally(() => setLoadingBuildings(false));
    }
  }, [modalProject]);

  const handleProjectSelect = useCallback((pid) => {
    setProjectId(pid);
    setBuildingId('');
    setBuildings([]);
    if (pid) {
      setLoadingBuildings(true);
      projectService.getBuildings(pid)
        .then(data => setBuildings(normalizeList(data)))
        .catch(() => toast.error('שגיאה בטעינת בניינים'))
        .finally(() => setLoadingBuildings(false));
    }
  }, []);

  const floorCount = fromFloor !== '' && toFloor !== '' ? Math.max(0, Number(toFloor) - Number(fromFloor) + 1) : 0;
  const totalUnits = floorCount * (Number(unitsPerFloor) || 0);

  const handleSubmit = async () => {
    const errs = {};
    if (!projectId) errs.projectId = 'חובה';
    if (!buildingId) errs.buildingId = 'חובה';
    if (fromFloor === '') errs.fromFloor = 'חובה';
    if (toFloor === '') errs.toFloor = 'חובה';
    if (!unitsPerFloor || Number(unitsPerFloor) < 1) errs.unitsPerFloor = 'חובה';
    if (fromFloor !== '' && toFloor !== '' && Number(toFloor) < Number(fromFloor)) errs.toFloor = 'חייב להיות גדול מ-"מקומה"';
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setSubmitting(true);
    try {
      const result = await floorService.bulkCreateUnits({
        project_id: projectId,
        building_id: buildingId,
        from_floor: Number(fromFloor),
        to_floor: Number(toFloor),
        units_per_floor: Number(unitsPerFloor),
      });
      toast.success(result.message || `${totalUnits} דירות נוצרו בהצלחה`);
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת דירות');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BottomSheetModal isOpen onClose={onClose} title="הוסף דירות">
      <SelectField
        label="פרויקט *"
        value={projectId}
        onChange={handleProjectSelect}
        options={projects.map(p => ({ value: p.id, label: `${p.name} (${p.code})` }))}
        placeholder="בחר פרויקט"
        isLoading={loadingProjects}
        error={errors.projectId}
        icon={FolderPlus}
      />
      <SelectField
        label="בניין *"
        value={buildingId}
        onChange={setBuildingId}
        options={buildings.map(b => ({ value: b.id, label: b.name }))}
        placeholder="בחר בניין"
        isLoading={loadingBuildings}
        disabled={!projectId}
        error={errors.buildingId}
        icon={Building2}
        emptyMessage="אין בניינים לפרויקט זה"
      />
      <div className="grid grid-cols-2 gap-3">
        <InputField label="מקומה *" value={fromFloor} onChange={setFromFloor} placeholder="1" type="number" error={errors.fromFloor} />
        <InputField label="עד קומה *" value={toFloor} onChange={setToFloor} placeholder="10" type="number" error={errors.toFloor} />
      </div>
      <InputField label="דירות לקומה *" value={unitsPerFloor} onChange={setUnitsPerFloor} placeholder="4" type="number" error={errors.unitsPerFloor} />
      {totalUnits > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-sm text-amber-700 text-center">
          הולכים ליצור {totalUnits} דירות ב-{floorCount} קומות
        </div>
      )}
      <Button
        onClick={handleSubmit}
        disabled={submitting}
        className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 rounded-lg"
      >
        {submitting ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />יוצר...</span> : 'צור דירות'}
      </Button>
    </BottomSheetModal>
  );
};

const AssignPMForm = ({ modalProject, onClose, onSuccess }) => {
  const [activeTab, setActiveTab] = useState('existing');
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [phone, setPhone] = useState('');
  const [inviteName, setInviteName] = useState('');
  const projectId = modalProject?.id;

  useEffect(() => {
    if (!projectId || activeTab !== 'existing') return;
    setLoading(true);
    const timer = setTimeout(() => {
      projectService.getAvailablePms(projectId, search)
        .then(data => setUsers(normalizeList(data)))
        .catch(() => toast.error('שגיאה בטעינת משתמשים'))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [projectId, search, activeTab]);

  const handleAssignExisting = async (userId) => {
    setSubmitting(true);
    try {
      await projectService.assignPm(projectId, userId);
      toast.success('מנהל פרויקט מונה בהצלחה');
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה במינוי מנהל פרויקט');
    } finally {
      setSubmitting(false);
    }
  };

  const handleInvite = async () => {
    if (!inviteName.trim()) {
      toast.error('שם מלא הוא שדה חובה');
      return;
    }
    if (!phone.trim()) {
      toast.error('יש להזין מספר נייד ישראלי תקין');
      return;
    }
    setSubmitting(true);
    try {
      await inviteService.create(projectId, { phone: phone.trim(), role: 'project_manager', full_name: inviteName.trim() });
      toast.success('הזמנה נשלחה בהצלחה');
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בשליחת הזמנה');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BottomSheetModal isOpen onClose={onClose} title="מינוי מנהל פרויקט">
      <div className="flex border-b border-slate-200 -mt-2 mb-4">
        <button onClick={() => setActiveTab('existing')}
          className={`flex-1 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === 'existing' ? 'border-amber-500 text-amber-700' : 'border-transparent text-slate-500'}`}>
          בחר משתמש קיים
        </button>
        <button onClick={() => setActiveTab('invite')}
          className={`flex-1 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === 'invite' ? 'border-amber-500 text-amber-700' : 'border-transparent text-slate-500'}`}>
          הזמן בטלפון
        </button>
      </div>

      {activeTab === 'existing' ? (
        <div className="space-y-3">
          <div className="relative">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="חפש לפי שם, טלפון או אימייל..."
              className="w-full pr-10 pl-3 py-2.5 border border-slate-300 rounded-lg text-sm text-right focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
            />
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
            </div>
          ) : users.length > 0 ? (
            <div className="space-y-2 max-h-[40vh] overflow-y-auto overscroll-contain">
              {users.map(u => (
                <button key={u.id} onClick={() => handleAssignExisting(u.id)} disabled={submitting}
                  className="w-full flex items-center gap-3 p-3 rounded-lg border border-slate-200 hover:bg-amber-50 active:bg-amber-100 transition-colors text-right disabled:opacity-50">
                  <div className="w-9 h-9 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-sm font-bold flex-shrink-0">
                    {(u.name || '?')[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-slate-900 truncate">{u.name}</div>
                    <div className="text-xs text-slate-500 truncate">{u.email || (u.phone_e164 || u.phone ? <bdi className="font-mono" dir="ltr">{u.phone_e164 || u.phone}</bdi> : '')}</div>
                  </div>
                  <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded">{u.role || ''}</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 py-8 text-center">
              <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center">
                <UserPlus className="w-6 h-6 text-slate-400" />
              </div>
              <p className="text-sm text-slate-500">לא נמצאו משתמשים מתאימים</p>
              <button
                type="button"
                onClick={() => setActiveTab('invite')}
                className="text-sm font-medium text-amber-600 hover:text-amber-700"
              >
                הזמן בטלפון ←
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="space-y-1" dir="ltr">
            <label className="block text-sm font-medium text-slate-700 text-right" dir="rtl">מספר טלפון *</label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                type="tel"
                value={phone}
                onChange={e => setPhone(e.target.value)}
                placeholder="05X-XXXXXXX"
                inputMode="tel"
                dir="ltr"
                className="w-full pl-10 pr-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              />
            </div>
          </div>
          <InputField label="שם מלא *" value={inviteName} onChange={setInviteName} placeholder="שם מלא" />
          <Button
            onClick={handleInvite}
            disabled={submitting || !phone.trim() || !inviteName.trim()}
            className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 rounded-lg"
          >
            {submitting ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />שולח...</span> : <span className="flex items-center justify-center gap-2"><Send className="w-4 h-4" />שלח הזמנה</span>}
          </Button>
        </div>
      )}
    </BottomSheetModal>
  );
};

const AddCompanyForm = ({ modalProject, onClose, onSuccess }) => {
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
  const projectId = modalProject?.id;

  const fetchTrades = useCallback(() => {
    if (!projectId) {
      setTradesLoading(true);
      tradeService.list()
        .then(data => {
          const opts = (data.trades || []).map(t => ({ value: t.key, label: t.label_he }));
          setTradeOptions(opts);
        })
        .catch(() => toast.error('שגיאה בטעינת תחומים'))
        .finally(() => setTradesLoading(false));
      return;
    }
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
    if (!newTradeLabel.trim() || !projectId) return;
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

  const allFilled = name.trim() && trade && contactName.trim() && contactPhone.trim();

  const handleSubmit = async () => {
    const errs = {};
    if (!name.trim()) errs.name = 'שדה חובה';
    if (!trade) errs.trade = 'שדה חובה';
    if (!contactName.trim()) errs.contactName = 'שדה חובה';
    if (!contactPhone.trim()) errs.contactPhone = 'שדה חובה';
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setSubmitting(true);
    try {
      await companyService.create({
        name: name.trim(),
        trade,
        contact_name: contactName.trim(),
        contact_phone: contactPhone.trim(),
      });
      toast.success('חברה נוצרה בהצלחה');
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת חברה');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BottomSheetModal isOpen onClose={onClose} title="הוסף חברה חדשה">
      <InputField label="שם חברה *" value={name} onChange={setName} placeholder="למשל: חברת חשמל" error={errors.name} icon={Briefcase} />
      <SelectField
        label="תחום *"
        value={trade}
        onChange={setTrade}
        options={tradeOptions}
        placeholder="בחר..."
        error={errors.trade}
        isLoading={tradesLoading}
      />
      {projectId && !showNewTrade && (
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
            <Button
              onClick={handleAddTrade}
              disabled={creatingTrade || !newTradeLabel.trim()}
              className="flex-1 bg-amber-500 hover:bg-amber-600 text-white text-xs py-1.5 rounded-lg"
            >
              {creatingTrade ? <Loader2 className="w-3.5 h-3.5 animate-spin mx-auto" /> : 'שמור'}
            </Button>
            <Button
              onClick={() => { setShowNewTrade(false); setNewTradeLabel(''); }}
              className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs py-1.5 rounded-lg"
            >
              ביטול
            </Button>
          </div>
        </div>
      )}
      <InputField label="שם איש קשר *" value={contactName} onChange={setContactName} placeholder="שם מלא" error={errors.contactName} />
      <InputField label="טלפון *" value={contactPhone} onChange={setContactPhone} placeholder="050-1234567" type="tel" error={errors.contactPhone} />
      <Button
        onClick={handleSubmit}
        disabled={submitting || !allFilled}
        className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 rounded-lg"
      >
        {submitting ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />יוצר...</span> : 'הוסף חברה'}
      </Button>
    </BottomSheetModal>
  );
};

const HierarchyViewer = ({ modalProject, onClose }) => {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState(modalProject?.id || '');
  const [hierarchy, setHierarchy] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [expandedBuildings, setExpandedBuildings] = useState({});
  const [expandedFloors, setExpandedFloors] = useState({});

  useEffect(() => {
    setLoadingProjects(true);
    projectService.list()
      .then(data => setProjects(normalizeList(data)))
      .catch(() => toast.error('שגיאה בטעינת פרויקטים'))
      .finally(() => setLoadingProjects(false));
  }, []);

  useEffect(() => {
    if (projectId) {
      setLoading(true);
      projectService.getHierarchy(projectId)
        .then(data => {
          setHierarchy(data);
          const bIds = {};
          const buildings = normalizeList(data?.buildings || data);
          buildings.forEach(b => { bIds[b.id] = true; });
          setExpandedBuildings(bIds);
        })
        .catch(() => toast.error('שגיאה בטעינת מבנה'))
        .finally(() => setLoading(false));
    }
  }, [projectId]);

  const toggleBuilding = (id) => {
    setExpandedBuildings(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleFloor = (id) => {
    setExpandedFloors(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const buildings = normalizeList(hierarchy?.buildings || hierarchy);

  return (
    <BottomSheetModal isOpen onClose={onClose} title="מבנה פרויקט">
      <SelectField
        label="פרויקט"
        value={projectId}
        onChange={setProjectId}
        options={projects.map(p => ({ value: p.id, label: `${p.name} (${p.code})` }))}
        placeholder="בחר פרויקט"
        isLoading={loadingProjects}
        icon={FolderPlus}
      />
      {loading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
        </div>
      )}
      {!loading && projectId && buildings.length === 0 && (
        <div className="text-center py-8 text-sm text-slate-400">אין נתונים</div>
      )}
      {!loading && buildings.length > 0 && (
        <div className="space-y-1">
          {buildings.map(building => {
            const floors = normalizeList(building.floors);
            const isExpanded = expandedBuildings[building.id];
            return (
              <div key={building.id} className="border border-slate-200 rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => toggleBuilding(building.id)}
                  className="w-full flex items-center gap-2 px-3 py-2.5 bg-slate-50 hover:bg-slate-100 text-sm font-medium text-slate-800"
                >
                  {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
                  <Building2 className="w-4 h-4 text-amber-500" />
                  <span className="flex-1 text-right">{building.name}</span>
                  <span className="text-xs text-slate-400">{floors.length} קומות</span>
                </button>
                {isExpanded && (
                  <div className="pr-6 border-t border-slate-100">
                    {floors.length === 0 ? (
                      <div className="px-3 py-2 text-xs text-slate-400">(ריק)</div>
                    ) : (
                      floors.map(floor => {
                        const units = normalizeList(floor.units);
                        const isFloorExpanded = expandedFloors[floor.id];
                        return (
                          <div key={floor.id}>
                            <button
                              type="button"
                              onClick={() => toggleFloor(floor.id)}
                              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-50 text-sm text-slate-700"
                            >
                              {units.length > 0 ? (
                                isFloorExpanded ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                              ) : (
                                <div className="w-3.5" />
                              )}
                              <Layers className="w-3.5 h-3.5 text-blue-500" />
                              <span className="flex-1 text-right">{floor.name}</span>
                              <span className="text-xs text-slate-400">{units.length} דירות</span>
                            </button>
                            {isFloorExpanded && units.length > 0 && (
                              <div className="pr-6 pb-1">
                                {units.map(unit => (
                                  <div key={unit.id} className="flex items-center gap-2 px-3 py-1.5 text-xs text-slate-600">
                                    <DoorOpen className="w-3 h-3 text-green-500" />
                                    <span>{formatUnitLabel(unit.effective_label || unit.name || unit.unit_no || unit.number || '')}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </BottomSheetModal>
  );
};

const STATUS_LABELS = {
  pending: 'ממתין',
  accepted: 'אושר',
  expired: 'פג תוקף',
  cancelled: 'בוטל',
};
const STATUS_COLORS = {
  pending: 'bg-amber-100 text-amber-700',
  accepted: 'bg-green-100 text-green-700',
  expired: 'bg-slate-100 text-slate-500',
  cancelled: 'bg-red-100 text-red-700',
};
const INVITE_STATUS_TABS = [
  { value: '', label: 'הכל' },
  { value: 'pending', label: 'ממתין' },
  { value: 'accepted', label: 'אושר' },
  { value: 'expired', label: 'פג תוקף' },
  { value: 'cancelled', label: 'בוטל' },
];

const INVITE_ROLE_OPTIONS = [
  { value: 'project_manager', label: 'מנהל פרויקט' },
  { value: 'management_team', label: 'צוות ניהולי' },
  { value: 'contractor', label: 'קבלן' },
];
const SUB_ROLE_OPTIONS = [
  { value: 'site_manager', label: 'מנהל אתר' },
  { value: 'execution_engineer', label: 'מהנדס ביצוע' },
  { value: 'safety_assistant', label: 'עוזר בטיחות' },
  { value: 'work_manager', label: 'מנהל עבודה' },
  { value: 'safety_officer', label: 'ממונה בטיחות' },
];

const ManageInvitesForm = ({ modalProject, onClose, onSuccess }) => {
  const [invites, setInvites] = useState([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [actionLoading, setActionLoading] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newPhone, setNewPhone] = useState('');
  const [newName, setNewName] = useState('');
  const [newRole, setNewRole] = useState('');
  const [newSubRole, setNewSubRole] = useState('');
  const [newTradeKey, setNewTradeKey] = useState('');
  const [tradeOptions, setTradeOptions] = useState([]);
  const [creating, setCreating] = useState(false);
  const [showNewTrade, setShowNewTrade] = useState(false);
  const [newTradeLabel, setNewTradeLabel] = useState('');
  const [creatingTrade, setCreatingTrade] = useState(false);
  const projectId = modalProject?.id;

  const fetchInvites = useCallback(() => {
    if (!projectId) return;
    setLoading(true);
    inviteService.list(projectId)
      .then(data => setInvites(normalizeList(data)))
      .catch((err) => {
        console.error('[ManagementPanel] fetchInvites FAILED', {
          status: err?.response?.status,
          url: err?.config?.url,
          detail: err?.response?.data?.detail,
          message: err?.message,
        });
        toast.error('שגיאה בטעינת הזמנות');
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  const silentFetchInvites = useCallback(() => {
    if (!projectId) return;
    inviteService.list(projectId)
      .then(data => setInvites(normalizeList(data)))
      .catch((err) => {
        console.warn('[ManagementPanel] silentFetchInvites FAILED (after successful action)', {
          status: err?.response?.status,
          url: err?.config?.url,
          detail: err?.response?.data?.detail,
          message: err?.message,
        });
        toast('רענון הרשימה נכשל – נסה לרענן', { icon: '⚠️', duration: 4000 });
      });
  }, [projectId]);

  useEffect(() => { fetchInvites(); }, [fetchInvites]);

  const fetchTrades = useCallback(() => {
    if (!projectId) return;
    tradeService.listForProject(projectId)
      .then(data => {
        const opts = (data.trades || []).map(t => ({ value: t.key, label: t.label_he }));
        setTradeOptions(opts);
      })
      .catch(() => {});
  }, [projectId]);

  useEffect(() => { fetchTrades(); }, [fetchTrades]);

  const handleAddTrade = async () => {
    if (!newTradeLabel.trim() || !projectId) return;
    setCreatingTrade(true);
    try {
      const result = await tradeService.createForProject(projectId, { label_he: newTradeLabel.trim() });
      toast.success('תחום חדש נוצר בהצלחה');
      setNewTradeLabel('');
      setShowNewTrade(false);
      await fetchTrades();
      if (result.key) setNewTradeKey(result.key);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת תחום');
    } finally {
      setCreatingTrade(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) { toast.error('שם מלא הוא שדה חובה'); return; }
    if (!newPhone.trim()) { toast.error('יש להזין מספר נייד ישראלי תקין'); return; }
    if (!newRole) { toast.error('יש לבחור תפקיד'); return; }
    if (newRole === 'management_team' && !newSubRole) { toast.error('יש לבחור תת-תפקיד לצוות ניהולי'); return; }
    if (newRole === 'contractor' && !newTradeKey) { toast.error('יש לבחור מקצוע עבור קבלן'); return; }
    setCreating(true);
    try {
      const payload = { phone: newPhone.trim(), role: newRole, full_name: newName.trim() };
      if (newRole === 'management_team' && newSubRole) payload.sub_role = newSubRole;
      if (newRole === 'contractor' && newTradeKey) payload.trade_key = newTradeKey;
      await inviteService.create(projectId, payload);
      toast.success('הזמנה נוצרה בהצלחה');
      setNewPhone(''); setNewName(''); setNewRole(''); setNewSubRole(''); setNewTradeKey(''); setShowCreate(false);
      fetchInvites();
      if (onSuccess) onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת הזמנה');
    } finally {
      setCreating(false);
    }
  };

  const handleResend = async (inviteId) => {
    setActionLoading(inviteId);
    try {
      const result = await inviteService.resend(projectId, inviteId);
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
      silentFetchInvites();
    } catch (err) {
      console.error('[ManagementPanel] handleResend FAILED', {
        status: err?.response?.status,
        url: err?.config?.url,
        detail: err?.response?.data?.detail,
      });
      toast.error(err.response?.data?.detail || 'שגיאה בשליחה חוזרת');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancel = async (inviteId) => {
    setActionLoading(inviteId);
    try {
      await inviteService.cancel(projectId, inviteId);
      toast.success('הזמנה בוטלה');
      silentFetchInvites();
      if (onSuccess) onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בביטול הזמנה');
    } finally {
      setActionLoading(null);
    }
  };

  const filtered = statusFilter ? invites.filter(i => i.status === statusFilter) : invites;

  return (
    <BottomSheetModal isOpen onClose={onClose} title="ניהול הזמנות">
      <button
        type="button"
        onClick={() => setShowCreate(!showCreate)}
        className="w-full mb-3 flex items-center justify-center gap-2 py-2.5 text-sm font-medium rounded-lg border-2 border-dashed border-amber-300 text-amber-700 hover:bg-amber-50 active:bg-amber-100 transition-colors"
      >
        <UserPlus className="w-4 h-4" />
        {showCreate ? 'סגור טופס הזמנה' : 'הזמנה חדשה'}
      </button>

      {showCreate && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-3">
          <div className="space-y-1" dir="ltr">
            <label className="block text-sm font-medium text-slate-700 text-right" dir="rtl">מספר טלפון *</label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input type="tel" inputMode="tel" value={newPhone} onChange={e => setNewPhone(e.target.value)} placeholder="05X-XXXXXXX" dir="ltr"
                className="w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500" />
            </div>
          </div>
          <InputField label="שם מלא *" value={newName} onChange={setNewName} placeholder="שם מלא" />
          <SelectField
            label="תפקיד *"
            value={newRole}
            onChange={(val) => { setNewRole(val); if (val !== 'management_team') setNewSubRole(''); if (val !== 'contractor') setNewTradeKey(''); }}
            options={INVITE_ROLE_OPTIONS}
            placeholder="בחר תפקיד"
            icon={UserPlus}
          />
          {newRole === 'management_team' && (
            <SelectField
              label="תת-תפקיד *"
              value={newSubRole}
              onChange={setNewSubRole}
              options={SUB_ROLE_OPTIONS}
              placeholder="בחר תת-תפקיד"
              icon={UserPlus}
            />
          )}
          {newRole === 'contractor' && (
            <>
              <SelectField
                label="תחום *"
                value={newTradeKey}
                onChange={setNewTradeKey}
                options={tradeOptions}
                placeholder="בחר תחום"
                icon={Briefcase}
              />
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
                    <Button
                      onClick={handleAddTrade}
                      disabled={creatingTrade || !newTradeLabel.trim()}
                      className="flex-1 bg-amber-500 hover:bg-amber-600 text-white text-xs py-1.5 rounded-lg"
                    >
                      {creatingTrade ? <Loader2 className="w-3.5 h-3.5 animate-spin mx-auto" /> : 'שמור'}
                    </Button>
                    <Button
                      onClick={() => { setShowNewTrade(false); setNewTradeLabel(''); }}
                      className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs py-1.5 rounded-lg"
                    >
                      ביטול
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
          <Button
            onClick={handleCreate}
            disabled={creating || !newName.trim() || !newPhone.trim() || !newRole || (newRole === 'management_team' && !newSubRole) || (newRole === 'contractor' && !newTradeKey)}
            className="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 rounded-lg"
          >
            {creating ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />יוצר...</span> : <span className="flex items-center justify-center gap-2"><Send className="w-4 h-4" />שלח הזמנה</span>}
          </Button>
        </div>
      )}

      <div className="flex gap-1 overflow-x-auto pb-2 mb-3">
        {INVITE_STATUS_TABS.map(tab => (
          <button key={tab.value} onClick={() => setStatusFilter(tab.value)}
            className={`px-3 py-1.5 text-xs font-medium rounded-full whitespace-nowrap transition-colors ${statusFilter === tab.value ? 'bg-amber-500 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-8 text-sm text-slate-400">אין הזמנות</div>
      ) : (
        <div className="space-y-2 max-h-[50vh] overflow-y-auto overscroll-contain">
          {filtered.map(invite => (
            <div key={invite.id || invite._id} className="border border-slate-200 rounded-lg p-3 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Phone className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                    <bdi className="font-mono text-sm font-medium text-slate-900" dir="ltr">{(() => { const p = invite.target_phone || invite.phone || invite.phone_e164 || ''; if (p.startsWith('+972') && p.length === 13) { const d = p.slice(4); return `0${d.slice(0,2)}-${d.slice(2,5)}-${d.slice(5)}`; } return p; })()}</bdi>
                  </div>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <span className="text-xs text-slate-500">{tRole(invite.role)}</span>
                    {invite.sub_role && <span className="text-xs text-slate-400">• {tSubRole(invite.sub_role)}</span>}
                  </div>
                  {invite.created_at && (
                    <div className="text-xs text-slate-400 mt-1">
                      {new Date(invite.created_at).toLocaleDateString('he-IL')}
                    </div>
                  )}
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${STATUS_COLORS[invite.status] || 'bg-slate-100 text-slate-500'}`}>
                  {STATUS_LABELS[invite.status] || invite.status || ''}
                </span>
              </div>
              {invite.status === 'pending' && (
                <div className="flex gap-2 pt-1 border-t border-slate-100">
                  <button
                    onClick={() => handleResend(invite.id || invite._id)}
                    disabled={actionLoading === (invite.id || invite._id)}
                    className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {actionLoading === (invite.id || invite._id) ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                    שלח שוב
                  </button>
                  <button
                    onClick={() => handleCancel(invite.id || invite._id)}
                    disabled={actionLoading === (invite.id || invite._id)}
                    className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {actionLoading === (invite.id || invite._id) ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />}
                    ביטול
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </BottomSheetModal>
  );
};

export const ManagementModals = ({ activeModal, modalProject, onClose, onSuccess }) => {
  if (!activeModal) return null;

  switch (activeModal) {
    case 'createProject':
      return <CreateProjectForm onClose={onClose} onSuccess={onSuccess} />;
    case 'addBuilding':
      return <AddBuildingForm modalProject={modalProject} onClose={onClose} onSuccess={onSuccess} />;
    case 'bulkFloors':
      return <BulkFloorsForm modalProject={modalProject} onClose={onClose} onSuccess={onSuccess} />;
    case 'bulkUnits':
      return <BulkUnitsForm modalProject={modalProject} onClose={onClose} onSuccess={onSuccess} />;
    case 'assignPM':
      return <AssignPMForm modalProject={modalProject} onClose={onClose} onSuccess={onSuccess} />;
    case 'addCompany':
      return <AddCompanyForm modalProject={modalProject} onClose={onClose} onSuccess={onSuccess} />;
    case 'viewHierarchy':
      return <HierarchyViewer modalProject={modalProject} onClose={onClose} />;
    case 'manageInvites':
      return <ManageInvitesForm modalProject={modalProject} onClose={onClose} onSuccess={onSuccess} />;
    default:
      return null;
  }
};
