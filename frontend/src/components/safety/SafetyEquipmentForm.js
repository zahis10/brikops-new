import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { safetyService } from '../../services/api';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../ui/select';
import SafetyFormModal from './SafetyFormModal';
import { EQUIPMENT_CATEGORY_HE, EQUIPMENT_STATUS_HE } from './safetyLabels';

// Create + edit an equipment item (safety_equipment). Mirrors SafetyTrainingForm
// chrome. Category is either one of the 10 fixed keys or a free-text custom value;
// is_custom_category is SERVER-derived and never sent. No delete (batch safety-p3b).
const CUSTOM = '__custom__';
const CAT_KEYS = Object.keys(EQUIPMENT_CATEGORY_HE);
const isFixed = (c) => CAT_KEYS.includes(c);

export default function SafetyEquipmentForm({ projectId, item, presetCategory, open, onClose, onSaved }) {
  const isEdit = !!item;

  const [catSelect, setCatSelect] = useState('');
  const [customCat, setCustomCat] = useState('');
  const [internalCode, setInternalCode] = useState('');
  const [description, setDescription] = useState('');
  const [serialNumber, setSerialNumber] = useState('');
  const [manufacturer, setManufacturer] = useState('');
  const [status, setStatus] = useState('active');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    const initial = isEdit ? item?.category : presetCategory;
    if (initial && isFixed(initial)) {
      setCatSelect(initial);
      setCustomCat('');
    } else if (initial) {
      setCatSelect(CUSTOM);
      setCustomCat(initial);
    } else {
      setCatSelect('');
      setCustomCat('');
    }
    setInternalCode(item?.internal_code || '');
    setDescription(item?.description || '');
    setSerialNumber(item?.serial_number || '');
    setManufacturer(item?.manufacturer || '');
    setStatus(item?.status || 'active');
  }, [open, item, presetCategory, isEdit]);

  const handleSubmit = async () => {
    let category;
    if (catSelect === CUSTOM) {
      category = customCat.trim();
      if (!category) { toast.error('יש להזין שם קטגוריה'); return; }
    } else {
      category = catSelect;
      if (!category) { toast.error('יש לבחור קטגוריה'); return; }
    }
    const code = internalCode.trim();
    if (!code) { toast.error('קוד פריט הוא שדה חובה'); return; }

    const payload = {
      category,
      internal_code: code,
      description: description.trim() || null,
      serial_number: serialNumber.trim() || null,
      manufacturer: manufacturer.trim() || null,
    };
    if (isEdit) payload.status = status;

    setSubmitting(true);
    try {
      const result = isEdit
        ? await safetyService.updateEquipment(projectId, item.id, payload)
        : await safetyService.createEquipment(projectId, payload);
      toast.success(isEdit ? 'הפריט עודכן' : 'הפריט נוסף');
      onSaved?.(result);
      onClose?.();
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'שגיאה בשמירת הפריט');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafetyFormModal
      open={open}
      onOpenChange={(o) => { if (!o && !submitting) onClose?.(); }}
      title={isEdit ? 'עריכת פריט ציוד' : 'פריט ציוד חדש'}
      onSubmit={handleSubmit}
      submitting={submitting}
    >
      <div className="space-y-1.5">
        <Label>קטגוריה *</Label>
        <Select value={catSelect} onValueChange={setCatSelect} dir="rtl">
          <SelectTrigger><SelectValue placeholder="בחר קטגוריה" /></SelectTrigger>
          <SelectContent>
            {CAT_KEYS.map((k) => (
              <SelectItem key={k} value={k}>{EQUIPMENT_CATEGORY_HE[k]}</SelectItem>
            ))}
            <SelectItem value={CUSTOM}>קטגוריה מותאמת אישית…</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {catSelect === CUSTOM && (
        <div className="space-y-1.5">
          <Label htmlFor="eq-custom-cat">שם הקטגוריה *</Label>
          <Input id="eq-custom-cat" value={customCat} maxLength={60} onChange={(e) => setCustomCat(e.target.value)} placeholder="לדוגמה: מערבל בטון" />
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="eq-code">קוד פריט *</Label>
        <Input id="eq-code" value={internalCode} maxLength={60} onChange={(e) => setInternalCode(e.target.value)} placeholder="לדוגמה: א.ג-03" />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="eq-desc">תיאור</Label>
        <Input id="eq-desc" value={description} maxLength={300} onChange={(e) => setDescription(e.target.value)} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="eq-serial">מספר סידורי</Label>
          <Input id="eq-serial" value={serialNumber} maxLength={60} onChange={(e) => setSerialNumber(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="eq-manufacturer">יצרן</Label>
          <Input id="eq-manufacturer" value={manufacturer} maxLength={120} onChange={(e) => setManufacturer(e.target.value)} />
        </div>
      </div>

      {isEdit && (
        <div className="space-y-1.5">
          <Label>סטטוס</Label>
          <Select value={status} onValueChange={setStatus} dir="rtl">
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {Object.entries(EQUIPMENT_STATUS_HE).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    </SafetyFormModal>
  );
}
