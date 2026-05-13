import React, { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { Loader2, Upload, FileText, X, CheckCircle } from 'lucide-react';

function formatFileSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

const DEFAULT_PLAN_TYPES = [
  { value: 'standard', label: 'כללית' },
  { value: 'tenant_changes', label: 'שינויי דיירים' },
];

const BulkPlanUploadModal = ({
  open,
  onClose,
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
  const bulkFileRef = useRef(null);

  // BATCH H.1 — reset internal state when modal closes so re-open
  // is clean (matches existing closeBulkModal semantics).
  useEffect(() => {
    if (!open) {
      setBulkFiles([]);
      setBulkUploading(false);
      setBulkResults(null);
      if (bulkFileRef.current) bulkFileRef.current.value = '';
    }
  }, [open]);

  if (!open) return null;

  const handleBulkFileSelect = (files) => {
    const fileList = Array.from(files);
    if (fileList.length + bulkFiles.length > maxFiles) {
      toast.error(`ניתן להעלות עד ${maxFiles} קבצים`);
      return;
    }
    const sizeLimit = maxFileSizeMb * 1024 * 1024;
    const newFiles = fileList.map(f => ({
      file: f,
      id: Math.random().toString(36).slice(2),
      discipline: defaultDiscipline || '',
      floor_id: '',
      unit_id: '',
      plan_type: 'standard',
      status: f.size > sizeLimit ? 'error' : 'pending',
      error: f.size > sizeLimit ? `קובץ גדול מדי (מקסימום ${maxFileSizeMb}MB)` : '',
      progress: 0,
    }));
    setBulkFiles(prev => [...prev, ...newFiles]);
  };

  const removeBulkFile = (id) => {
    setBulkFiles(prev => prev.filter(f => f.id !== id));
  };

  const updateBulkFile = (id, updates) => {
    setBulkFiles(prev => prev.map(f => f.id === id ? { ...f, ...updates } : f));
  };

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
          await uploadFn(bf.file, bf.discipline, {
            plan_type: bf.plan_type || 'standard',
            floor_id: bf.floor_id || undefined,
            unit_id: bf.unit_id || undefined,
          });
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
      await uploadFn(bf.file, bf.discipline, {
        plan_type: bf.plan_type || 'standard',
        floor_id: bf.floor_id || undefined,
        unit_id: bf.unit_id || undefined,
      });
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

  const handleDefaultDisciplineChange = (val) => {
    if (onDefaultDisciplineChange) onDefaultDisciplineChange(val);
    setBulkFiles(prev => prev.map(f => f.discipline ? f : { ...f, discipline: val }));
  };

  const acceptedLabel = acceptedExtensions
    .split(',').map(s => s.trim().replace('.', '').toUpperCase()).join(', ');

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={closeBulkModal} />
      <div className="relative z-10 w-full sm:max-w-lg sm:mx-4 bg-white shadow-2xl rounded-t-2xl sm:rounded-2xl max-h-[92vh] flex flex-col" dir="rtl">
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <h3 className="text-base font-bold text-slate-800">העלאה מרובה</h3>
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
                        <p className="text-[10px] text-red-500">{bf.error}</p>
                      </div>
                      <button onClick={() => retryBulkFile(bf)} className="px-2 py-1 bg-red-500 hover:bg-red-600 text-white text-[10px] rounded-lg font-bold transition-colors">
                        נסה שוב
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <button onClick={() => onClose()} className="w-full py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-sm font-bold transition-colors">
                סגור
              </button>
            </div>
          ) : (
            <>
              <div>
                <label className="text-xs font-medium text-slate-600 mb-1.5 block">תחום ברירת מחדל</label>
                <select
                  value={defaultDiscipline}
                  onChange={e => handleDefaultDisciplineChange(e.target.value)}
                  className="w-full h-10 px-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-indigo-300"
                >
                  <option value="">בחר תחום</option>
                  {allDisciplines.map(d => (
                    <option key={d.key} value={d.key}>{getDisciplineLabel(d.key)}</option>
                  ))}
                </select>
              </div>

              <div
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); handleBulkFileSelect(e.dataTransfer.files); }}
              >
                <input ref={bulkFileRef} type="file" accept={acceptedExtensions} multiple onChange={e => { handleBulkFileSelect(e.target.files); e.target.value = ''; }} className="hidden" id="bulk-plan-file-pick" />
                <label htmlFor="bulk-plan-file-pick" className="flex flex-col items-center justify-center gap-2 w-full py-6 border-2 border-dashed border-indigo-300 rounded-xl text-sm text-indigo-500 cursor-pointer hover:border-indigo-400 hover:bg-indigo-50/50 transition-colors">
                  <Upload className="w-6 h-6" />
                  <span className="text-xs">גרור קבצים לכאן או לחץ לבחירה</span>
                  <span className="text-[10px] text-slate-400">{acceptedLabel} · עד {maxFiles} קבצים · עד {maxFileSizeMb}MB לקובץ</span>
                </label>
              </div>

              {bulkFiles.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-bold text-slate-600">{bulkFiles.length} קבצים נבחרו</p>
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {bulkFiles.map(bf => (
                      <div key={bf.id} className={`rounded-xl border p-3 space-y-2 ${bf.status === 'error' ? 'bg-red-50 border-red-200' : bf.status === 'done' ? 'bg-green-50 border-green-200' : bf.status === 'uploading' ? 'bg-indigo-50 border-indigo-200' : 'bg-white border-slate-200'}`}>
                        <div className="flex items-center gap-2">
                          <FileText className={`w-4 h-4 shrink-0 ${bf.status === 'error' ? 'text-red-400' : bf.status === 'done' ? 'text-green-500' : 'text-slate-400'}`} />
                          <span className="text-xs text-slate-700 truncate flex-1">{bf.file.name}</span>
                          <span className="text-[10px] text-slate-400">{formatFileSize(bf.file.size)}</span>
                          {bf.status === 'pending' && (
                            <button onClick={() => removeBulkFile(bf.id)} className="text-slate-400 hover:text-red-500">
                              <X className="w-3.5 h-3.5" />
                            </button>
                          )}
                          {bf.status === 'done' && <CheckCircle className="w-4 h-4 text-green-500" />}
                          {bf.status === 'uploading' && <Loader2 className="w-4 h-4 animate-spin text-indigo-500" />}
                        </div>
                        {bf.status === 'error' && bf.error && (
                          <p className="text-[10px] text-red-500">{bf.error}</p>
                        )}
                        {bf.status === 'uploading' && (
                          <div className="w-full bg-indigo-100 rounded-full h-1.5">
                            <div className="bg-indigo-500 h-1.5 rounded-full transition-all" style={{ width: `${bf.progress}%` }} />
                          </div>
                        )}
                        {bf.status === 'pending' && (
                          <div className="flex gap-2">
                            <select
                              value={bf.discipline}
                              onChange={e => updateBulkFile(bf.id, { discipline: e.target.value })}
                              className={`flex-1 h-8 px-2 text-[11px] bg-white border rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-300 ${!bf.discipline ? 'border-red-300' : 'border-slate-200'}`}
                            >
                              <option value="">תחום *</option>
                              {allDisciplines.map(d => (
                                <option key={d.key} value={d.key}>{getDisciplineLabel(d.key)}</option>
                              ))}
                            </select>
                            {showFloorField && floorsList.length > 0 && (
                              <select
                                value={bf.floor_id}
                                onChange={e => updateBulkFile(bf.id, { floor_id: e.target.value })}
                                className="flex-1 h-8 px-2 text-[11px] bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-300"
                              >
                                <option value="">קומה</option>
                                {floorsList.map(f => (
                                  <option key={f.id} value={f.id}>{f.building_name ? `${f.building_name} - ` : ''}{f.display_label || f.name || `קומה ${f.floor_number || ''}`}</option>
                                ))}
                              </select>
                            )}
                            <select
                              value={bf.plan_type}
                              onChange={e => updateBulkFile(bf.id, { plan_type: e.target.value })}
                              className="h-8 px-2 text-[11px] bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-300"
                            >
                              {planTypes.map(pt => (
                                <option key={pt.value} value={pt.value}>{pt.label}</option>
                              ))}
                            </select>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {bulkFiles.length > 0 && (
                <button
                  onClick={handleBulkUpload}
                  disabled={bulkUploading || bulkFiles.filter(f => f.status === 'pending' && f.discipline).length === 0}
                  className="w-full py-3 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-sm font-bold transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {bulkUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  {bulkUploading ? 'מעלה...' : `העלה ${bulkFiles.filter(f => f.status === 'pending' && f.discipline).length} קבצים`}
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default BulkPlanUploadModal;
