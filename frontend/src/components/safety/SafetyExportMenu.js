import React, { useState } from 'react';
import { Download, ChevronDown, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../ui/dropdown-menu';
import { safetyService } from '../../services/api';

function yyyymmdd() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}${m}${day}`;
}

function downloadBlob(response, fallbackName) {
  const disp = response?.headers?.['content-disposition'] || '';
  const match = disp.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
  let filename = fallbackName;
  if (match) {
    try {
      filename = decodeURIComponent(match[1]);
    } catch (e) {
      // Malformed % in header — use the raw captured group as-is.
      filename = match[1];
    }
  }
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export default function SafetyExportMenu({
  projectId,
  currentFilter,
  hasActiveFilter,
}) {
  const [busy, setBusy] = useState(false);

  const stamp = yyyymmdd();
  const shortId = (projectId || '').slice(0, 8);

  const run = async (type) => {
    if (busy) return;
    setBusy(true);
    try {
      let response;
      let fallback;
      if (type === 'excel') {
        response = await safetyService.exportExcel(projectId);
        fallback = `safety_${shortId}_${stamp}.xlsx`;
      } else if (type === 'filtered') {
        const params = {};
        if (currentFilter) {
          Object.entries(currentFilter).forEach(([k, v]) => {
            if (v != null && v !== '') params[k] = v;
          });
        }
        response = await safetyService.exportFiltered(projectId, params);
        fallback = `safety_filtered_${shortId}_${stamp}.xlsx`;
      } else {
        response = await safetyService.exportPdfRegister(projectId);
        fallback = `safety_register_${shortId}_${stamp}.pdf`;
      }
      downloadBlob(response, fallback);
      toast.success('הקובץ הורד בהצלחה');
    } catch (err) {
      toast.error('שגיאה בייצוא — נסה שוב');
    } finally {
      setTimeout(() => setBusy(false), 500);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={busy}
          className="px-3 py-2 text-sm rounded-lg border border-slate-200 hover:bg-slate-50 flex items-center gap-1 min-h-[44px] disabled:opacity-60"
        >
          {busy ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Download className="w-4 h-4" />
          )}
          ייצוא
          <ChevronDown className="w-3 h-3 opacity-60" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" dir="rtl" className="min-w-[200px]">
        <DropdownMenuItem onSelect={() => run('excel')} disabled={busy}>
          ייצוא Excel כללי
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => hasActiveFilter && run('filtered')}
          disabled={busy || !hasActiveFilter}
          title={!hasActiveFilter ? 'אין סינון פעיל' : undefined}
        >
          ייצוא לפי סינון
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => run('pdf')} disabled={busy}>
          פנקס כללי PDF
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
