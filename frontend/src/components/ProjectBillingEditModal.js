import React, { useState, useEffect, useMemo } from 'react';
import { billingService } from '../services/api';
import { formatCurrency } from '../utils/billingLabels';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from './ui/dialog';

const LICENSE_FIRST = 450;
const LICENSE_ADDITIONAL = 450;
const PRICE_PER_UNIT = 15;

export default function ProjectBillingEditModal({ open, onClose, projectBilling, onSaved }) {
  const [units, setUnits] = useState('');
  const [saving, setSaving] = useState(false);
  const [serverPricing, setServerPricing] = useState(null);

  const originalUnits = projectBilling?.contracted_units || 0;
  const parsedUnits = parseInt(units) || 0;

  useEffect(() => {
    if (open && projectBilling) {
      setUnits(String(projectBilling.contracted_units || ''));
    }
  }, [open, projectBilling]);

  useEffect(() => {
    if (open) {
      billingService.listActivePlans().then(data => {
        const plans = Array.isArray(data) ? data : data?.plans;
        if (plans?.length > 0) {
          setServerPricing(plans[0]);
        }
      }).catch(() => {});
    }
  }, [open]);

  const preview = useMemo(() => {
    if (parsedUnits < 1) return null;
    const lf = serverPricing?.license_first ?? LICENSE_FIRST;
    const la = serverPricing?.license_additional ?? LICENSE_ADDITIONAL;
    const ppu = serverPricing?.price_per_unit ?? PRICE_PER_UNIT;
    const licenseFee = lf;
    const unitCost = parsedUnits * ppu;
    return { licenseFee, unitCost, total: licenseFee + unitCost, pricePerUnit: ppu, licenseAdditional: la };
  }, [parsedUnits, serverPricing]);

  const hasChanges = parsedUnits > 0 && parsedUnits !== originalUnits;

  const handleSave = async () => {
    if (!hasChanges) return;
    setSaving(true);
    try {
      const payload = { plan_id: projectBilling.plan_id || 'standard', contracted_units: parsedUnits };
      const response = await billingService.updateProjectBilling(projectBilling.project_id, payload);

      if (response.pending_contracted_units != null) {
        const dateStr = response.pending_effective_from
          ? new Date(response.pending_effective_from).toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit' })
          : '';
        toast(`הירידה תיכנס לתוקף ב-${dateStr}. עד אז החיוב לפי הכמות הנוכחית.`, { icon: '📅' });
      } else if (parsedUnits > originalUnits) {
        toast('ההגדלה פעילה מיד. החיוב יתעדכן לפי השיא החודשי.', { icon: '⬆️' });
      } else {
        toast.success('השינויים נשמרו בהצלחה.');
      }

      onSaved?.(response);
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail || 'שגיאה בשמירת שינויים';
      toast.error(detail);
    } finally {
      setSaving(false);
    }
  };

  if (!projectBilling) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-lg" dir="rtl">
        <DialogHeader>
          <DialogTitle className="text-right">עריכת תמחור פרויקט</DialogTitle>
          <DialogDescription className="text-right text-sm text-slate-500">
            {projectBilling.project_name}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 mt-2">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">כמות יחידות לחיוב</label>
            <input
              type="number"
              min={1}
              value={units}
              onChange={(e) => setUnits(e.target.value)}
              onBlur={() => { if (!units || parseInt(units) < 1) setUnits('1'); }}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
              dir="ltr"
            />
          </div>

          {preview && (
            <div className="bg-slate-50 rounded-lg p-3 space-y-2">
              {projectBilling.plan_id === 'founder_6m' ? (<>
                <div className="text-xs text-slate-500 font-medium">תמחור תוכנית מייסדים</div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">מחיר חודשי</span>
                  <span className="font-bold text-slate-900">₪499</span>
                </div>
                <div className="border-t border-slate-200 pt-2 space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">מחיר רגיל</span>
                    <span className="text-slate-400 line-through">{formatCurrency(preview.total)}/חודש</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-emerald-600 font-semibold">חסכת עם תוכנית מייסדים</span>
                    <span className="text-emerald-600 font-semibold">{formatCurrency(preview.total - 499)}/חודש</span>
                  </div>
                </div>
              </>) : (<>
                <div className="text-xs text-slate-500 font-medium">הערכה לפרויקט ראשון — הסכום הסופי ייקבע לאחר שמירה</div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">רישיון פרויקט</span>
                  <span className="font-medium text-slate-700">{formatCurrency(preview.licenseFee)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">{parsedUnits} יחידות × {formatCurrency(preview.pricePerUnit)}</span>
                  <span className="font-medium text-slate-700">{formatCurrency(preview.unitCost)}</span>
                </div>
                <div className="border-t border-slate-200 pt-2 flex justify-between">
                  <span className="text-sm font-medium text-slate-700">סה״כ חודשי (הערכה)</span>
                  <span className="text-lg font-bold text-slate-900">{formatCurrency(preview.total)}</span>
                </div>
                <div className="text-xs text-slate-400">פרויקט נוסף: רישיון {formatCurrency(preview.licenseAdditional)}</div>
              </>)}
            </div>
          )}

          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
          >
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            שמור שינויים
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
