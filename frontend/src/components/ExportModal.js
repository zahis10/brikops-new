import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from './ui/dialog';
import { Download, Loader2, FileSpreadsheet, FileText } from 'lucide-react';
import { exportService } from '../services/api';
import { toast } from 'sonner';

const ExportModal = ({ open, onOpenChange, scope, unitId, buildingId, filters, meta }) => {
  const [exporting, setExporting] = useState(false);
  const [format, setFormat] = useState('excel');

  const handleExport = async () => {
    setExporting(true);
    try {
      await exportService.exportDefects({
        scope,
        unit_id: unitId,
        building_id: buildingId,
        filters: filters || {},
        format,
      });
      toast.success('הקובץ הורד בהצלחה');
      onOpenChange(false);
    } catch (err) {
      console.error('Export failed:', err);
      toast.error('שגיאה בייצוא. נסה שוב.');
    } finally {
      setExporting(false);
    }
  };

  const scopeLabel = scope === 'building'
    ? `בניין: ${meta?.buildingName || ''}`
    : `דירה: ${meta?.unitLabel || ''}`;

  const filterParts = [];
  if (filters?.status && filters.status !== 'all') {
    const statusLabels = { open: 'פתוחים', closed: 'סגורים', blocking: 'חוסמי מסירה', in_progress: 'בטיפול' };
    filterParts.push(`סטטוס: ${statusLabels[filters.status] || filters.status}`);
  }
  if (filters?.category && filters.category !== 'all') filterParts.push(`תחום: ${filters.category}`);
  if (filters?.company && filters.company !== 'all') filterParts.push('חברה: מסוננת');
  if (filters?.assignee && filters.assignee !== 'all') filterParts.push('אחראי: מסונן');
  if (filters?.created_by && filters.created_by !== 'all') filterParts.push('יוצר: מסונן');
  if (filters?.floor && filters.floor !== 'all') filterParts.push('קומה: מסוננת');
  if (filters?.unit && filters.unit !== 'all') filterParts.push('דירה: מסוננת');
  if (filters?.search) filterParts.push(`חיפוש: "${filters.search}"`);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[380px] p-0" dir="rtl">
        <DialogHeader className="px-5 pt-5 pb-3 border-b border-slate-200">
          <DialogTitle className="text-right text-base font-bold text-slate-800">
            <div className="flex items-center gap-2">
              <Download className="w-4 h-4" />
              ייצוא ליקויים
            </div>
          </DialogTitle>
          <DialogDescription className="sr-only">ייצוא ליקויים לקובץ</DialogDescription>
        </DialogHeader>

        <div className="px-5 py-4 space-y-4">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setFormat('excel')}
              className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium border transition-colors ${
                format === 'excel'
                  ? 'border-amber-400 bg-amber-50 text-amber-700'
                  : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'
              }`}
            >
              <FileSpreadsheet className="w-4 h-4" />
              Excel
            </button>
            <button
              type="button"
              onClick={() => setFormat('pdf')}
              className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium border transition-colors ${
                format === 'pdf'
                  ? 'border-amber-400 bg-amber-50 text-amber-700'
                  : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'
              }`}
            >
              <FileText className="w-4 h-4" />
              PDF
            </button>
          </div>

          <div className="bg-slate-50 rounded-lg p-3 space-y-2">
            <div className="flex items-center gap-2 text-sm text-slate-700">
              {format === 'pdf' ? (
                <FileText className="w-4 h-4 text-amber-500" />
              ) : (
                <FileSpreadsheet className="w-4 h-4 text-amber-500" />
              )}
              <span className="font-medium">
                {format === 'pdf' ? 'PDF (.pdf)' : 'Excel (.xlsx)'}
              </span>
            </div>
            <div className="text-xs text-slate-500">
              {meta?.projectName && <span>{meta.projectName} · </span>}
              {scopeLabel}
            </div>
            {format === 'pdf' && (
              <div className="text-xs text-amber-600">
                כולל תמונות מוטמעות
              </div>
            )}
          </div>

          {filterParts.length > 0 && (
            <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
              <div className="text-xs font-medium text-amber-700 mb-1">סינון פעיל:</div>
              <div className="text-xs text-amber-600">
                {filterParts.join(' · ')}
              </div>
            </div>
          )}

          {filterParts.length === 0 && (
            <div className="text-xs text-slate-400 text-center">
              ייצוא כל הליקויים (ללא סינון)
            </div>
          )}
        </div>

        <div className="border-t border-slate-200 px-5 py-3 flex gap-3">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={exporting}
            className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            ביטול
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="flex-1 px-4 py-2.5 rounded-xl text-sm font-bold bg-amber-500 hover:bg-amber-600 text-white shadow-sm transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {exporting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                מייצא...
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                ייצוא
              </>
            )}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ExportModal;
