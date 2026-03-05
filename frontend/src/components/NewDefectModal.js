import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactDOM from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { projectService, buildingService, floorService, projectCompanyService } from '../services/api';
import { toast } from 'sonner';
import { formatUnitLabel } from '../utils/formatters';
import {
  X, Upload, ChevronDown, Camera, Loader2, Building2, Layers, DoorOpen, AlertTriangle, RefreshCw, Check, ImagePlus, Plus
} from 'lucide-react';
import { Button } from './ui/button';
import { tCategory } from '../i18n';

const normalizeList = (data) => {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  if (data && typeof data === 'object') {
    const arrKey = Object.keys(data).find(k => Array.isArray(data[k]));
    if (arrKey) return data[arrKey];
  }
  return [];
};

const CATEGORIES = [
  'electrical', 'plumbing', 'hvac', 'painting', 'flooring',
  'carpentry', 'masonry', 'windows', 'doors', 'general',
  'bathroom_cabinets', 'finishes', 'structural', 'aluminum',
  'metalwork', 'glazing', 'carpentry_kitchen'
].map(key => ({ value: key, label: tCategory(key) }));

const PRIORITIES = [
  { value: 'low', label: 'נמוך', color: 'text-slate-500' },
  { value: 'medium', label: 'בינוני', color: 'text-blue-600' },
  { value: 'high', label: 'גבוה', color: 'text-amber-600' },
  { value: 'critical', label: 'קריטי', color: 'text-red-600' },
];

const OptionsOverlay = ({ open, options, value, onChange, onClose, label, emptyMessage }) => {
  if (!open) return null;
  return ReactDOM.createPortal(
    <div className="fixed inset-0 z-[9999] flex items-end justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" />
      <div
        className="relative w-full max-w-lg bg-white rounded-t-2xl shadow-2xl max-h-[60vh] flex flex-col animate-in slide-in-from-bottom duration-200"
        dir="rtl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
          <button type="button" onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
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
      </div>
    </div>,
    document.body
  );
};

const SelectField = ({ label, value, onChange, options, error, icon: Icon, placeholder, isLoading, disabled, hasError, onRetry, emptyMessage }) => {
  const [open, setOpen] = useState(false);
  const selectedLabel = options.find(o => o.value === value)?.label;
  const isDisabled = disabled || isLoading;
  const displayText = isLoading ? 'טוען...' : (disabled ? 'בחר שדה אב קודם' : (selectedLabel || placeholder));

  return (
    <div className="space-y-1" dir="rtl">
      <label className="block text-sm font-medium text-slate-700">{label}</label>
      <div className="relative">
        {Icon && <Icon className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none z-10" />}
        <button
          type="button"
          onClick={() => { if (!isDisabled) setOpen(true); }}
          className={`w-full ${Icon ? 'pr-10' : 'pr-3'} pl-8 py-2.5 border rounded-lg bg-white text-sm text-right focus:ring-2 focus:ring-amber-500 focus:border-amber-500 ${error ? 'border-red-400' : 'border-slate-300'} ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} ${!selectedLabel && !isLoading && !disabled ? 'text-slate-400' : 'text-slate-900'}`}
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
      {!isLoading && !disabled && !hasError && options.length === 0 && emptyMessage && (
        <p className="text-xs text-slate-500 mt-1">{emptyMessage}</p>
      )}
      {hasError && onRetry && (
        <button type="button" onClick={onRetry}
          className="flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700 mt-1">
          <RefreshCw className="w-3 h-3" />
          שגיאה בטעינה - לחץ לנסות שוב
        </button>
      )}
      <OptionsOverlay
        open={open}
        options={options}
        value={value}
        onChange={onChange}
        onClose={() => setOpen(false)}
        label={label}
        emptyMessage={emptyMessage}
      />
    </div>
  );
};

const NewDefectModal = ({ isOpen, onClose, onSuccess, prefillData }) => {
  const navigate = useNavigate();
  const hasPrefill = !!(prefillData && prefillData.project_id && prefillData.unit_id);

  const [projectId, setProjectId] = useState('');
  const [buildingId, setBuildingId] = useState('');
  const [floorId, setFloorId] = useState('');
  const [unitId, setUnitId] = useState('');
  const [category, setCategory] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('medium');
  const [companyId, setCompanyId] = useState('');
  const [assigneeId, setAssigneeId] = useState('');

  const [images, setImages] = useState([]);
  const [projects, setProjects] = useState([]);
  const [buildings, setBuildings] = useState([]);
  const [floors, setFloors] = useState([]);
  const [units, setUnits] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [contractors, setContractors] = useState([]);
  const [projectMembers, setProjectMembers] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  const [loading, setLoading] = useState({});
  const [loadError, setLoadError] = useState({});

  const loadProjects = useCallback(() => {
    setLoading(l => ({ ...l, projects: true }));
    setLoadError(e => ({ ...e, projects: false }));
    projectService.list()
      .then(data => { setProjects(normalizeList(data)); })
      .catch(err => { console.error('Failed to load projects:', err); toast.error('שגיאה בטעינת פרויקטים'); setLoadError(e => ({ ...e, projects: true })); })
      .finally(() => setLoading(l => ({ ...l, projects: false })));
  }, []);

  const loadCompanies = useCallback((pid) => {
    if (!pid) return;
    setLoading(l => ({ ...l, companies: true }));
    setLoadError(e => ({ ...e, companies: false }));
    Promise.all([
      projectCompanyService.list(pid),
      projectService.getMemberships(pid),
    ])
      .then(([compData, memData]) => {
        setCompanies(normalizeList(compData));
        setProjectMembers(normalizeList(memData));
      })
      .catch(err => { console.error('Failed to load companies/members:', err); toast.error('שגיאה בטעינת חברות'); setLoadError(e => ({ ...e, companies: true })); })
      .finally(() => setLoading(l => ({ ...l, companies: false })));
  }, []);

  useEffect(() => {
    if (isOpen) {
      if (hasPrefill) {
        setProjectId(prefillData.project_id);
        setBuildingId(prefillData.building_id);
        setFloorId(prefillData.floor_id);
        setUnitId(prefillData.unit_id);
        loadCompanies(prefillData.project_id);
      }
      if (!hasPrefill) {
        loadProjects();
      }
    }
  }, [isOpen, hasPrefill, prefillData, loadProjects, loadCompanies]);

  const loadBuildings = useCallback((pid) => {
    if (!pid) return;
    setLoading(l => ({ ...l, buildings: true }));
    setLoadError(e => ({ ...e, buildings: false }));
    projectService.getBuildings(pid)
      .then(data => { setBuildings(normalizeList(data)); })
      .catch(err => { console.error('Failed to load buildings:', err); toast.error('שגיאה בטעינת בניינים'); setLoadError(e => ({ ...e, buildings: true })); })
      .finally(() => setLoading(l => ({ ...l, buildings: false })));
  }, []);

  const loadFloors = useCallback((bid) => {
    if (!bid) return;
    setLoading(l => ({ ...l, floors: true }));
    setLoadError(e => ({ ...e, floors: false }));
    buildingService.getFloors(bid)
      .then(data => { setFloors(normalizeList(data)); })
      .catch(err => { console.error('Failed to load floors:', err); toast.error('שגיאה בטעינת קומות'); setLoadError(e => ({ ...e, floors: true })); })
      .finally(() => setLoading(l => ({ ...l, floors: false })));
  }, []);

  const loadUnits = useCallback((fid) => {
    if (!fid) return;
    setLoading(l => ({ ...l, units: true }));
    setLoadError(e => ({ ...e, units: false }));
    floorService.getUnits(fid)
      .then(data => { setUnits(normalizeList(data)); })
      .catch(err => { console.error('Failed to load units:', err); toast.error('שגיאה בטעינת דירות'); setLoadError(e => ({ ...e, units: true })); })
      .finally(() => setLoading(l => ({ ...l, units: false })));
  }, []);

  const handleProjectChange = useCallback((v) => {
    setProjectId(v);
    setBuildingId('');
    setFloorId('');
    setUnitId('');
    setCompanyId('');
    setAssigneeId('');
    setBuildings([]);
    setFloors([]);
    setUnits([]);
    setCompanies([]);
    setContractors([]);
    setProjectMembers([]);
    if (v) {
      loadBuildings(v);
      loadCompanies(v);
    }
  }, [loadBuildings, loadCompanies]);

  const handleBuildingChange = useCallback((v) => {
    setBuildingId(v);
    setFloorId('');
    setUnitId('');
    setFloors([]);
    setUnits([]);
    if (v) {
      loadFloors(v);
    }
  }, [loadFloors]);

  const handleFloorChange = useCallback((v) => {
    setFloorId(v);
    setUnitId('');
    setUnits([]);
    if (v) {
      loadUnits(v);
    }
  }, [loadUnits]);

  const handleCategoryChange = useCallback((v) => {
    setCategory(v);
    setCompanyId('');
    setAssigneeId('');
  }, []);

  const handleCompanyChange = useCallback((v) => {
    setCompanyId(v);
    setAssigneeId('');
  }, []);

  useEffect(() => {
    if (companyId && projectMembers.length > 0) {
      const matched = projectMembers.filter(m =>
        m.role === 'contractor' &&
        (m.company_id === companyId || m.user_company_id === companyId)
      );
      setContractors(matched);
    } else if (!companyId) {
      setContractors([]);
    }
  }, [companyId, projectMembers]);

  const filteredCompanies = category
    ? companies.filter(c =>
        c.trade === category ||
        (c.specialties && c.specialties.includes(category))
      )
    : companies;

  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);

  const handleImageAdd = useCallback((e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    const newImages = files.map(file => ({
      file,
      preview: URL.createObjectURL(file),
      name: file.name,
    }));
    setImages(prev => [...prev, ...newImages]);
    e.target.value = '';
  }, []);

  const removeImage = useCallback((index) => {
    setImages(prev => {
      URL.revokeObjectURL(prev[index].preview);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  const validate = useCallback(() => {
    const errs = {};
    if (!projectId) errs.project_id = 'חובה';
    if (!buildingId) errs.building_id = 'חובה';
    if (!floorId) errs.floor_id = 'חובה';
    if (!unitId) errs.unit_id = 'חובה';
    if (!category) errs.category = 'חובה';
    if (!title.trim()) errs.title = 'חובה';
    if (!description.trim()) errs.description = 'חובה';
    if (!companyId) errs.company_id = 'חובה';
    if (!assigneeId) errs.assignee_id = 'חובה';
    if (images.length === 0) errs.images = 'נדרשת לפחות תמונה אחת';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }, [projectId, buildingId, floorId, unitId, category, title, description, companyId, assigneeId, images]);

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);

    const withTimeout = (promise, ms, stepName) =>
      Promise.race([
        promise,
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error(`שגיאת זמן בשלב: ${stepName} — נסה שוב`)), ms)
        ),
      ]);

    try {
      const taskData = {
        project_id: projectId,
        building_id: buildingId,
        floor_id: floorId,
        unit_id: unitId,
        category: category,
        title: title,
        description: description,
        priority: priority,
      };
      const { taskService } = await import('../services/api');

      console.log('Step 1: creating task…');
      const task = await withTimeout(taskService.create(taskData), 30000, 'יצירת ליקוי');
      console.log('Step 1: task created id=' + task.id);

      console.log('Step 2: uploading ' + images.length + ' images…');
      const uploadPromises = images.map(img => taskService.uploadAttachment(task.id, img.file));
      await withTimeout(Promise.all(uploadPromises), 60000, 'העלאת תמונות');
      console.log('Step 2: uploads done');

      console.log('Step 3: assigning contractor…');
      const assignResult = await withTimeout(taskService.assign(task.id, {
        company_id: companyId,
        assignee_id: assigneeId,
      }), 30000, 'שיוך קבלן');
      console.log('Step 3: assigned');

      toast.success('הליקוי נוצר בהצלחה!');

      if (assignResult?.notification_status?.sent) {
        const ch = assignResult.notification_status.channel;
        if (ch === 'whatsapp') {
          toast.success('נשלחה הודעה לקבלן ב-WhatsApp');
        } else if (ch === 'sms') {
          toast.success('נשלחה SMS לקבלן (fallback)');
        } else {
          toast.success('נשלחה הודעה לקבלן');
        }
      } else if (assignResult?.notification_status && !assignResult.notification_status.sent) {
        toast.info('לא ניתן לשלוח הודעה לקבלן כרגע');
      }
      images.forEach(img => URL.revokeObjectURL(img.preview));
      setProjectId('');
      setBuildingId('');
      setFloorId('');
      setUnitId('');
      setCategory('');
      setTitle('');
      setDescription('');
      setPriority('medium');
      setCompanyId('');
      setAssigneeId('');
      setImages([]);
      setErrors({});
      onSuccess(task.id);
    } catch (err) {
      console.error('handleSubmit error:', err);
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : (typeof detail === 'object' && detail?.message ? detail.message : err.message || 'שגיאה ביצירת הליקוי');
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 overflow-y-auto p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg my-8 overflow-hidden">
        <div className="bg-amber-500 text-white px-6 py-4 flex items-center justify-between">
          <button onClick={onClose} className="p-1 hover:bg-amber-600 rounded-lg transition-colors">
            <X className="w-5 h-5" />
          </button>
          <h2 className="text-lg font-bold">{hasPrefill ? `ליקוי חדש — ${formatUnitLabel(prefillData.unit_label)}` : 'ליקוי חדש'}</h2>
        </div>

        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          {hasPrefill ? (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2">
              <h3 className="text-sm font-semibold text-amber-800 flex items-center gap-2 justify-end">
                <span>מיקום (נעול)</span>
                <Building2 className="w-4 h-4" />
              </h3>
              <div className="grid grid-cols-2 gap-2 text-sm" dir="rtl">
                <div className="flex items-center gap-1.5 text-slate-700">
                  <Building2 className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                  <span className="truncate">{prefillData.project_name}</span>
                </div>
                <div className="flex items-center gap-1.5 text-slate-700">
                  <Building2 className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                  <span className="truncate">{prefillData.building_name}</span>
                </div>
                <div className="flex items-center gap-1.5 text-slate-700">
                  <Layers className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                  <span className="truncate">{prefillData.floor_name}</span>
                </div>
                <div className="flex items-center gap-1.5 text-slate-700">
                  <DoorOpen className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                  <span className="truncate">{formatUnitLabel(prefillData.unit_label)}</span>
                </div>
              </div>
            </div>
          ) : (
          <div className="bg-slate-50 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-semibold text-slate-600 flex items-center gap-2 justify-end">
              <span>מיקום</span>
              <Building2 className="w-4 h-4" />
            </h3>
            <SelectField
              label="פרויקט *"
              value={projectId}
              onChange={handleProjectChange}
              options={projects.map(p => ({ value: p.id, label: `${p.name} (${p.code})` }))}
              error={errors.project_id}
              placeholder="בחר פרויקט"
              isLoading={loading.projects}
              hasError={loadError.projects}
              onRetry={loadProjects}
              emptyMessage="אין פרויקטים זמינים"
            />
            <SelectField
              label="בניין *"
              value={buildingId}
              onChange={handleBuildingChange}
              options={buildings.map(b => ({ value: b.id, label: b.name }))}
              error={errors.building_id}
              icon={Building2}
              placeholder="בחר בניין"
              isLoading={loading.buildings}
              disabled={!projectId}
              hasError={loadError.buildings}
              onRetry={() => projectId && loadBuildings(projectId)}
              emptyMessage="אין בניינים לפרויקט זה"
            />
            <div className="grid grid-cols-2 gap-3">
              <SelectField
                label="קומה *"
                value={floorId}
                onChange={handleFloorChange}
                options={floors.map(f => ({ value: f.id, label: f.name }))}
                error={errors.floor_id}
                icon={Layers}
                placeholder="בחר קומה"
                isLoading={loading.floors}
                disabled={!buildingId}
                hasError={loadError.floors}
                onRetry={() => buildingId && loadFloors(buildingId)}
                emptyMessage="אין קומות לבניין זה"
              />
              <SelectField
                label="יחידה *"
                value={unitId}
                onChange={v => setUnitId(v)}
                options={units.map(u => ({ value: u.id, label: formatUnitLabel(u.unit_no) }))}
                error={errors.unit_id}
                icon={DoorOpen}
                placeholder="בחר יחידה"
                isLoading={loading.units}
                disabled={!floorId}
                hasError={loadError.units}
                onRetry={() => floorId && loadUnits(floorId)}
                emptyMessage="אין דירות לקומה זו"
              />
            </div>
          </div>
          )}

          <div className="space-y-3">
            <SelectField
              label="קטגוריה *"
              value={category}
              onChange={handleCategoryChange}
              options={CATEGORIES}
              error={errors.category}
              placeholder="בחר קטגוריה"
            />
            <div className="space-y-1" dir="rtl">
              <label className="block text-sm font-medium text-slate-700">כותרת *</label>
              <input
                type="text"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="תאר את הליקוי בקצרה"
                className={`w-full px-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500 ${errors.title ? 'border-red-400' : 'border-slate-300'}`}
              />
              {errors.title && <p className="text-xs text-red-500">{errors.title}</p>}
            </div>
            <div className="space-y-1" dir="rtl">
              <label className="block text-sm font-medium text-slate-700">תיאור *</label>
              <textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="תאר את הליקוי בפירוט"
                rows={3}
                className={`w-full px-3 py-2.5 border rounded-lg text-sm resize-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 ${errors.description ? 'border-red-400' : 'border-slate-300'}`}
              />
              {errors.description && <p className="text-xs text-red-500">{errors.description}</p>}
            </div>
            <SelectField
              label="עדיפות"
              value={priority}
              onChange={v => setPriority(v)}
              options={PRIORITIES}
              icon={AlertTriangle}
              placeholder="בחר עדיפות"
            />
          </div>

          <div className="bg-slate-50 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-semibold text-slate-600 text-right">שיוך קבלן</h3>
            {companies.length === 0 && !loading.companies ? (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-center space-y-2">
                <p className="text-sm text-amber-800 font-medium">אין חברות בפרויקט</p>
                <p className="text-xs text-amber-600">כדי להקצות ליקוי לקבלן יש להוסיף חברה.</p>
                <Button
                  onClick={() => { onClose(); if (projectId) navigate(`/projects/${projectId}/control?tab=companies`); }}
                  className="bg-amber-500 hover:bg-amber-600 text-white text-sm px-4 py-2 rounded-lg"
                  disabled={!projectId}
                >
                  <Plus className="w-4 h-4 ml-1 inline" />
                  הוסף חברה
                </Button>
              </div>
            ) : (
              <>
                <SelectField
                  label="חברה *"
                  value={companyId}
                  onChange={handleCompanyChange}
                  options={filteredCompanies.map(c => ({ value: c.id, label: c.name }))}
                  error={errors.company_id}
                  placeholder={category ? 'בחר חברה (מסונן לפי קטגוריה)' : 'בחר קטגוריה קודם'}
                  isLoading={loading.companies}
                  disabled={!category}
                  emptyMessage={category && filteredCompanies.length === 0 ? 'אין חברות בתחום זה' : undefined}
                />
                <SelectField
                  label="קבלן מבצע *"
                  value={assigneeId}
                  onChange={v => setAssigneeId(v)}
                  options={contractors.map(m => ({ value: m.user_id, label: m.user_name || m.name || 'קבלן' }))}
                  error={errors.assignee_id}
                  placeholder={companyId ? 'בחר קבלן' : 'בחר חברה קודם'}
                  isLoading={loading.contractors}
                  disabled={!companyId}
                  emptyMessage={companyId && !loading.contractors ? 'אין קבלנים משויכים. יש לשייך קבלן לחברה/תחום.' : undefined}
                />
              </>
            )}
          </div>

          <div className="space-y-2" dir="rtl">
            <label className="block text-sm font-medium text-slate-700">
              תמונות * <span className="text-xs text-slate-400">(לפחות 1)</span>
            </label>
            <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" onChange={handleImageAdd} className="hidden" />
            <input ref={galleryInputRef} type="file" accept="image/*" multiple onChange={handleImageAdd} className="hidden" />
            {images.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2">
                {images.map((img, i) => (
                  <div key={i} className="relative w-20 h-20 rounded-lg overflow-hidden border border-slate-200 group">
                    <img src={img.preview} alt="" className="w-full h-full object-cover" />
                    <button
                      onClick={() => removeImage(i)}
                      className="absolute top-0.5 right-0.5 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => cameraInputRef.current?.click()}
                className={`flex-1 flex flex-col items-center justify-center gap-1 py-3 rounded-lg border-2 border-dashed transition-colors cursor-pointer hover:bg-amber-50 active:bg-amber-100 ${errors.images ? 'border-red-400' : 'border-amber-300'}`}
              >
                <Camera className="w-6 h-6 text-amber-500" />
                <span className="text-xs font-medium text-amber-700">צלם תמונה</span>
              </button>
              <button
                type="button"
                onClick={() => galleryInputRef.current?.click()}
                className={`flex-1 flex flex-col items-center justify-center gap-1 py-3 rounded-lg border-2 border-dashed transition-colors cursor-pointer hover:bg-slate-50 active:bg-slate-100 ${errors.images ? 'border-red-400' : 'border-slate-300'}`}
              >
                <ImagePlus className="w-6 h-6 text-slate-400" />
                <span className="text-xs font-medium text-slate-600">בחר מגלריה</span>
              </button>
            </div>
            {errors.images && <p className="text-xs text-red-500">{errors.images}</p>}
          </div>
        </div>

        <div className="border-t px-6 py-4 flex gap-3" dir="rtl">
          <Button
            onClick={handleSubmit}
            disabled={submitting}
            className="flex-1 bg-amber-500 hover:bg-amber-600 text-white font-medium py-2.5 rounded-lg"
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                יוצר ליקוי...
              </span>
            ) : (
              'צור ליקוי'
            )}
          </Button>
          <Button
            onClick={onClose}
            variant="outline"
            disabled={submitting}
            className="px-6 py-2.5 rounded-lg"
          >
            ביטול
          </Button>
        </div>
      </div>
    </div>
  );
};

export default NewDefectModal;
