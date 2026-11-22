import React, { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { Loader2, Upload, FileText, X, CheckCircle, Plus } from 'lucide-react';
import SheetPicker from './SheetPicker';

function formatFileSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

const DEFAULT_PLAN_TYPES = [
  { value: 'standard', label: 'תוכנית כללית' },
  { value: 'tenant_changes', label: 'שינויי דיירים' },
];

// a plan is named after its file, without the extension (the same default as in the one-file form)
const planNameOf = (file) => file.name.replace(/\.[^/.]+$/, '');

// one row of the list for every chosen file
function toBulkEntries(files, discipline, maxFileSizeMb) {
  const sizeLimit = maxFileSizeMb * 1024 * 1024;
  return Array.from(files).map(f => ({
    file: f,
    id: Math.random().toString(36).slice(2),
    discipline: discipline || '',
    floor_id: '',
    unit_id: '',
    status: f.size > sizeLimit ? 'error' : 'pending',
    error: f.size > sizeLimit ? `קובץ גדול מדי (מקסימום ${maxFileSizeMb}MB)` : '',
    progress: 0,
  }));
}

// The floors of a project as options of a floor picker. The building name is part of the label only when the
// project has more than one building. The first option clears the choice.
export function floorPickerOptions(floors) {
  const manyBuildings = new Set(floors.map(f => f.building_id)).size > 1;
  return [
    { value: '', label: 'ללא קומה' },
    ...floors.map(f => {
      const name = f.display_label || f.name || `קומה ${f.floor_number || ''}`;
      return { value: f.id, label: manyBuildings && f.building_name ? `${f.building_name} · ${name}` : name };
    }),
  ];
}

const BulkPlanUploadModal = ({
  open,
  onClose,
  initialFiles = null,
  allDisciplines = [],
  getDisciplineLabel = (k) => k,
  defaultDiscipline = '',
  onDefaultDisciplineChange,
  showFloorField = false,
  floorsList = [],
  planTypes = DEFAULT_PLAN_TYPES,
  uploadFn,
  onUploadComplete,
  maxFiles = 20,
  maxFileSizeMb = 50,
  acceptedExtensions = '.pdf,.jpg,.jpeg,.png,.dwg,.dxf',
}) => {
  const [bulkFiles, setBulkFiles] = useState([]);
  const [bulkUploading, setBulkUploading] = useState(false);
  const [bulkResults, setBulkResults] = useState(null);
  const [planType, setPlanType] = useState('standard');   // one type for all the files of an upload
  const bulkFileRef = useRef(null);

  // BATCH H.1 — reset internal state when modal closes so re-open
  // is clean (matches existing closeBulkModal semantics).
  useEffect(() => {
    if (!open) {
      setBulkFiles([]);
      setBulkUploading(false);
      setBulkResults(null);
      setPlanType('standard');
      if (bulkFileRef.current) bulkFileRef.current.value = '';
    }
  }, [open]);

  // #625 — files that were already chosen in the page's upload dialog are listed as soon as this one opens
  useEffect(() => {
    if (!open || !initialFiles || initialFiles.length === 0) return;
    if (initialFiles.length > maxFiles) {
      toast.error(`ניתן להעלות עד ${maxFiles} קבצים`);
      return;
    }
    setBulkFiles(toBulkEntries(initialFiles, defaultDiscipline, maxFileSizeMb));
    // only when the dialog opens: choosing another discipline later must not rebuild the list
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  const handleBulkFileSelect = (files) => {
    const fileList = Array.from(files);
    if (fileList.length + bulkFiles.length > maxFiles) {
      toast.error(`ניתן להעלות עד ${maxFiles} קבצים`);
      return;
    }
    const newFiles = toBulkEntries(fileList, defaultDiscipline, maxFileSizeMb);
    setBulkFiles(prev => [...prev, ...newFiles]);
  };

  const removeBulkFile = (id) => {
    setBulkFiles(prev => prev.filter(f => f.id !== id));
  };

  const updateBulkFile = (id, updates) => {
    setBulkFiles(prev => prev.map(f => f.id === id ? { ...f, ...updates } : f));
  };

  const uploadOne = (bf) => uploadFn(bf.file, bf.discipline, {
    name: planNameOf(bf.file),
    plan_type: planType,
    floor_id: bf.floor_id || undefined,
    unit_id: bf.unit_id || undefined,
  });

  const handleBulkUpload = async () => {
    const toUpload = bulkFiles.filter(f => f.status === 'pending' && f.discipline);
    if (toUpload.length === 0) {
      toast.error('אין קבצים תקינים להעלאה');
      return;
    }
    setBulkUploading(true);
    let succeeded = 0;
    let failed = 0;
    const CONCURRENCY = 3;
    for (let i = 0; i < toUpload.length; i += CONCURRENCY) {
      const batch = toUpload.slice(i, i + CONCURRENCY);
      // eslint-disable-next-line no-await-in-loop
      await Promise.all(batch.map(async (bf) => {
        updateBulkFile(bf.id, { status: 'uploading', progress: 50 });
        try {
          await uploadOne(bf);
          updateBulkFile(bf.id, { status: 'done', progress: 100 });
          succeeded++;
        } catch (err) {
          updateBulkFile(bf.id, {
            status: 'error',
            error: err?.response?.data?.detail || 'שגיאה בהעלאה',
            progress: 0,
          });
          failed++;
        }
      }));
    }
    setBulkUploading(false);
    setBulkResults({ succeeded, failed, total: toUpload.length });
    if (succeeded > 0 && onUploadComplete) onUploadComplete();
  };

  const retryBulkFile = async (bf) => {
    updateBulkFile(bf.id, { status: 'uploading', progress: 50, error: '' });
    try {
      await uploadOne(bf);
      updateBulkFile(bf.id, { status: 'done', progress: 100 });
      if (onUploadComplete) onUploadComplete();
      toast.success(`${bf.file.name} הועלה בהצלחה`);
    } catch (err) {
      updateBulkFile(bf.id, {
        status: 'error',
        error: err?.response?.data?.detail || 'שגיאה בהעלאה',
        progress: 0,
      });
    }
  };

  const closeBulkModal = () => {
    if (bulkUploading) return;
    onClose();
  };

  // The discipline chosen on top applies to every file that still follows it (no discipline yet, or the previous
  // choice); a file whose discipline was set on its own row keeps it.
  const handleDefaultDisciplineChange = (val) => {
    if (val === defaultDiscipline) return;
    if (onDefaultDisciplineChange) onDefaultDisciplineChange(val);
    setBulkFiles(prev => prev.map(f => (!f.discipline || f.discipline === defaultDiscipline) ? { ...f, discipline: val } : f));
  };

  const acceptedLabel = acceptedExtensions
    .split(',').map(s => s.trim().replace('.', '').toUpperCase()).join(', ');

  const disciplineOptions = allDisciplines.map(d => ({ value: d.key, label: getDisciplineLabel(d.key) }));
  const floorOptions = showFloorField && floorsList.length > 0 ? floorPickerOptions(floorsList) : null;
  const pendingFiles = bulkFiles.filter(f => f.status === 'pending');
  const readyCount = pendingFiles.filter(f => f.discipline).length;
  const missingCount = pendingFiles.length - readyCount;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={closeBulkModal} />
      <div className="relative z-10 w-full sm:max-w-lg sm:mx-4 bg-white shadow-2xl rounded-t-2xl sm:rounded-2xl max-h-[92vh] flex flex-col" dir="rtl">
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <h3 className="text-base font-bold text-slate-800">העלאת תוכניות</h3>
          <button onClick={closeBulkModal} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>
        <div className="overflow-y-auto p-4 space-y-4">
          {bulkResults ? (
            <div className="space-y-3">
              <div className={`rounded-xl p-4 text-center ${bulkResults.failed > 0 ? 'bg-amber-50 border border-amber-200' : 'bg-green-50 border border-green-200'}`}>
                <p className="text-sm font-bold text-slate-800">הועלו {bulkResults.succeeded} מתוך {bulkResults.total}</p>
                {bulkResults.failed > 0 && <p className="text-xs text-amber-700 mt-1">{bulkResults.failed} קבצים נכשלו — ניתן לנסות שוב</p>}
              </div>
              {bulkFiles.filter(f => f.status === 'error').length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-bold text-red-600">קבצים שנכשלו:</p>
                  {bulkFiles.filter(f => f.status === 'error').map(bf => (
                    <div key={bf.id} className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                      <FileText className="w-4 h-4 text-red-400 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-red-800 truncate">{bf.file.name}</p>
                        <p className="text-xs text-red-500">{bf.error}</p>
                      </div>
                      <button onClick={() => retryBulkFile(bf)} className="px-2 py-1 bg-red-500 hover:bg-red-600 text-white text-xs rounded-lg font-bold transition-colors">
                        נסה שוב
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <button onClick={() => onClose()} className="w-full py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-sm font-bold transition-colors">
                סגור
              </button>
            </div>
          ) : (
            <>
              <div>
                <p className="text-xs font-medium text-slate-600 mb-2">תחום לכל הקבצים *</p>
                <div className="flex flex-wrap gap-2">
                  {allDisciplines.map(d => (
                    <button
                      key={d.key}
                      type="button"
                      onClick={() => handleDefaultDisciplineChange(d.key)}
                      aria-pressed={defaultDiscipline === d.key}
                      className={`min-h-[44px] px-4 text-sm rounded-full border transition-colors ${
                        defaultDiscipline === d.key
                          ? 'bg-amber-500 text-white border-amber-500'
                          : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      {getDisciplineLabel(d.key)}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs font-medium text-slate-600 mb-2">סוג</p>
                <div className="flex gap-2">
                  {planTypes.map(pt => (
                    <button
                      key={pt.value}
                      type="button"
                      onClick={() => setPlanType(pt.value)}
                      aria-pressed={planType === pt.value}
                      className={`flex-1 min-h-[44px] rounded-xl text-sm font-medium border transition-colors ${
                        planType === pt.value
                          ? (pt.value === 'tenant_changes' ? 'bg-violet-500 text-white border-violet-500' : 'bg-amber-500 text-white border-amber-500')
                          : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      {pt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div
                className="space-y-2"
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); handleBulkFileSelect(e.dataTransfer.files); }}
              >
                <input ref={bulkFileRef} type="file" accept={acceptedExtensions} multiple onChange={e => { handleBulkFileSelect(e.target.files); e.target.value = ''; }} className="hidden" id="bulk-plan-file-pick" />
                {bulkFiles.length === 0 ? (
                  <label htmlFor="bulk-plan-file-pick" className="flex flex-col items-center justify-center gap-2 w-full py-6 border-2 border-dashed border-slate-300 rounded-xl text-sm text-slate-500 cursor-pointer hover:border-amber-400 hover:text-amber-600 transition-colors">
                    <Upload className="w-6 h-6" />
                    <span className="text-xs">גרור קבצים לכאן או לחץ לבחירה</span>
                    <span className="text-xs text-slate-500 text-center px-2">{acceptedLabel} · עד {maxFiles} קבצים · עד {maxFileSizeMb}MB לקובץ</span>
                  </label>
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-bold text-slate-700">{bulkFiles.length === 1 ? 'קובץ אחד' : `${bulkFiles.length} קבצים`}</p>
                      {/* index.css forces one colour on every <label>, so the amber text sits on an inner span */}
                      <label htmlFor="bulk-plan-file-pick" className="min-h-[44px] px-2 flex items-center cursor-pointer">
                        <span className="flex items-center gap-1 text-sm font-medium text-amber-700 hover:text-amber-800 transition-colors">
                          <Plus className="w-4 h-4" />
                          הוספת קבצים
                        </span>
                      </label>
                    </div>
                    {bulkFiles.map(bf => (
                      <div key={bf.id} className={`rounded-xl border p-3 space-y-2 ${bf.status === 'error' ? 'bg-red-50 border-red-200' : bf.status === 'done' ? 'bg-green-50 border-green-200' : bf.status === 'uploading' ? 'bg-amber-50 border-amber-200' : 'bg-white border-slate-200'}`}>
                        <div className="flex items-center gap-2">
                          <FileText className={`w-4 h-4 shrink-0 ${bf.status === 'error' ? 'text-red-400' : bf.status === 'done' ? 'text-green-500' : 'text-slate-400'}`} />
                          {/* index.css sets direction: rtl on every element. A file name that starts with a Latin letter or a digit is
                              laid out left-to-right, so a long name is cut at its end and its beginning (the sheet number) stays visible. */}
                          <span style={{ direction: /^[A-Za-z0-9]/.test(bf.file.name) ? 'ltr' : 'rtl' }} className="text-sm text-slate-800 text-right truncate flex-1">{bf.file.name}</span>
                          <span className="text-xs text-slate-500">{formatFileSize(bf.file.size)}</span>
                          {bf.status === 'pending' && (
                            <button type="button" onClick={() => removeBulkFile(bf.id)} aria-label="הסרת הקובץ" className="-my-3 -ml-3 w-11 h-11 flex-shrink-0 flex items-center justify-center text-slate-400 hover:text-red-500 transition-colors">
                              <X className="w-4 h-4" />
                            </button>
                          )}
                          {bf.status === 'done' && <CheckCircle className="w-4 h-4 text-green-500" />}
                          {bf.status === 'uploading' && <Loader2 className="w-4 h-4 animate-spin text-amber-500" />}
                        </div>
                        {bf.status === 'error' && bf.error && (
                          <p className="text-xs text-red-500">{bf.error}</p>
                        )}
                        {bf.status === 'uploading' && (
                          <div className="w-full bg-amber-100 rounded-full h-1.5">
                            <div className="bg-amber-500 h-1.5 rounded-full transition-all" style={{ width: `${bf.progress}%` }} />
                          </div>
                        )}
                        {bf.status === 'pending' && (
                          <div className="grid grid-cols-9 gap-2">
                            <div className={floorOptions ? 'col-span-4 min-w-0' : 'col-span-9 min-w-0'}>
                              <SheetPicker
                                title="תחום"
                                value={bf.discipline}
                                options={disciplineOptions}
                                onChange={v => updateBulkFile(bf.id, { discipline: v })}
                                placeholder="תחום *"
                                invalid={!bf.discipline}
                              />
                            </div>
                            {floorOptions && (
                              <div className="col-span-5 min-w-0">
                                <SheetPicker
                                  title="קומה"
                                  value={bf.floor_id}
                                  options={floorOptions}
                                  onChange={v => updateBulkFile(bf.id, { floor_id: v })}
                                  placeholder="קומה"
                                />
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </>
                )}
              </div>

              {bulkFiles.length > 0 && (
                <div className="space-y-2">
                  {missingCount > 0 && (
                    <p className={`text-xs text-center ${readyCount === 0 ? 'text-slate-600' : 'text-red-600'}`}>
                      {readyCount === 0 ? 'כדי להעלות צריך לבחור תחום' : missingCount === 1 ? 'קובץ אחד בלי תחום לא יועלה' : `${missingCount} קבצים בלי תחום לא יועלו`}
                    </p>
                  )}
                  <button
                    onClick={handleBulkUpload}
                    disabled={bulkUploading || readyCount === 0}
                    className="w-full py-3 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-sm font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {bulkUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    {bulkUploading ? 'מעלה...' : readyCount === 0 ? 'העלאה' : readyCount === 1 ? 'העלה קובץ אחד' : `העלה ${readyCount} קבצים`}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default BulkPlanUploadModal;
