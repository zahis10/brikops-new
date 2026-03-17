import React, { useState, useRef } from 'react';
import { X, Upload, Download, Loader2, CheckCircle2, AlertTriangle, FileSpreadsheet, RefreshCw } from 'lucide-react';
import { g4ImportService } from '../../services/api';

const MAX_FILE_SIZE = 5 * 1024 * 1024;

export default function G4ImportModal({ projectId, onClose }) {
  const [step, setStep] = useState('upload');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const fileInputRef = useRef(null);

  const handleDownloadTemplate = async () => {
    try {
      setLoading(true);
      await g4ImportService.downloadTemplate(projectId);
    } catch (err) {
      setError('שגיאה בהורדת התבנית');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    setError(null);

    const ext = selected.name.split('.').pop()?.toLowerCase();
    if (!['xlsx', 'csv'].includes(ext)) {
      setError('פורמט לא נתמך. יש להעלות קובץ xlsx או csv');
      return;
    }
    if (selected.size > MAX_FILE_SIZE) {
      setError('קובץ גדול מדי (מקסימום 5MB)');
      return;
    }
    setFile(selected);
  };

  const handleUpload = async () => {
    if (!file) return;
    try {
      setLoading(true);
      setError(null);
      const result = await g4ImportService.preview(projectId, file);
      setPreviewData(result);
      setStep('preview');
    } catch (err) {
      setError(err.response?.data?.detail || 'שגיאה בקריאת הקובץ');
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!previewData) return;
    const validRows = previewData.rows
      .filter(r => r.valid)
      .map(r => r.row);

    if (validRows.length === 0) {
      setError('אין שורות תקינות לייבוא');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const result = await g4ImportService.execute(projectId, validRows);
      setImportResult(result);
      setStep('done');
    } catch (err) {
      setError(err.response?.data?.detail || 'שגיאה בייבוא');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setStep('upload');
    setFile(null);
    setPreviewData(null);
    setImportResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        className="absolute inset-x-3 top-[5%] bottom-[5%] sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2 sm:w-full sm:max-w-2xl bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden"
        dir="rtl"
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
            <h2 className="text-sm font-bold text-slate-800">ייבוא נתוני רוכשים (ג4)</h2>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded-lg">
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {error && (
            <div className="mb-4 flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg p-3">
              <AlertTriangle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
              <span className="text-xs text-red-700">{error}</span>
            </div>
          )}

          {step === 'upload' && (
            <div className="space-y-4">
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-center space-y-3">
                <p className="text-sm text-slate-600">
                  העלו קובץ Excel או CSV עם נתוני הרוכשים בפורמט הקבוע
                </p>
                <button
                  onClick={handleDownloadTemplate}
                  disabled={loading}
                  className="inline-flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium px-3 py-1.5 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  הורד תבנית
                </button>
              </div>

              <div className="space-y-3">
                <label
                  className="block border-2 border-dashed border-slate-300 rounded-xl p-8 text-center cursor-pointer hover:border-emerald-400 hover:bg-emerald-50/30 transition-colors"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xlsx,.csv"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                  <p className="text-sm text-slate-500">
                    {file ? file.name : 'לחצו לבחירת קובץ (.xlsx / .csv)'}
                  </p>
                  {file && (
                    <p className="text-xs text-slate-400 mt-1">
                      {(file.size / 1024).toFixed(0)} KB
                    </p>
                  )}
                </label>

                {file && (
                  <button
                    onClick={handleUpload}
                    disabled={loading}
                    className="w-full flex items-center justify-center gap-2 bg-emerald-600 text-white text-sm font-medium py-2.5 rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    {loading ? 'קורא קובץ...' : 'המשך'}
                  </button>
                )}
              </div>
            </div>
          )}

          {step === 'preview' && previewData && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700">
                  <CheckCircle2 className="w-3 h-3" /> {previewData.valid_count} שורות תקינות
                </span>
                {previewData.error_count > 0 && (
                  <span className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-red-100 text-red-700">
                    <AlertTriangle className="w-3 h-3" /> {previewData.error_count} שגיאות
                  </span>
                )}
                {previewData.overwrite_count > 0 && (
                  <span className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-amber-100 text-amber-700">
                    <RefreshCw className="w-3 h-3" /> {previewData.overwrite_count} יוחלפו
                  </span>
                )}
              </div>

              {previewData.overwrite_count > 0 && (
                <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-3">
                  <RefreshCw className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                  <span className="text-xs text-amber-800">
                    {previewData.overwrite_count} יחידות כבר מכילות נתוני רוכשים — הנתונים הקיימים יוחלפו
                  </span>
                </div>
              )}

              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200">
                        <th className="px-2 py-2 text-right font-medium text-slate-500">#</th>
                        <th className="px-2 py-2 text-right font-medium text-slate-500">בניין</th>
                        <th className="px-2 py-2 text-right font-medium text-slate-500">קומה</th>
                        <th className="px-2 py-2 text-right font-medium text-slate-500">דירה</th>
                        <th className="px-2 py-2 text-right font-medium text-slate-500">שם רוכש</th>
                        <th className="px-2 py-2 text-right font-medium text-slate-500">ת"ז</th>
                        <th className="px-2 py-2 text-right font-medium text-slate-500">טלפון</th>
                        <th className="px-2 py-2 text-right font-medium text-slate-500">סטטוס</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewData.rows.map((item, idx) => {
                        const r = item.row;
                        const hasError = !item.valid;
                        const hasWarning = item.warnings?.length > 0;
                        const isOverwrite = item.overwrite;
                        let bgClass = '';
                        if (hasError) bgClass = 'bg-red-50';
                        else if (isOverwrite) bgClass = 'bg-amber-50';
                        else if (hasWarning) bgClass = 'bg-yellow-50';

                        return (
                          <tr key={idx} className={`border-b border-slate-100 ${bgClass}`}>
                            <td className="px-2 py-1.5 text-slate-400">{r.source_row || idx + 2}</td>
                            <td className="px-2 py-1.5">{r.building_name}</td>
                            <td className="px-2 py-1.5">{r.floor}</td>
                            <td className="px-2 py-1.5 font-medium">{r.apartment_number}</td>
                            <td className="px-2 py-1.5">{r.tenant_name}</td>
                            <td className="px-2 py-1.5 font-mono">{r.tenant_id_number}</td>
                            <td className="px-2 py-1.5 font-mono" dir="ltr">{r.tenant_phone}</td>
                            <td className="px-2 py-1.5">
                              {hasError && (
                                <span className="text-red-600" title={item.errors.join(', ')}>
                                  {item.errors.join(', ')}
                                </span>
                              )}
                              {!hasError && hasWarning && (
                                <span className="text-amber-600" title={item.warnings.join(', ')}>
                                  {item.warnings.join(', ')}
                                </span>
                              )}
                              {!hasError && !hasWarning && isOverwrite && (
                                <span className="text-amber-600">יוחלף</span>
                              )}
                              {!hasError && !hasWarning && !isOverwrite && (
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handleReset}
                  className="flex-1 text-sm text-slate-600 font-medium py-2.5 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                >
                  חזרה
                </button>
                <button
                  onClick={handleExecute}
                  disabled={loading || previewData.valid_count === 0}
                  className="flex-1 flex items-center justify-center gap-2 bg-emerald-600 text-white text-sm font-medium py-2.5 rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  {loading ? 'מייבא...' : `ייבוא ${previewData.valid_count} שורות`}
                </button>
              </div>
            </div>
          )}

          {step === 'done' && importResult && (
            <div className="space-y-4 text-center py-4">
              <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto" />
              <h3 className="text-lg font-bold text-slate-800">הייבוא הושלם</h3>
              <div className="flex justify-center gap-4 text-sm">
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3">
                  <div className="text-2xl font-bold text-emerald-700">{importResult.imported}</div>
                  <div className="text-xs text-emerald-600">יובאו</div>
                </div>
                {importResult.skipped > 0 && (
                  <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3">
                    <div className="text-2xl font-bold text-red-700">{importResult.skipped}</div>
                    <div className="text-xs text-red-600">דולגו</div>
                  </div>
                )}
              </div>
              {importResult.errors?.length > 0 && (
                <div className="mt-4 text-right bg-red-50 border border-red-200 rounded-lg p-3">
                  <p className="text-xs font-medium text-red-700 mb-1">שגיאות:</p>
                  {importResult.errors.map((e, i) => (
                    <p key={i} className="text-xs text-red-600">
                      שורה {e.source_row || '?'} (דירה {e.apartment || '?'}): {e.errors?.join(', ')}
                    </p>
                  ))}
                </div>
              )}
              <button
                onClick={onClose}
                className="mt-4 bg-slate-800 text-white text-sm font-medium px-6 py-2.5 rounded-lg hover:bg-slate-900 transition-colors"
              >
                סגור
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
