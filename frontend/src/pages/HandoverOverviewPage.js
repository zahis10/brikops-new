import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { handoverService } from '../services/api';
import {
  ChevronRight, Loader2, Building2, FileSignature, ChevronDown, ChevronUp,
  AlertTriangle, X, Filter, Plus, Settings, FileSpreadsheet
} from 'lucide-react';
import ProjectSwitcher from '../components/ProjectSwitcher';
import NotificationBell from '../components/NotificationBell';
import UserDrawer from '../components/UserDrawer';
import G4ImportModal from '../components/handover/G4ImportModal';

const STATUS_COLORS = {
  signed:            { bg: '#dcfce7', border: '#86efac', text: '#166534', icon: '✓',  label: 'נמסר' },
  partially_signed:  { bg: '#fef3c7', border: '#fcd34d', text: '#92400e', icon: '✍', label: 'חתום חלקית' },
  in_progress:       { bg: '#dbeafe', border: '#93c5fd', text: '#1e40af', icon: '⋯',  label: 'בתהליך' },
  draft:             { bg: '#f1f5f9', border: '#cbd5e1', text: '#475569', icon: '○',  label: 'טיוטה' },
  none:              { bg: '#ffffff', border: '#d1d5db', text: '#9ca3af', icon: '',   label: 'טרם התחיל' },
};

const STATUS_OPTIONS = [
  { value: 'none',              label: 'טרם התחיל' },
  { value: 'draft',             label: 'טיוטה' },
  { value: 'in_progress',       label: 'בתהליך' },
  { value: 'partially_signed',  label: 'חתום חלקית' },
  { value: 'signed',            label: 'נמסר' },
];

const TYPE_LABELS = { initial: 'ראשונית', final: 'חזקה' };

const STAT_CARDS = [
  { key: 'total_units',      label: 'סה"כ יחידות',   color: 'bg-slate-100 text-slate-700',   dimStatuses: null },
  { key: 'signed',           label: 'נמסר',           color: 'bg-green-100 text-green-700',   dimStatuses: ['signed'] },
  { key: 'partially_signed', label: 'חתום חלקית',     color: 'bg-amber-100 text-amber-700',   dimStatuses: ['partially_signed'] },
  { key: 'pending',          label: 'ממתין',           color: 'bg-blue-100 text-blue-700',     dimStatuses: ['draft', 'in_progress'] },
  { key: 'not_started',      label: 'טרם התחילו',     color: 'bg-white text-slate-500 border border-slate-200', dimStatuses: ['none'] },
];

export default function HandoverOverviewPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({ building: '', status: [], type: '' });
  const [dimFilter, setDimFilter] = useState(null);
  const [expandedBuildings, setExpandedBuildings] = useState({});
  const [popover, setPopover] = useState(null);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false);
  const [legalModalOpen, setLegalModalOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const popoverRef = useRef(null);
  const statusDropdownRef = useRef(null);

  const fetchData = useCallback(async (currentFilters) => {
    try {
      setLoading(true);
      setError(null);
      const params = {};
      if (currentFilters.building) params.building = currentFilters.building;
      if (currentFilters.status.length > 0) params.status = currentFilters.status.join(',');
      if (currentFilters.type) params.type = currentFilters.type;
      const result = await handoverService.getOverview(projectId, params);
      setData(result);
      const expanded = {};
      for (const b of result.buildings) {
        expanded[b.building_id] = true;
      }
      setExpandedBuildings(prev => {
        const merged = { ...expanded };
        for (const key of Object.keys(prev)) {
          if (key in merged) merged[key] = prev[key];
        }
        return merged;
      });
    } catch (err) {
      console.error('[HandoverOverview] load error', err);
      setError('שגיאה בטעינת נתוני מסירות');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { fetchData(filters); }, [fetchData, filters]);

  useEffect(() => {
    const handleClick = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        setPopover(null);
      }
      if (statusDropdownRef.current && !statusDropdownRef.current.contains(e.target)) {
        setStatusDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleStatClick = (card) => {
    if (!card.dimStatuses) return;
    setDimFilter(prev => prev === card.key ? null : card.key);
  };

  const handleFilterChange = (key, value) => {
    setDimFilter(null);
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleStatusToggle = (statusValue) => {
    setDimFilter(null);
    setFilters(prev => {
      const current = prev.status;
      const next = current.includes(statusValue)
        ? current.filter(s => s !== statusValue)
        : [...current, statusValue];
      return { ...prev, status: next };
    });
  };

  const handleClearAll = () => {
    setDimFilter(null);
    setFilters({ building: '', status: [], type: '' });
  };

  const hasActiveFilters = filters.building || filters.status.length > 0 || filters.type;

  const toggleBuilding = (id) => {
    setExpandedBuildings(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const isDimmed = (unitStatus) => {
    if (!dimFilter) return false;
    const card = STAT_CARDS.find(c => c.key === dimFilter);
    if (!card?.dimStatuses) return false;
    return !card.dimStatuses.includes(unitStatus);
  };

  const handleCellClick = (unit, buildingName, e) => {
    const protocols = unit.protocols || [];
    if (protocols.length === 1) {
      navigate(`/projects/${projectId}/units/${unit.unit_id}/handover/${protocols[0].id}`);
      return;
    }
    const rect = e.currentTarget.getBoundingClientRect();
    setPopover({
      unit,
      buildingName,
      x: rect.left + rect.width / 2,
      y: rect.bottom + 4,
    });
  };

  const handleCreateFromPopover = (unitId, protocolType) => {
    setPopover(null);
    navigate(`/projects/${projectId}/units/${unitId}/handover?create=${protocolType}`);
  };

  const summary = data?.summary || { total_units: 0, signed: 0, partially_signed: 0, pending: 0, not_started: 0 };
  const buildings = data?.buildings || [];
  const filterOptions = data?.filters || { buildings: [], types: ['initial', 'final'] };

  const FilterContent = () => (
    <div className="flex flex-wrap items-center gap-2">
      <select
        value={filters.building}
        onChange={(e) => handleFilterChange('building', e.target.value)}
        className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 min-w-[120px]"
      >
        <option value="">כל המבנים</option>
        {filterOptions.buildings.map(b => (
          <option key={b} value={b}>{b}</option>
        ))}
      </select>

      <div className="relative" ref={statusDropdownRef}>
        <button
          onClick={() => setStatusDropdownOpen(prev => !prev)}
          className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 flex items-center gap-1"
        >
          סטטוס {filters.status.length > 0 && <span className="bg-blue-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">{filters.status.length}</span>}
        </button>
        {statusDropdownOpen && (
          <div className="absolute top-full right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-50 min-w-[180px]">
            {STATUS_OPTIONS.map(opt => (
              <label key={opt.value} className="flex items-center gap-2 px-3 py-2 hover:bg-slate-50 cursor-pointer text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={filters.status.includes(opt.value)}
                  onChange={() => handleStatusToggle(opt.value)}
                  className="rounded border-slate-300"
                />
                <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ backgroundColor: STATUS_COLORS[opt.value].bg, border: `1px solid ${STATUS_COLORS[opt.value].border}` }} />
                {opt.label}
              </label>
            ))}
          </div>
        )}
      </div>

      <select
        value={filters.type}
        onChange={(e) => handleFilterChange('type', e.target.value)}
        className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700"
      >
        <option value="">הכל</option>
        {filterOptions.types.map(t => (
          <option key={t} value={t}>{TYPE_LABELS[t] || t}</option>
        ))}
      </select>

      {hasActiveFilters && (
        <button
          onClick={handleClearAll}
          className="text-sm text-red-500 hover:text-red-700 flex items-center gap-1 px-2 py-1"
        >
          <X className="w-3.5 h-3.5" />
          נקה הכל
        </button>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 pb-20" dir="rtl">
      <header className="bg-gradient-to-br from-slate-900 to-slate-800 text-white sticky top-0 z-50 shadow-md">
        <div className="max-w-[1100px] mx-auto px-4 py-3 flex items-center gap-2">
          <button onClick={() => navigate(`/projects/${projectId}`)} className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors">
            <ChevronRight className="w-4 h-4" />
          </button>
          <ProjectSwitcher currentProjectId={projectId} />
          <div className="flex-1" />
          <NotificationBell />
          <UserDrawer user={user} />
        </div>
      </header>

      <div className="max-w-[1100px] mx-auto px-4 pt-4">
        <div className="flex items-center gap-2 mb-4">
          <FileSignature className="w-5 h-5 text-amber-500" />
          <h1 className="text-lg font-bold text-slate-800">מסירות</h1>
          <div className="flex-1" />
          {data?.can_manage_legal && (
            <button
              onClick={() => setImportModalOpen(true)}
              className="flex items-center gap-1.5 text-xs text-emerald-600 hover:text-emerald-800 font-medium px-3 py-1.5 border border-emerald-200 rounded-lg hover:bg-emerald-50 transition-colors"
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              ייבוא רוכשים
            </button>
          )}
          {data?.can_manage_legal && data?.org_id && (
            <button
              onClick={() => setLegalModalOpen(true)}
              className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium px-3 py-1.5 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
            >
              <Settings className="w-3.5 h-3.5" />
              הגדרות נסחים
            </button>
          )}
        </div>

        {loading && !data ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
            <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
            <p className="text-sm text-red-600">{error}</p>
            <button onClick={() => fetchData(filters)} className="mt-3 text-xs text-red-500 underline">נסה שוב</button>
          </div>
        ) : summary.total_units === 0 && !hasActiveFilters ? (
          <div className="bg-white border border-slate-200 rounded-xl p-8 text-center">
            <FileSignature className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <h2 className="text-sm font-semibold text-slate-600 mb-1">אין יחידות בפרויקט</h2>
            <p className="text-xs text-slate-400">הגדירו מבנה פרויקט כדי להתחיל</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Zone 1: Stats Bar */}
            <div className="overflow-x-auto -mx-4 px-4">
              <div className="flex gap-3 min-w-max">
                {STAT_CARDS.map(card => {
                  const value = summary[card.key];
                  const pct = summary.total_units > 0 && card.key !== 'total_units'
                    ? Math.round((value / summary.total_units) * 100)
                    : null;
                  const isActive = dimFilter === card.key;
                  return (
                    <button
                      key={card.key}
                      onClick={() => handleStatClick(card)}
                      className={`flex-shrink-0 rounded-xl px-4 py-3 text-right transition-all min-w-[110px]
                        ${card.color}
                        ${isActive ? 'ring-2 ring-offset-1 ring-blue-500 shadow-md scale-[1.03]' : ''}
                        ${card.dimStatuses ? 'cursor-pointer hover:shadow-sm active:scale-[0.98]' : 'cursor-default'}
                      `}
                    >
                      <div className="text-3xl font-extrabold leading-none">{value}</div>
                      <div className="text-xs mt-1 opacity-80">{card.label}</div>
                      {pct !== null && <div className="text-[10px] mt-0.5 opacity-60">{pct}%</div>}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Color Legend */}
            <div className="flex flex-wrap gap-3 text-xs text-slate-600">
              {Object.entries(STATUS_COLORS).map(([key, c]) => (
                <span key={key} className="flex items-center gap-1">
                  <span
                    className="w-3 h-3 rounded-sm inline-block"
                    style={{
                      backgroundColor: c.bg,
                      border: key === 'none' ? '1px dashed #9ca3af' : `1px solid ${c.border}`,
                    }}
                  />
                  {c.label}
                </span>
              ))}
            </div>

            {/* Zone 2: Filter Bar — Desktop */}
            <div className="hidden sm:block bg-white border border-slate-200 rounded-xl p-3">
              <FilterContent />
            </div>

            {/* Zone 2: Filter Bar — Mobile */}
            <div className="sm:hidden">
              <button
                onClick={() => setMobileFilterOpen(true)}
                className="flex items-center gap-2 text-sm text-slate-600 bg-white border border-slate-200 rounded-xl px-4 py-2.5 w-full justify-center"
              >
                <Filter className="w-4 h-4" />
                סינון
                {hasActiveFilters && <span className="bg-blue-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">{filters.status.length + (filters.building ? 1 : 0) + (filters.type ? 1 : 0)}</span>}
              </button>
            </div>

            {/* Mobile filter bottom sheet */}
            {mobileFilterOpen && (
              <div className="fixed inset-0 z-50 sm:hidden">
                <div className="absolute inset-0 bg-black/40" onClick={() => setMobileFilterOpen(false)} />
                <div className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl p-4 space-y-4 max-h-[70vh] overflow-y-auto">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-800">סינון</h3>
                    <button onClick={() => setMobileFilterOpen(false)} className="p-1">
                      <X className="w-5 h-5 text-slate-400" />
                    </button>
                  </div>
                  <div className="space-y-3">
                    <div>
                      <label className="text-xs font-medium text-slate-500 mb-1 block">מבנה</label>
                      <select
                        value={filters.building}
                        onChange={(e) => handleFilterChange('building', e.target.value)}
                        className="text-sm border border-slate-200 rounded-lg px-3 py-2.5 bg-white text-slate-700 w-full"
                      >
                        <option value="">כל המבנים</option>
                        {filterOptions.buildings.map(b => (
                          <option key={b} value={b}>{b}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-slate-500 mb-1 block">סטטוס</label>
                      <div className="space-y-1">
                        {STATUS_OPTIONS.map(opt => (
                          <label key={opt.value} className="flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-slate-50 cursor-pointer text-sm text-slate-700">
                            <input
                              type="checkbox"
                              checked={filters.status.includes(opt.value)}
                              onChange={() => handleStatusToggle(opt.value)}
                              className="rounded border-slate-300"
                            />
                            <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ backgroundColor: STATUS_COLORS[opt.value].bg, border: `1px solid ${STATUS_COLORS[opt.value].border}` }} />
                            {opt.label}
                          </label>
                        ))}
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-slate-500 mb-1 block">סוג</label>
                      <select
                        value={filters.type}
                        onChange={(e) => handleFilterChange('type', e.target.value)}
                        className="text-sm border border-slate-200 rounded-lg px-3 py-2.5 bg-white text-slate-700 w-full"
                      >
                        <option value="">הכל</option>
                        {filterOptions.types.map(t => (
                          <option key={t} value={t}>{TYPE_LABELS[t] || t}</option>
                        ))}
                      </select>
                    </div>
                    {hasActiveFilters && (
                      <button
                        onClick={() => { handleClearAll(); setMobileFilterOpen(false); }}
                        className="w-full text-sm text-red-500 border border-red-200 rounded-lg py-2.5 flex items-center justify-center gap-1"
                      >
                        <X className="w-3.5 h-3.5" /> נקה הכל
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {loading && (
              <div className="flex justify-center py-4">
                <Loader2 className="w-5 h-5 text-amber-500 animate-spin" />
              </div>
            )}

            {/* Zone 3: Building Grid */}
            {buildings.map(b => {
              const expanded = expandedBuildings[b.building_id] !== false;
              const floorCount = b.floors?.length || 0;
              return (
                <div key={b.building_id} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                  <button
                    onClick={() => toggleBuilding(b.building_id)}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors"
                  >
                    <Building2 className="w-5 h-5 text-slate-400 flex-shrink-0" />
                    <div className="flex-1 text-right min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-800">{b.building_name}</span>
                        <span className="text-[10px] text-slate-400">דירות {b.total_units} · קומות {floorCount}</span>
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden" dir="ltr">
                          <div
                            className="h-full bg-green-500 rounded-full transition-all"
                            style={{ width: `${b.progress_pct}%`, marginLeft: 'auto' }}
                          />
                        </div>
                        <span className="text-[10px] text-slate-500 font-medium w-8 text-left">{b.progress_pct}%</span>
                      </div>
                    </div>
                    {expanded ? <ChevronUp className="w-4 h-4 text-slate-400 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />}
                  </button>

                  {expanded && (
                    <div className="border-t border-slate-100">
                      {b.floors?.map((floor, fi) => (
                        <div key={fi} className={`flex items-start gap-2 px-3 py-2 ${fi > 0 ? 'border-t border-slate-50' : ''}`}>
                          <div className="w-14 flex-shrink-0 text-left pt-1">
                            <span className="text-[11px] font-medium text-slate-400">{floor.floor_name || `קומה ${floor.floor}`}</span>
                          </div>
                          <div className="flex-1 flex flex-wrap gap-1.5">
                            {floor.units?.map(unit => {
                              const sc = STATUS_COLORS[unit.status] || STATUS_COLORS.none;
                              const dimmed = isDimmed(unit.status);
                              const sigInfo = unit.protocols?.find(p => p.status === 'partially_signed');
                              return (
                                <button
                                  key={unit.unit_id}
                                  onClick={(e) => handleCellClick(unit, b.building_name, e)}
                                  title={`${sc.label}${unit.open_defects > 0 ? ` · ${unit.open_defects} ליקויים` : ''}${unit.spare_tiles_count === 0 ? ' · אין ריצוף ספייר' : unit.spare_tiles_count == null ? ' · לא עודכן ריצוף ספייר' : ''}`}
                                  className={`relative min-w-[44px] min-h-[44px] w-[52px] h-[52px] rounded-lg flex flex-col items-center justify-center
                                    transition-all hover:scale-105 hover:shadow-md active:scale-95
                                    ${dimmed ? 'opacity-25' : ''}
                                  `}
                                  style={{
                                    backgroundColor: sc.bg,
                                    border: unit.status === 'none' ? `1.5px dashed ${sc.border}` : `1.5px solid ${sc.border}`,
                                  }}
                                >
                                  {unit.open_defects > 0 && (
                                    <span className="absolute -top-1 -left-1 bg-red-500 text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center leading-none">
                                      {unit.open_defects > 9 ? '9+' : unit.open_defects}
                                    </span>
                                  )}
                                  {(unit.spare_tiles_count === 0 || unit.spare_tiles_count == null) && (
                                    <span className={`absolute -bottom-1 -left-1 rounded-full w-3 h-3 border border-white ${unit.spare_tiles_count === 0 ? 'bg-amber-500' : 'bg-blue-400'}`} />
                                  )}
                                  <span className="text-xs font-bold leading-none" style={{ color: sc.text }}>
                                    {unit.apartment_number}
                                  </span>
                                  {sc.icon && (
                                    <span className="text-[10px] mt-0.5 leading-none" style={{ color: sc.text }}>
                                      {sc.icon}
                                    </span>
                                  )}
                                  {unit.status === 'partially_signed' && sigInfo && (
                                    <span className="text-[9px] leading-none mt-0.5" style={{ color: sc.text }}>
                                      {sigInfo.signature_count}/{sigInfo.signatures_total}
                                    </span>
                                  )}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {buildings.length === 0 && !loading && (
              <div className="bg-white border border-slate-200 rounded-xl p-6 text-center">
                <p className="text-sm text-slate-500">לא נמצאו תוצאות עם הסינון הנוכחי</p>
                {hasActiveFilters && (
                  <button onClick={handleClearAll} className="mt-2 text-xs text-blue-500 underline">נקה סינון</button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {importModalOpen && (
        <G4ImportModal
          projectId={projectId}
          onClose={() => setImportModalOpen(false)}
        />
      )}

      {legalModalOpen && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setLegalModalOpen(false)} />
          <div className="absolute inset-x-4 top-[30%] sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2 sm:w-full sm:max-w-md bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden" dir="rtl">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
              <h2 className="text-sm font-bold text-slate-800">נסחים משפטיים</h2>
              <button onClick={() => setLegalModalOpen(false)} className="p-1 hover:bg-slate-100 rounded-lg">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <p className="text-sm text-slate-600">נסחים משפטיים מנוהלים כעת דרך עורך תבניות המסירה.</p>
              <p className="text-xs text-slate-400">פתחו את תבנית המסירה מדף ניהול תבניות ועברו לטאב "נסחים משפטיים".</p>
              <button
                onClick={() => { setLegalModalOpen(false); window.location.href = '/admin/qc-templates'; }}
                className="w-full py-2.5 text-sm text-purple-600 hover:bg-purple-50 flex items-center gap-1.5 justify-center rounded-xl border border-purple-200 transition-colors font-medium"
              >
                עבור לניהול תבניות
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Unit popover */}
      {popover && (
        <div
          ref={popoverRef}
          className="fixed z-50 bg-white border border-slate-200 rounded-xl shadow-xl p-3 min-w-[220px]"
          style={{
            left: `${Math.min(popover.x, window.innerWidth - 240)}px`,
            top: `${Math.min(popover.y, window.innerHeight - 200)}px`,
            transform: 'translateX(-50%)',
          }}
        >
          <div className="text-xs text-slate-400 mb-2">דירה {popover.unit.apartment_number} · {popover.buildingName}</div>

          {popover.unit.protocols.length > 0 ? (
            <div className="space-y-1.5">
              {popover.unit.protocols.map(p => {
                const sc = STATUS_COLORS[p.status] || STATUS_COLORS.draft;
                return (
                  <button
                    key={p.id}
                    onClick={() => { setPopover(null); navigate(`/projects/${projectId}/units/${popover.unit.unit_id}/handover/${p.id}`); }}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-50 transition-colors text-right"
                  >
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: sc.border }} />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-slate-700">
                        {p.type === 'initial' ? 'מסירה ראשונית' : 'מסירת חזקה'}
                      </span>
                      <span className="text-[11px] text-slate-400 mr-1">
                        — {sc.label}
                        {p.status === 'partially_signed' && ` (${p.signature_count}/${p.signatures_total})`}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="space-y-1.5">
              <button
                onClick={() => handleCreateFromPopover(popover.unit.unit_id, 'initial')}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-purple-50 hover:bg-purple-100 text-purple-700 text-sm font-medium transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                התחל מסירה ראשונית
              </button>
              <button
                onClick={() => handleCreateFromPopover(popover.unit.unit_id, 'final')}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-700 text-sm font-medium transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                התחל מסירת חזקה
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
