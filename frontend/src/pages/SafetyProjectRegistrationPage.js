import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { ChevronDown, ChevronUp, Save, Download, Trash2, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { safetyService } from '../services/api';
import { downloadBlob } from '../utils/fileDownload';

const EMPTY_MANAGER = {
  first_name: '',
  last_name: '',
  id_number: '',
  address: '',
  notes: '',
};

const EMPTY_ADDRESS = {
  city: '',
  postal_code: '',
  street: '',
  house_number: '',
  email: '',
  phone: '',
  mobile: '',
  fax: '',
};

const Section = ({ title, isOpen, onToggle, children }) => (
  <div className="bg-white rounded-xl shadow-sm border border-slate-200 mb-3">
    <button
      onClick={onToggle}
      className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-50 transition-colors"
    >
      <span className="font-bold text-slate-800">{title}</span>
      {isOpen ? <ChevronUp className="w-5 h-5 text-slate-500" /> :
                <ChevronDown className="w-5 h-5 text-slate-500" />}
    </button>
    {isOpen && (
      <div className="px-4 pb-4 border-t border-slate-100 pt-3" dir="rtl">
        {children}
      </div>
    )}
  </div>
);

const Field = ({ label, value, onChange, type = 'text', placeholder = '' }) => (
  <div className="mb-3">
    <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
    <input
      type={type}
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      dir="rtl"
      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
    />
  </div>
);

export default function SafetyProjectRegistrationPage() {
  const { projectId } = useParams();
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reg, setReg] = useState({
    developer_name: '',
    main_contractor_name: '',
    contractor_registry_number: '',
    office_address: { ...EMPTY_ADDRESS },
    managers: [],
    permit_number: '',
    form_4_target_date: '',
  });
  const [completion, setCompletion] = useState({
    completion_pct: 0,
    missing_fields: [],
    is_complete: false,
  });
  const [openSections, setOpenSections] = useState({
    general: true,
    address: false,
    managers: false,
    regulatory: false,
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await safetyService.getRegistration(projectId);
      setReg({
        developer_name: data.developer_name || '',
        main_contractor_name: data.main_contractor_name || '',
        contractor_registry_number: data.contractor_registry_number || '',
        office_address: data.office_address || { ...EMPTY_ADDRESS },
        managers: data.managers || [],
        permit_number: data.permit_number || '',
        form_4_target_date: data.form_4_target_date || '',
      });
      const required = await safetyService.getRegistrationRequiredFields(projectId);
      setCompletion(required);
    } catch (err) {
      console.error('Failed to load registration:', err);
      toast.error('שגיאה בטעינת רישום הפרויקט');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await safetyService.upsertRegistration(projectId, reg);
      toast.success('רישום הפרויקט נשמר');
      await load();
    } catch (err) {
      console.error('Failed to save registration:', err);
      toast.error('שגיאה בשמירה');
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadPdf = async () => {
    try {
      const blob = await safetyService.exportRegistrationPdf(projectId);
      // V3: downloadBlob handles both web (blob URL + anchor) and Capacitor
      // native (Filesystem.writeFile + Share sheet). See utils/fileDownload.js:14.
      await downloadBlob(blob, `registration_${projectId}.pdf`, 'application/pdf');
      toast.success('הקובץ נשמר');
    } catch (err) {
      console.error('Failed to export PDF:', err);
      toast.error('שגיאה בייצוא PDF');
    }
  };

  const setField = (field, value) => setReg(prev => ({ ...prev, [field]: value }));
  const setAddrField = (field, value) =>
    setReg(prev => ({ ...prev, office_address: { ...prev.office_address, [field]: value } }));
  const addManager = () =>
    setReg(prev => ({ ...prev, managers: [...prev.managers, { ...EMPTY_MANAGER }] }));
  const removeManager = (idx) =>
    setReg(prev => ({ ...prev, managers: prev.managers.filter((_, i) => i !== idx) }));
  const setManagerField = (idx, field, value) =>
    setReg(prev => ({
      ...prev,
      managers: prev.managers.map((m, i) => i === idx ? { ...m, [field]: value } : m),
    }));
  const toggleSection = (key) =>
    setOpenSections(prev => ({ ...prev, [key]: !prev[key] }));

  if (loading) {
    return <div className="p-8 text-center text-slate-500">טוען...</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900 mb-2">רישום פרויקט בטיחות</h1>
          <p className="text-sm text-slate-600">פרטי הפרויקט לפי דרישות פנקס הקבלנים</p>
          <div className="mt-3 bg-slate-200 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full transition-all ${completion.is_complete ? 'bg-emerald-500' : 'bg-amber-500'}`}
              style={{ width: `${completion.completion_pct}%` }}
            />
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {completion.completion_pct}% הושלם ({completion.missing_fields.length} שדות חסרים)
          </p>
        </div>

        <Section title="1. כללי" isOpen={openSections.general} onToggle={() => toggleSection('general')}>
          <Field label="שם היזם" value={reg.developer_name} onChange={(v) => setField('developer_name', v)} placeholder="לדוגמה: ארזי הנגב ייזום ובניה בע״מ" />
          <Field label="שם המבצע (קבלן ראשי)" value={reg.main_contractor_name} onChange={(v) => setField('main_contractor_name', v)} />
          <Field label="מספר רישום בפנקס הקבלנים" value={reg.contractor_registry_number} onChange={(v) => setField('contractor_registry_number', v)} placeholder="לדוגמה: 24914" />
        </Section>

        <Section title="2. מען המשרד הראשי" isOpen={openSections.address} onToggle={() => toggleSection('address')}>
          <Field label="הישוב" value={reg.office_address?.city} onChange={(v) => setAddrField('city', v)} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="רחוב / ת.ד" value={reg.office_address?.street} onChange={(v) => setAddrField('street', v)} />
            <Field label="מס' בית" value={reg.office_address?.house_number} onChange={(v) => setAddrField('house_number', v)} />
          </div>
          <Field label="מיקוד" value={reg.office_address?.postal_code} onChange={(v) => setAddrField('postal_code', v)} />
          <Field label="דואר אלקטרוני" value={reg.office_address?.email} onChange={(v) => setAddrField('email', v)} type="email" />
          <div className="grid grid-cols-3 gap-3">
            <Field label="טלפון" value={reg.office_address?.phone} onChange={(v) => setAddrField('phone', v)} />
            <Field label="נייד" value={reg.office_address?.mobile} onChange={(v) => setAddrField('mobile', v)} />
            <Field label="פקס" value={reg.office_address?.fax} onChange={(v) => setAddrField('fax', v)} />
          </div>
        </Section>

        <Section title={`3. מנהלי החברה (${reg.managers.length})`} isOpen={openSections.managers} onToggle={() => toggleSection('managers')}>
          {reg.managers.length === 0 && (
            <p className="text-sm text-slate-500 mb-3">לא הוזנו מנהלים. הוסף לפחות מנהל אחד.</p>
          )}
          {reg.managers.map((mgr, idx) => (
            <div key={idx} className="bg-slate-50 rounded-lg p-3 mb-3">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-slate-700">מנהל #{idx + 1}</span>
                <button onClick={() => removeManager(idx)} className="text-red-500 hover:text-red-700">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="שם פרטי" value={mgr.first_name} onChange={(v) => setManagerField(idx, 'first_name', v)} />
                <Field label="שם משפחה" value={mgr.last_name} onChange={(v) => setManagerField(idx, 'last_name', v)} />
              </div>
              <Field label="ת.ז" value={mgr.id_number} onChange={(v) => setManagerField(idx, 'id_number', v)} placeholder="9 ספרות (יוצפן בשמירה)" />
              <Field label="מען" value={mgr.address} onChange={(v) => setManagerField(idx, 'address', v)} />
              <Field label="הערות" value={mgr.notes} onChange={(v) => setManagerField(idx, 'notes', v)} />
            </div>
          ))}
          <button onClick={addManager} className="w-full py-2 border-2 border-dashed border-slate-300 rounded-lg text-slate-600 hover:border-blue-500 hover:text-blue-600 flex items-center justify-center gap-2">
            <Plus className="w-4 h-4" /> הוסף מנהל
          </button>
        </Section>

        <Section title="4. אסמכתאות רגולטוריות" isOpen={openSections.regulatory} onToggle={() => toggleSection('regulatory')}>
          <Field label="מספר היתר בנייה" value={reg.permit_number} onChange={(v) => setField('permit_number', v)} />
          <Field label="תאריך יעד טופס 4" value={reg.form_4_target_date} onChange={(v) => setField('form_4_target_date', v)} type="date" />
        </Section>

        {/* V3: safe-area-inset-bottom for iOS notch + py-3 for ≥44px touch target */}
        <div
          className="sticky bottom-0 bg-white border-t border-slate-200 -mx-4 px-4 pt-3 mt-4 flex gap-3"
          style={{ paddingBottom: 'max(12px, env(safe-area-inset-bottom))' }}
        >
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2"
          >
            <Save className="w-4 h-4" /> {saving ? 'שומר...' : 'שמור'}
          </button>
          <button
            onClick={handleDownloadPdf}
            className="px-4 bg-slate-700 hover:bg-slate-800 text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2"
            title="הורד את הרישום כ-PDF"
          >
            <Download className="w-4 h-4" /> PDF
          </button>
        </div>
      </div>
    </div>
  );
}
