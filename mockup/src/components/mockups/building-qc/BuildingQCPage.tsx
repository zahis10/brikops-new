import { useState } from "react";
import {
  ArrowRight,
  ClipboardCheck,
  Layers,
  Search,
  Clock,
  AlertCircle,
  Lock,
  ShieldCheck,
  XCircle,
  ChevronLeft,
} from "lucide-react";

const QC_STATUS_ICONS: Record<string, any> = {
  not_started: Clock,
  in_progress: AlertCircle,
  pending_review: Lock,
  submitted: Lock,
  approved: ShieldCheck,
  rejected: XCircle,
};

const QC_STATUS_LABELS: Record<string, string> = {
  not_started: "לא התחיל",
  in_progress: "בביצוע",
  pending_review: "ממתין לאישור",
  submitted: "ממתין לאישור",
  approved: "אושר",
  rejected: "נדחה",
};

const QC_STATUS_COLORS: Record<string, { color: string; bg: string }> = {
  not_started: { color: "text-slate-400", bg: "bg-slate-50" },
  in_progress: { color: "text-amber-600", bg: "bg-amber-50" },
  pending_review: { color: "text-blue-600", bg: "bg-blue-50" },
  submitted: { color: "text-blue-600", bg: "bg-blue-50" },
  approved: { color: "text-emerald-600", bg: "bg-emerald-50" },
  rejected: { color: "text-red-600", bg: "bg-red-50" },
};

const QUALITY_BADGES: Record<string, { label: string; color: string } | null> = {
  passed: { label: "תקין", color: "bg-emerald-100 text-emerald-700" },
  failed: { label: "נכשל", color: "bg-red-100 text-red-700" },
  mixed: { label: "בביצוע", color: "bg-amber-100 text-amber-700" },
  not_started: null,
};

const FILTER_OPTIONS = [
  { id: "all", label: "הכל" },
  { id: "rejected", label: "נדחה" },
  { id: "pending_review", label: "ממתין לאישור" },
  { id: "in_progress", label: "בביצוע" },
  { id: "approved", label: "אושר" },
  { id: "not_started", label: "לא התחיל" },
];

interface Floor {
  id: string;
  name: string;
  qcStatus: string;
  quality: string | null;
}

const MOCK_FLOORS: Floor[] = [
  { id: "1", name: "קומת מרתף", qcStatus: "rejected", quality: "failed" },
  { id: "2", name: "קומת קרקע", qcStatus: "pending_review", quality: "mixed" },
  { id: "3", name: "קומה 1", qcStatus: "in_progress", quality: "mixed" },
  { id: "4", name: "קומה 2", qcStatus: "in_progress", quality: "mixed" },
  { id: "5", name: "קומה 3", qcStatus: "approved", quality: "passed" },
  { id: "6", name: "קומה 4", qcStatus: "not_started", quality: null },
  { id: "7", name: "קומה 5", qcStatus: "not_started", quality: null },
  { id: "8", name: "קומת גג", qcStatus: "not_started", quality: null },
];

const STATUS_ORDER: Record<string, number> = {
  rejected: 0,
  pending_review: 1,
  in_progress: 2,
  not_started: 3,
  approved: 5,
};

export function BuildingQCPage() {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");

  const statusCounts: Record<string, number> = {};
  MOCK_FLOORS.forEach((f) => {
    const normalized = f.qcStatus === "submitted" ? "pending_review" : f.qcStatus;
    statusCounts[normalized] = (statusCounts[normalized] || 0) + 1;
  });

  let filtered = MOCK_FLOORS;
  if (search.trim()) {
    const q = search.trim().toLowerCase();
    filtered = filtered.filter((f) => f.name.toLowerCase().includes(q));
  }
  if (filter !== "all") {
    if (filter === "pending_review") {
      filtered = filtered.filter(
        (f) => f.qcStatus === "pending_review" || f.qcStatus === "submitted"
      );
    } else {
      filtered = filtered.filter((f) => f.qcStatus === filter);
    }
  }
  filtered.sort(
    (a, b) =>
      (STATUS_ORDER[a.qcStatus] ?? 3) - (STATUS_ORDER[b.qcStatus] ?? 3)
  );

  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 font-sans">
      {/* Header */}
      <div className="sticky top-0 z-30 bg-slate-800 px-4 py-3 flex items-center gap-3">
        <button className="text-white hover:text-amber-300 transition-colors">
          <ArrowRight className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-white font-bold text-lg truncate leading-tight flex items-center gap-2">
            <ClipboardCheck className="w-4 h-4 text-amber-400" />
            בקרת ביצוע
          </h1>
          <p className="text-slate-300 text-xs truncate">בניין A — פרויקט נווה שאנן</p>
        </div>
        <div className="text-xs text-slate-400 whitespace-nowrap">{MOCK_FLOORS.length} קומות</div>
      </div>

      {/* Search + Filters */}
      <div className="px-4 pt-3 space-y-2.5">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="חיפוש קומה..."
            className="w-full pr-9 pl-3 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-amber-300"
          />
        </div>

        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              onClick={() => setFilter(opt.id)}
              className={`whitespace-nowrap px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === opt.id
                  ? "bg-slate-700 text-white"
                  : "bg-white border border-slate-200 text-slate-500 hover:border-slate-300"
              }`}
            >
              {opt.label}
              {opt.id === "all"
                ? ` (${MOCK_FLOORS.length})`
                : statusCounts[opt.id]
                ? ` (${statusCounts[opt.id]})`
                : ""}
            </button>
          ))}
        </div>
      </div>

      {/* Floor List */}
      <div className="px-4 pt-3 pb-6 space-y-1.5">
        {filtered.length === 0 ? (
          <div className="text-center py-8">
            <Layers className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500">אין קומות מתאימות לפילטר</p>
          </div>
        ) : (
          filtered.map((floor) => {
            const status = floor.qcStatus;
            const vs = QC_STATUS_COLORS[status] || QC_STATUS_COLORS.not_started;
            const Icon = QC_STATUS_ICONS[status] || Clock;
            const quality =
              floor.quality && QUALITY_BADGES[floor.quality]
                ? QUALITY_BADGES[floor.quality]
                : null;
            return (
              <button
                key={floor.id}
                className="w-full flex items-center justify-between px-4 py-3.5 bg-white rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors text-right"
              >
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Layers className="w-4 h-4 text-blue-500" />
                  </div>
                  <span className="text-sm font-bold text-slate-700">
                    {floor.name}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  {quality && (
                    <span
                      className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full ${quality.color}`}
                    >
                      {quality.label}
                    </span>
                  )}
                  <span
                    className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${vs.bg} ${vs.color}`}
                  >
                    <Icon className="w-3 h-3" />
                    {QC_STATUS_LABELS[status]}
                  </span>
                  <ChevronLeft className="w-3.5 h-3.5 text-slate-300" />
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
