import React, { useState } from 'react';
import { Download, Loader2, FileSpreadsheet, CheckCircle } from 'lucide-react';
import { exportService } from '../services/api';
import { toast } from 'sonner';

const ProjectDataExportTab = ({ projectId, projectName }) => {
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      await exportService.exportDefects({
        scope: 'project',
        project_id: projectId,
        filters: {},
        format: 'excel',
      });
      toast.success('הקובץ הורד בהצלחה');
    } catch (err) {
      console.error('Project export failed:', err);
      if (err?.response?.status === 403) {
        toast.error('אין הרשאה לייצוא נתונים');
      } else {
        toast.error('שגיאה בייצוא. נסה שוב.');
      }
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6" dir="rtl">
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 bg-amber-50 rounded-xl flex items-center justify-center shrink-0">
          <FileSpreadsheet className="w-6 h-6 text-amber-600" />
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-bold text-slate-800 mb-1">ייצוא נתוני פרויקט</h3>
          <p className="text-sm text-slate-500 mb-4">
            ייצוא כל הליקויים בפרויקט לקובץ Excel — כולל בניינים, קומות, דירות, סטטוסים, קבלנים וקישורי תמונות.
          </p>

          <div className="bg-slate-50 rounded-lg p-4 mb-4">
            <div className="flex items-center gap-2 text-sm text-slate-600 mb-2">
              <CheckCircle className="w-4 h-4 text-green-500" />
              <span>כל הליקויים מכל הבניינים והדירות</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-600 mb-2">
              <CheckCircle className="w-4 h-4 text-green-500" />
              <span>קישורים לתמונות (פתיחה בדפדפן)</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <CheckCircle className="w-4 h-4 text-green-500" />
              <span>פורמט Excel — ניתן לפתוח ב-Google Sheets או Microsoft Excel</span>
            </div>
          </div>

          <button
            onClick={handleExport}
            disabled={exporting}
            className="flex items-center gap-2 px-5 py-2.5 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-300 text-white font-medium rounded-lg transition-colors"
          >
            {exporting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>מייצא...</span>
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                <span>ייצוא לקובץ Excel</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProjectDataExportTab;
