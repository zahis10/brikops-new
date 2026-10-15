import React, { useState, useEffect } from 'react';
import { Switch } from '../ui/switch';
import { Loader2, Settings2 } from 'lucide-react';
import { toast } from 'sonner';
import { billingService } from '../../services/api';

export default function PlatformFeatureToggles() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    let alive = true;
    billingService.getDefectAiMode()
      .then(data => { if (alive) setConfig(data); })
      .catch(() => { if (alive) setError('שגיאה בטעינת הגדרות הפלטפורמה'); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);
  const toggle = async (next) => {
    setSaving(true);
    try {
      const data = await billingService.setDefectAiMode(next);
      setConfig(data);
      toast.success(next ? 'מצב AI פעיל לכל המשתמשים' : 'מצב AI כבוי — כולם בטופס הקלאסי');
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'שגיאה');
    } finally { setSaving(false); }
  };
  const { enabled, updated_at } = config || {};
  return (
    <div className="bg-white rounded-xl border shadow-sm p-4" dir="rtl">
      <div className="flex items-center gap-2 mb-3">
        <Settings2 className="w-4 h-4 text-slate-500" />
        <h3 className="text-sm font-bold text-slate-700">הגדרות פלטפורמה</h3>
      </div>
      {loading ? <Loader2 className="w-5 h-5 animate-spin text-slate-500" aria-label="טוען הגדרות" /> : error ? (
        <div className="text-xs text-red-600" role="alert">{error}</div>
      ) : (
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-medium text-slate-800">מצב AI בטופס ליקוי</div>
            <div className="text-xs text-slate-500 mt-0.5">{enabled ? 'פעיל לכל המשתמשים — המתג "מצב מילוי" מוצג בטופס' : 'כבוי לכל המשתמשים — כולם רואים את הטופס הקלאסי'}</div>
            {updated_at && <div className="text-[11px] text-slate-400 mt-1">עודכן {new Date(updated_at).toLocaleString('he-IL')}</div>}
          </div>
          <Switch checked={enabled} disabled={saving} onCheckedChange={toggle} aria-label="מצב AI בטופס ליקוי" />
        </div>
      )}
    </div>
  );
}
