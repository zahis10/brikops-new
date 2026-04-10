import React, { useState, useEffect, useRef } from 'react';
import { Download, Loader2, FileSpreadsheet, Archive, CheckCircle, AlertCircle } from 'lucide-react';
import { exportService, dataExportService } from '../services/api';
import { toast } from 'sonner';

const ProjectDataExportTab = ({ projectId, projectName }) => {
  const [excelExporting, setExcelExporting] = useState(false);

  const [exportJob, setExportJob] = useState(null);
  const [latestExport, setLatestExport] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    dataExportService.getLatest(projectId)
      .then(data => { if (data?.exists) setLatestExport(data); })
      .catch(() => {});
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId]);

  const handleExcelExport = async () => {
    setExcelExporting(true);
    try {
      await exportService.exportDefects({
        scope: 'project', project_id: projectId, filters: {}, format: 'excel',
      });
      toast.success('הקובץ הורד בהצלחה');
    } catch (err) {
      toast.error(err?.response?.status === 403 ? 'אין הרשאה' : 'שגיאה בייצוא');
    } finally {
      setExcelExporting(false);
    }
  };

  const handleFullExport = async () => {
    try {
      const result = await dataExportService.startExport(projectId);
      setExportJob({ job_id: result.job_id, status: 'pending', progress: 0, progress_label: 'מתחיל...' });
      startPolling(result.job_id);
    } catch (err) {
      const status = err?.response?.status;
      if (status === 409) toast.error('ייצוא כבר בתהליך');
      else if (status === 429) toast.error('ניתן לייצא פעם בשעה');
      else if (status === 403) toast.error('אין הרשאה לייצוא נתונים');
      else toast.error('שגיאה בהתחלת ייצוא');
    }
  };

  const startPolling = (jobId) => {
    pollRef.current = setInterval(async () => {
      try {
        const data = await dataExportService.getStatus(projectId, jobId);
        setExportJob(data);
        if (data.status === 'done') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          toast.success('הייצוא הושלם!');
          if (data.download_url) window.open(data.download_url, '_blank');
          setLatestExport({ ...data, exists: true, completed_at: data.completed_at });
        } else if (data.status === 'error') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          toast.error(data.error || 'שגיאה בייצוא');
        }
      } catch {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }, 2000);
  };

  const isRunning = exportJob && ['pending', 'processing'].includes(exportJob.status);
  const isDone = exportJob?.status === 'done';
  const isError = exportJob?.status === 'error';

  const formatSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-4" dir="rtl">
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-green-50 rounded-lg flex items-center justify-center shrink-0">
            <FileSpreadsheet className="w-5 h-5 text-green-600" />
          </div>
          <div className="flex-1">
            <h3 className="font-bold text-slate-800 mb-1">ייצוא אקסל (ליקויים בלבד)</h3>
            <p className="text-sm text-slate-500 mb-3">
              כל הליקויים בפרויקט בקובץ Excel — כולל סטטוסים, קבלנים וקישורי תמונות.
            </p>
            <button onClick={handleExcelExport} disabled={excelExporting}
              className="flex items-center gap-2 px-4 py-2 bg-green-500 hover:bg-green-600 disabled:bg-green-300 text-white text-sm font-medium rounded-lg transition-colors">
              {excelExporting
                ? <><Loader2 className="w-4 h-4 animate-spin" /><span>מייצא...</span></>
                : <><Download className="w-4 h-4" /><span>הורד Excel</span></>}
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-amber-50 rounded-lg flex items-center justify-center shrink-0">
            <Archive className="w-5 h-5 text-amber-600" />
          </div>
          <div className="flex-1">
            <h3 className="font-bold text-slate-800 mb-1">ייצוא מלא (ZIP)</h3>
            <p className="text-sm text-slate-500 mb-3">
              כל נתוני הפרויקט: ליקויים, פרוטוקולי מסירה, בקרת ביצוע, מבנה, צוות, חברות — כולל כל התמונות.
            </p>

            {isRunning && (
              <div className="mb-3">
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-slate-600">{exportJob.progress_label}</span>
                  <span className="text-slate-400">{exportJob.progress}%</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2">
                  <div className="bg-amber-500 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${exportJob.progress}%` }} />
                </div>
              </div>
            )}

            {isDone && exportJob.stats && (
              <div className="bg-green-50 rounded-lg p-3 mb-3 text-sm text-green-800">
                <div className="flex items-center gap-2 font-medium mb-1">
                  <CheckCircle className="w-4 h-4" />
                  <span>הייצוא הושלם — {formatSize(exportJob.file_size)}</span>
                </div>
                <div className="text-green-600">
                  {exportJob.stats.defects} ליקויים · {exportJob.stats.handover_protocols} מסירות · {exportJob.stats.qc_runs} בקרות ביצוע · {exportJob.stats.photos_downloaded || 0} תמונות
                </div>
                {exportJob.download_url && (
                  <a href={exportJob.download_url} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 mt-2 text-green-700 hover:text-green-900 underline">
                    <Download className="w-3 h-3" /> הורד שוב
                  </a>
                )}
              </div>
            )}

            {isError && (
              <div className="bg-red-50 rounded-lg p-3 mb-3 text-sm text-red-700 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{exportJob.error || 'שגיאה בייצוא'}</span>
              </div>
            )}

            <button onClick={handleFullExport} disabled={isRunning}
              className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-300 text-white text-sm font-medium rounded-lg transition-colors">
              {isRunning
                ? <><Loader2 className="w-4 h-4 animate-spin" /><span>מייצא...</span></>
                : <><Archive className="w-4 h-4" /><span>ייצוא מלא</span></>}
            </button>

            {latestExport?.exists && !exportJob && (
              <div className="mt-3 text-xs text-slate-400">
                ייצוא אחרון: {new Date(latestExport.completed_at).toLocaleDateString('he-IL')} — {formatSize(latestExport.file_size)}
                {latestExport.download_url && (
                  <a href={latestExport.download_url} target="_blank" rel="noopener noreferrer"
                    className="mr-2 text-amber-500 hover:text-amber-700 underline">הורד</a>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProjectDataExportTab;
