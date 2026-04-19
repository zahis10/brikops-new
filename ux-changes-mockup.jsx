import { useState } from "react";
import {
  ChevronLeft, Eye, EyeOff, Users, Building2, ClipboardCheck,
  FileEdit, KeyRound, CreditCard, ArrowRight, Info, Search,
  FolderOpen, Plus, AlertTriangle, Clock, CheckCircle2
} from "lucide-react";

const Section = ({ title, children }) => (
  <div className="mb-8">
    <h3 className="text-lg font-bold text-slate-800 mb-3 border-b border-slate-200 pb-2">{title}</h3>
    {children}
  </div>
);

const BeforeAfter = ({ children }) => (
  <div className="grid grid-cols-2 gap-4 mb-4">
    {children}
  </div>
);

const Label = ({ type }) => (
  <div className={`text-xs font-bold mb-2 px-2 py-1 rounded-full inline-block ${
    type === "before" ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
  }`}>
    {type === "before" ? "❌ לפני" : "✅ אחרי"}
  </div>
);

const MockCard = ({ children, className = "" }) => (
  <div className={`bg-white rounded-xl border border-slate-200 p-4 ${className}`}>
    {children}
  </div>
);

export default function UXChangesMockup() {
  const [showPw, setShowPw] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div className="max-w-3xl mx-auto p-6 bg-slate-50 min-h-screen font-sans" dir="rtl">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">BrikOps — שינויי UX</h1>
        <p className="text-sm text-slate-500">8 שינויים בפועל (5 ממצאים כבר מתוקנים בקוד)</p>
      </div>

      {/* 1. Password RTL Fix */}
      <Section title="1. שדה סיסמה — תיקון כיוון (קריטי)">
        <p className="text-sm text-slate-600 mb-3">כשלוחצים על אייקון העין, הסיסמה מוצגת בכיוון הפוך. סימן הקריאה קופץ להתחלה.</p>
        <BeforeAfter>
          <div>
            <Label type="before" />
            <MockCard>
              <label className="text-xs text-slate-500 mb-1 block">סיסמה</label>
              <div className="relative">
                <input
                  type="text"
                  value="!BrikOpsDemo2026"
                  readOnly
                  dir="rtl"
                  className="w-full h-11 px-3 py-2 pl-10 text-right text-slate-900 bg-white border border-slate-200 rounded-lg text-sm"
                />
                <button className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400">
                  <Eye className="w-5 h-5" />
                </button>
              </div>
              <p className="text-xs text-red-500 mt-1">← סימן קריאה בהתחלה במקום בסוף</p>
            </MockCard>
          </div>
          <div>
            <Label type="after" />
            <MockCard>
              <label className="text-xs text-slate-500 mb-1 block">סיסמה</label>
              <div className="relative">
                <input
                  type="text"
                  value="BrikOpsDemo2026!"
                  readOnly
                  dir="ltr"
                  className="w-full h-11 px-3 py-2 pl-10 text-left text-slate-900 bg-white border border-slate-200 rounded-lg text-sm"
                />
                <button className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400">
                  <Eye className="w-5 h-5" />
                </button>
              </div>
              <p className="text-xs text-green-600 mt-1">dir="ltr" — סימן קריאה בסוף ✓</p>
            </MockCard>
          </div>
        </BeforeAfter>
      </Section>

      {/* 2. Dashboard Whitespace */}
      <Section title="2. דשבורד — שטח לבן (קריטי)">
        <p className="text-sm text-slate-600 mb-3">min-h-screen יוצר חלל לבן מיותר מתחת לתוכן.</p>
        <BeforeAfter>
          <div>
            <Label type="before" />
            <MockCard className="relative">
              <div className="bg-slate-800 text-white text-xs p-2 rounded mb-2">הדר דשבורד</div>
              <div className="bg-amber-50 p-2 rounded text-xs mb-2">תוכן הדשבורד</div>
              <div className="bg-red-50 border-2 border-dashed border-red-300 h-24 rounded flex items-center justify-center">
                <span className="text-xs text-red-500 font-bold">שטח לבן מיותר (min-h-screen)</span>
              </div>
            </MockCard>
          </div>
          <div>
            <Label type="after" />
            <MockCard>
              <div className="bg-slate-800 text-white text-xs p-2 rounded mb-2">הדר דשבורד</div>
              <div className="bg-amber-50 p-2 rounded text-xs mb-2">תוכן הדשבורד</div>
              <p className="text-xs text-green-600 mt-1">min-h-0 — התוכן נגמר, הדף נגמר ✓</p>
            </MockCard>
          </div>
        </BeforeAfter>
      </Section>

      {/* 3. Defect Card Clickability */}
      <Section title="3. כרטיס ליקוי — cursor + chevron (קריטי)">
        <p className="text-sm text-slate-600 mb-3">הכרטיסים לחיצים אבל אין שום רמז ויזואלי לזה.</p>
        <BeforeAfter>
          <div>
            <Label type="before" />
            <MockCard>
              <div className="flex items-start gap-2">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-800">סדק באריחים</p>
                  <p className="text-xs text-slate-500 mt-0.5">מטבח — ריצוף</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">פתוח</span>
                    <span className="text-[10px] text-amber-600 font-medium">גבוה</span>
                  </div>
                </div>
              </div>
              <p className="text-xs text-red-500 mt-2">← אין cursor-pointer, אין חץ</p>
            </MockCard>
          </div>
          <div>
            <Label type="after" />
            <MockCard className="cursor-pointer hover:shadow-md transition-shadow border-slate-200 hover:border-amber-300">
              <div className="flex items-start gap-2">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-800">סדק באריחים</p>
                  <p className="text-xs text-slate-500 mt-0.5">מטבח — ריצוף</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">פתוח</span>
                    <span className="text-[10px] text-amber-600 font-medium">גבוה</span>
                  </div>
                </div>
                <ChevronLeft className="w-4 h-4 text-slate-400 flex-shrink-0 mt-1" />
              </div>
              <p className="text-xs text-green-600 mt-2">cursor-pointer + chevron שמאלי ✓</p>
            </MockCard>
          </div>
        </BeforeAfter>
      </Section>

      {/* 4. Emoji → Lucide Icons */}
      <Section title="4. טאבים — אימוג'ים → Lucide (בינוני)">
        <p className="text-sm text-slate-600 mb-3">כל האפליקציה ב-Lucide, רק הטאבים של Admin באימוג'ים.</p>
        <BeforeAfter>
          <div>
            <Label type="before" />
            <MockCard>
              <div className="flex gap-2 overflow-x-auto text-xs">
                {[
                  { icon: "👥", label: "צוות" },
                  { icon: "🏢", label: "קבלנים" },
                  { icon: "📋", label: "מאשרים" },
                  { icon: "📝", label: "תבנית QC" },
                  { icon: "🔑", label: "מסירה" },
                  { icon: "💳", label: "מנוי" },
                ].map((t, i) => (
                  <button key={i} className={`flex items-center gap-1 px-3 py-2 rounded-lg whitespace-nowrap ${
                    i === 0 ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600"
                  }`}>
                    <span>{t.icon}</span>
                    <span>{t.label}</span>
                  </button>
                ))}
              </div>
            </MockCard>
          </div>
          <div>
            <Label type="after" />
            <MockCard>
              <div className="flex gap-2 overflow-x-auto text-xs">
                {[
                  { Icon: Users, label: "צוות" },
                  { Icon: Building2, label: "קבלנים" },
                  { Icon: ClipboardCheck, label: "מאשרים" },
                  { Icon: FileEdit, label: "תבנית QC" },
                  { Icon: KeyRound, label: "מסירה" },
                  { Icon: CreditCard, label: "מנוי" },
                ].map((t, i) => (
                  <button key={i} className={`flex items-center gap-1.5 px-3 py-2 rounded-lg whitespace-nowrap ${
                    i === 0 ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600"
                  }`}>
                    <t.Icon className="w-4 h-4" />
                    <span>{t.label}</span>
                  </button>
                ))}
              </div>
            </MockCard>
          </div>
        </BeforeAfter>
      </Section>

      {/* 5. Touch Targets */}
      <Section title="5. Touch Targets — כפתורים קטנים מדי (בינוני)">
        <p className="text-sm text-slate-600 mb-3">כפתורי הדר 32px, כפתור info 18px. מינימום WCAG: 44px.</p>
        <BeforeAfter>
          <div>
            <Label type="before" />
            <MockCard>
              <div className="flex items-center gap-4 justify-center">
                <div className="relative">
                  <button className="p-1.5 bg-slate-800 rounded-lg text-white">
                    <ArrowRight className="w-5 h-5" />
                  </button>
                  <span className="text-[9px] text-red-500 mt-1 block text-center">32px</span>
                </div>
                <div className="relative">
                  <button className="p-0.5 rounded-full bg-slate-100">
                    <Info className="w-3.5 h-3.5 text-slate-400" />
                  </button>
                  <span className="text-[9px] text-red-500 mt-1 block text-center">18px</span>
                </div>
              </div>
            </MockCard>
          </div>
          <div>
            <Label type="after" />
            <MockCard>
              <div className="flex items-center gap-4 justify-center">
                <div className="relative">
                  <button className="p-3 bg-slate-800 rounded-lg text-white">
                    <ArrowRight className="w-5 h-5" />
                  </button>
                  <span className="text-[9px] text-green-600 mt-1 block text-center">46px ✓</span>
                </div>
                <div className="relative">
                  <button className="p-2 rounded-full bg-slate-100">
                    <Info className="w-4 h-4 text-slate-400" />
                  </button>
                  <span className="text-[9px] text-green-600 mt-1 block text-center">32px+</span>
                </div>
              </div>
            </MockCard>
          </div>
        </BeforeAfter>
      </Section>

      {/* 6. Search Placeholders */}
      <Section title="6. Placeholders ספציפיים (בינוני)">
        <BeforeAfter>
          <div>
            <Label type="before" />
            <MockCard>
              <div className="space-y-2">
                <div className="relative">
                  <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-300" />
                  <input readOnly className="w-full h-9 pr-9 pl-3 text-sm text-right bg-slate-50 border border-slate-200 rounded-lg text-slate-400" value="חיפוש פרויקט..." />
                </div>
                <div className="relative">
                  <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-300" />
                  <input readOnly className="w-full h-9 pr-9 pl-3 text-sm text-right bg-slate-50 border border-slate-200 rounded-lg text-slate-400" value="חיפוש ליקוי..." />
                </div>
              </div>
            </MockCard>
          </div>
          <div>
            <Label type="after" />
            <MockCard>
              <div className="space-y-2">
                <div className="relative">
                  <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-300" />
                  <input readOnly className="w-full h-9 pr-9 pl-3 text-sm text-right bg-slate-50 border border-slate-200 rounded-lg text-slate-400" value="חפש לפי שם, קוד או כתובת..." />
                </div>
                <div className="relative">
                  <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-300" />
                  <input readOnly className="w-full h-9 pr-9 pl-3 text-sm text-right bg-slate-50 border border-slate-200 rounded-lg text-slate-400" value="חפש לפי תיאור, קטגוריה או קבלן..." />
                </div>
              </div>
            </MockCard>
          </div>
        </BeforeAfter>
      </Section>

      {/* Summary */}
      <div className="bg-white rounded-xl border border-amber-200 p-5 mt-8">
        <h3 className="text-base font-bold text-slate-900 mb-3">סיכום — מה בפועל צריך לשנות</h3>
        <div className="space-y-2 text-sm text-slate-700">
          <div className="flex items-start gap-2">
            <span className="text-red-500 font-bold text-xs mt-0.5 bg-red-50 px-1.5 py-0.5 rounded">קריטי</span>
            <span><strong>LoginPage.js</strong> שורה 628 — הוסף <code className="bg-slate-100 px-1 rounded text-xs">dir="ltr"</code></span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-red-500 font-bold text-xs mt-0.5 bg-red-50 px-1.5 py-0.5 rounded">קריטי</span>
            <span><strong>ProjectDashboardPage.js</strong> שורה 242 — שנה <code className="bg-slate-100 px-1 rounded text-xs">min-h-screen</code> ל-<code className="bg-slate-100 px-1 rounded text-xs">min-h-0</code></span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-red-500 font-bold text-xs mt-0.5 bg-red-50 px-1.5 py-0.5 rounded">קריטי</span>
            <span><strong>UnitDetailPage.js</strong> שורה 271 — הוסף <code className="bg-slate-100 px-1 rounded text-xs">cursor-pointer</code> + ChevronLeft</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-amber-600 font-bold text-xs mt-0.5 bg-amber-50 px-1.5 py-0.5 rounded">בינוני</span>
            <span><strong>ProjectControlPage.js</strong> שורות 73-81 — החלף 6 אימוג'ים ב-Lucide</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-amber-600 font-bold text-xs mt-0.5 bg-amber-50 px-1.5 py-0.5 rounded">בינוני</span>
            <span><strong>ProjectDashboardPage.js</strong> שורה 245 — <code className="bg-slate-100 px-1 rounded text-xs">p-1.5</code> → <code className="bg-slate-100 px-1 rounded text-xs">p-3</code></span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-amber-600 font-bold text-xs mt-0.5 bg-amber-50 px-1.5 py-0.5 rounded">בינוני</span>
            <span><strong>TeamActivitySection.js</strong> שורה 72 — <code className="bg-slate-100 px-1 rounded text-xs">p-0.5</code> → <code className="bg-slate-100 px-1 rounded text-xs">p-2</code></span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-amber-600 font-bold text-xs mt-0.5 bg-amber-50 px-1.5 py-0.5 rounded">בינוני</span>
            <span><strong>4 קבצים</strong> — placeholders ספציפיים יותר</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-amber-600 font-bold text-xs mt-0.5 bg-amber-50 px-1.5 py-0.5 rounded">בינוני</span>
            <span><strong>ProjectControlPage.js</strong> שורה ~3370 — gradient scroll indicator לטאבים</span>
          </div>
        </div>
        <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500">
          כבר מתוקן בקוד: Badge Emergent ✓ | Empty state ✓ | Badge "לא עודכן" בכחול ✓ | צבע ציון דינמי ✓ | Project card hover ✓
        </div>
      </div>
    </div>
  );
}
