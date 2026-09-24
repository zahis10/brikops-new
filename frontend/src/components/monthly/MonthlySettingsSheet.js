import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { Switch } from '../ui/switch';
import { MobileSelect } from '../ui/mobile-select';
import { monthlyCloseService } from '../../services/monthlyCloseService';

export default function MonthlySettingsSheet({ open, onOpenChange, projectId, onSaved }) {
  const [data, setData] = useState(null);
  const [mapping, setMapping] = useState({});
  const [visible, setVisible] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const load = async () => {
    setLoading(true);
    setData(null);
    try {
      const settings = await monthlyCloseService.getSettings(projectId);
      setData(settings);
      setMapping(settings.stage_companies || {});
      setVisible(!!settings.contractor_visible);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'לא ניתן לטעון הגדרות');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { if (open) load(); }, [open, projectId]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = async () => {
    setSaving(true);
    try {
      await monthlyCloseService.putSettings(projectId, {
        stage_companies: { ...data.suggestions, ...mapping }, contractor_visible: visible, updated_at: data.updated_at,
      });
      toast.success('ההגדרות נשמרו');
      onOpenChange(false);
      onSaved();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'לא ניתן לשמור הגדרות');
      if (error.response?.status === 409) await load();
    } finally {
      setSaving(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent dir="rtl" className="max-w-lg max-h-[90vh] overflow-y-auto text-right">
        <DialogHeader className="text-right">
          <DialogTitle>חשבון חודשי · הגדרות</DialogTitle>
          <DialogDescription className="text-right">שיוך שלבים לקבלנים ושקיפות הדוח</DialogDescription>
        </DialogHeader>
        {loading && <p className="text-slate-500">טוען הגדרות…</p>}
        {!loading && !data && <button type="button" onClick={load} className="text-amber-700">נסה שוב</button>}
        {!loading && data && <>
          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-2 font-bold text-slate-900">
              <span>מי הקבלן של כל שלב</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs">{data.stages?.length || 0} שלבים</span>
            </div>
            <p className="mt-2 text-sm text-slate-500">ברירת מחדל לפי המקצוע של החברה. בלי שיוך — השלב לא נכנס לחשבון של אף אחד.</p>
            <div className="mt-4 space-y-4">
              {(data.stages || []).map((stage) => {
                const suggested = !Object.prototype.hasOwnProperty.call(mapping, stage.id) && data.suggestions?.[stage.id];
                return (
                  <div key={stage.id}>
                    <label className="mb-1 flex items-center gap-2 text-sm font-medium">
                      {stage.title}
                      {suggested && <span className="rounded-full bg-amber-100 px-2 text-xs text-amber-800">הצעה</span>}
                    </label>
                    <MobileSelect value={suggested ? data.suggestions[stage.id] : (mapping[stage.id] || '')}
                      onChange={(event) => setMapping((previous) => ({ ...previous, [stage.id]: event.target.value || null }))}
                      options={[{ value: '', label: '— ללא קבלן —' }, ...(data.companies || []).map((company) => ({
                        value: company.id, label: `${company.name} · ${company.trade_label || company.trade || ''}`,
                      }))]} />
                  </div>
                );
              })}
            </div>
          </section>
          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <label className="flex items-center justify-between gap-3 font-semibold">
              הקבלן רואה את הדוח שלו
              <Switch checked={visible} onCheckedChange={setVisible} />
            </label>
            <p className="mt-2 text-sm text-slate-500">כשמופעל: כל קבלן רואה רק את הדוח שלו, קריאה בלבד, ומקבל התראה בפעמון כשחודש נסגר.</p>
          </section>
          <button type="button" onClick={save} disabled={saving || !data.can_write}
            className="min-h-[44px] w-full rounded-lg bg-amber-500 font-bold text-white disabled:opacity-50">
            {saving ? 'שומר…' : 'שמור הגדרות'}
          </button>
        </>}
      </DialogContent>
    </Dialog>
  );
}