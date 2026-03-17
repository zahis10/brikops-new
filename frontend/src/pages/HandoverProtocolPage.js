import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { handoverService } from '../services/api';
import { toast } from 'sonner';
import { t } from '../i18n';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import {
  ArrowRight, Loader2, ChevronDown, ChevronUp, ShieldCheck,
  Home, Users, Gauge, Package, FileText, Scale, PenLine,
  AlertTriangle, Lock, ArrowLeft, CheckCircle2, Bug, Clock,
  Circle, ChevronLeft, FileDown, Share2
} from 'lucide-react';
import HandoverPropertyForm from '../components/handover/HandoverPropertyForm';
import HandoverTenantForm from '../components/handover/HandoverTenantForm';
import HandoverMeterForm from '../components/handover/HandoverMeterForm';
import HandoverDeliveredItems from '../components/handover/HandoverDeliveredItems';
import HandoverGeneralNotes from '../components/handover/HandoverGeneralNotes';
import HandoverLegalSections from '../components/handover/HandoverLegalSections';
import SignatureSection from '../components/handover/SignatureSection';

const API = process.env.REACT_APP_BACKEND_URL || '';

const ENGINE_SECTIONS = [
  { key: 'property', label: t('handover', 'propertyDetails'), icon: Home, visibleTypes: ['initial', 'final'] },
  { key: 'tenants', label: t('handover', 'tenants'), icon: Users, visibleTypes: ['initial', 'final'] },
  { key: 'meters', label: t('handover', 'meters'), icon: Gauge, visibleTypes: ['final'] },
  { key: 'delivered', label: t('handover', 'deliveredItems'), icon: Package, visibleTypes: ['final'] },
  { key: 'notes', label: t('handover', 'generalNotes'), icon: FileText, visibleTypes: ['initial', 'final'] },
];

const STATUS_BADGE = {
  draft: { label: t('handover', 'draft'), color: 'bg-white/20 text-white' },
  in_progress: { label: t('handover', 'inProgress'), color: 'bg-white/20 text-white' },
  partially_signed: { label: t('handover', 'partiallySigned'), color: 'bg-amber-400/30 text-amber-100' },
  signed: { label: t('handover', 'signed'), color: 'bg-green-400/30 text-green-100' },
};

const ProgressRing = ({ checked, total, size = 36, strokeWidth = 3, textClass = '' }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = total > 0 ? checked / total : 0;
  const offset = circumference * (1 - pct);
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="rotate-[-90deg]">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth={strokeWidth} />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={pct >= 1 ? '#22c55e' : '#a78bfa'} strokeWidth={strokeWidth}
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.5s ease' }} />
      </svg>
      <span className={`absolute font-extrabold ${textClass || 'text-[9px] text-slate-600'}`}>
        {total > 0 ? Math.round(pct * 100) : 0}%
      </span>
    </div>
  );
};

const ProgressRingLight = ({ checked, total, size = 44, strokeWidth = 3.5 }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = total > 0 ? checked / total : 0;
  const offset = circumference * (1 - pct);
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="rotate-[-90deg]">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e2e8f0" strokeWidth={strokeWidth} />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={pct >= 1 ? '#22c55e' : '#a78bfa'} strokeWidth={strokeWidth}
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.5s ease' }} />
      </svg>
      <span className="absolute text-[10px] font-bold text-slate-600">
        {total > 0 ? Math.round(pct * 100) : 0}%
      </span>
    </div>
  );
};

const HandoverProtocolPage = () => {
  const { projectId, unitId, protocolId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [protocol, setProtocol] = useState(null);
  const [loading, setLoading] = useState(true);
  const [metadataOpen, setMetadataOpen] = useState(false);
  const [expandedEngine, setExpandedEngine] = useState(null);
  const [userRole, setUserRole] = useState(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [shareLoading, setShareLoading] = useState(false);
  const [legalOpen, setLegalOpen] = useState(true);
  const [signaturesOpen, setSignaturesOpen] = useState(true);
  const signatureRef = useRef(null);

  const loadProtocol = useCallback(async () => {
    try {
      setLoading(true);
      const data = await handoverService.getProtocol(projectId, protocolId);
      setProtocol(data);
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'loadError'));
    } finally {
      setLoading(false);
    }
  }, [projectId, protocolId]);

  useEffect(() => { loadProtocol(); }, [loadProtocol]);

  useEffect(() => {
    const fetchRole = async () => {
      try {
        const token = localStorage.getItem('token');
        const res = await axios.get(`${API}/api/projects/${projectId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setUserRole(res.data?.my_role || null);
        if (user?.platform_role === 'super_admin') setUserRole('super_admin');
      } catch { setUserRole(null); }
    };
    fetchRole();
  }, [projectId, user]);

  const handleFormUpdated = useCallback(() => { loadProtocol(); }, [loadProtocol]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
      </div>
    );
  }

  if (!protocol) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4" dir="rtl">
        <p className="text-slate-500">{t('handover', 'loadError')}</p>
        <button onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover`)}
          className="text-purple-600 hover:text-purple-700 font-medium">
          {t('handover', 'backToHandover')}
        </button>
      </div>
    );
  }

  const isLocked = protocol.locked === true;
  const statusInfo = STATUS_BADGE[protocol.status] || STATUS_BADGE.draft;
  const typeLabel = protocol.type === 'initial'
    ? t('handover', 'initialProtocol')
    : t('handover', 'finalProtocol');

  const templateSections = protocol.sections || [];
  const totalItems = templateSections.reduce((sum, s) => sum + (s.items?.length || 0), 0);
  const checkedItems = templateSections.reduce(
    (sum, s) => sum + (s.items?.filter(i => i.status && i.status !== 'not_checked').length || 0), 0
  );
  const okItems = templateSections.reduce(
    (sum, s) => sum + (s.items?.filter(i => i.status === 'ok').length || 0), 0
  );
  const defectCount = templateSections.reduce(
    (sum, s) => sum + (s.items?.filter(i => i.defect_id).length || 0), 0
  );
  const remainingItems = totalItems - checkedItems;
  const pct = totalItems > 0 ? Math.round((checkedItems / totalItems) * 100) : 0;

  const sectionStats = (section) => {
    const items = section.items || [];
    const total = items.length;
    const checked = items.filter(i => i.status && i.status !== 'not_checked').length;
    const defects = items.filter(i => i.defect_id).length;
    return { total, checked, defects };
  };

  const continueSection = (() => {
    if (pct >= 100) return null;
    let partial = null;
    let empty = null;
    for (const s of templateSections) {
      const stats = sectionStats(s);
      if (stats.checked > 0 && stats.checked < stats.total && !partial) partial = s;
      if (stats.checked === 0 && !empty) empty = s;
    }
    return partial || empty || null;
  })();

  const groupedSections = (() => {
    const issues = [];
    const inProgress = [];
    const notStarted = [];
    const completed = [];
    for (const s of templateSections) {
      const stats = sectionStats(s);
      if (stats.defects > 0) { issues.push({ section: s, stats }); }
      else if (stats.checked > 0 && stats.checked < stats.total) { inProgress.push({ section: s, stats }); }
      else if (stats.checked === 0) { notStarted.push({ section: s, stats }); }
      else { completed.push({ section: s, stats }); }
    }
    return { issues, inProgress, notStarted, completed };
  })();

  const allSameGroup = [groupedSections.issues, groupedSections.inProgress, groupedSections.notStarted, groupedSections.completed]
    .filter(g => g.length > 0).length <= 1;

  const hasLegalSections = (protocol?.legal_sections || []).length > 0;
  const visibleEngineSections = ENGINE_SECTIONS.filter(es => {
    if (!es.visibleTypes.includes(protocol.type || 'initial')) return false;
    return true;
  });

  const renderEngineContent = (key) => {
    const formProps = { protocol, projectId, isSigned: isLocked, onUpdated: handleFormUpdated };
    switch (key) {
      case 'property': return <HandoverPropertyForm {...formProps} />;
      case 'tenants': return <HandoverTenantForm {...formProps} />;
      case 'meters': return <HandoverMeterForm {...formProps} />;
      case 'delivered': return <HandoverDeliveredItems {...formProps} />;
      case 'notes': return <HandoverGeneralNotes {...formProps} />;
      default: return null;
    }
  };

  const buildPdfFilename = () => {
    const type = protocol.type || 'initial';
    const apt = (protocol.snapshot?.unit_name || '').replace(/[^\w\u0590-\u05FF]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '') || protocolId.slice(0, 8);
    const floor = (protocol.snapshot?.floor_name || '').replace(/[^\w\u0590-\u05FF]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
    return `protocol_mesira_${type}_${apt}${floor ? '_' + floor : ''}.pdf`;
  };

  const handlePdfError = (err) => {
    console.error('PDF error:', err);
    if (err?.response?.status === 400) {
      toast.error('ניתן להוריד PDF רק לפרוטוקול חתום');
    } else if (err?.response?.status === 504) {
      toast.error('יצירת ה-PDF לקחה יותר מדי זמן, נסו שוב');
    } else if (err?.response?.status >= 500) {
      toast.error('שגיאה ביצירת PDF, נסו שוב');
    } else {
      toast.error('שגיאת רשת');
    }
  };

  const handleDownloadPdf = async () => {
    setPdfLoading(true);
    try {
      const blob = await handoverService.getPdfBlob(projectId, protocolId);
      const filename = buildPdfFilename();
      const url = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      URL.revokeObjectURL(url);
      a.remove();
    } catch (err) {
      handlePdfError(err);
    } finally {
      setPdfLoading(false);
    }
  };

  const handleSharePdf = async () => {
    setShareLoading(true);
    try {
      const blob = await handoverService.getPdfBlob(projectId, protocolId);
      const filename = buildPdfFilename();
      const file = new File([blob], filename, { type: 'application/pdf' });
      if (navigator.canShare?.({ files: [file] })) {
        const projectName = protocol.snapshot?.project_name || '';
        const apartment = protocol.snapshot?.unit_name || '';
        await navigator.share({
          title: 'פרוטוקול מסירה',
          text: `פרוטוקול מסירה — ${projectName}${apartment ? ', דירה ' + apartment : ''}`,
          files: [file],
        });
      } else {
        const url = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();
      }
    } catch (err) {
      if (err?.name !== 'AbortError') {
        handlePdfError(err);
      }
    } finally {
      setShareLoading(false);
    }
  };

  const handleSignFAB = () => {
    signatureRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const renderSectionCard = ({ section, stats }, accent) => (
    <button
      key={section.section_id}
      onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}/sections/${section.section_id}`)}
      className={`w-full flex items-center gap-3 p-3 rounded-xl border bg-white transition-all active:scale-[0.98] hover:shadow-sm
        ${accent === 'red' ? 'border-r-[3px] border-r-red-400 border-slate-200' : ''}
        ${accent === 'blue' ? 'border-r-[3px] border-r-blue-400 border-slate-200' : ''}
        ${accent === 'green' ? 'border-r-[3px] border-r-green-400 border-slate-200 opacity-70' : ''}
        ${accent === 'none' ? 'border-slate-200' : ''}
        ${!accent ? 'border-slate-200' : ''}`}
    >
      <ProgressRingLight checked={stats.checked} total={stats.total} />
      <div className="flex-1 min-w-0 text-right">
        <h3 className="text-sm font-bold text-slate-800 truncate">{section.name}</h3>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-[11px] text-slate-500">{stats.checked}/{stats.total} פריטים</span>
          {stats.defects > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-600 font-medium flex items-center gap-0.5">
              <Bug className="w-2.5 h-2.5" />{stats.defects} ליקויים
            </span>
          )}
          {stats.checked === stats.total && stats.total > 0 && stats.defects === 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-100 text-green-600 font-medium">הושלם ✓</span>
          )}
        </div>
      </div>
      <ChevronLeft className="w-4 h-4 text-slate-300 flex-shrink-0" />
    </button>
  );

  const renderGroup = (label, items, accent) => {
    if (items.length === 0) return null;
    return (
      <div className="space-y-1.5">
        {!allSameGroup && (
          <h3 className="text-[11px] font-semibold text-slate-500 px-1 mt-3">{label} ({items.length})</h3>
        )}
        {items.map(item => renderSectionCard(item, accent))}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="bg-gradient-to-bl from-[#1e1b4b] to-[#312e81] text-white">
        <div className="max-w-lg mx-auto px-4 pt-3 pb-5">
          <div className="flex items-center gap-3 mb-4">
            <button onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover`)}
              className="p-1.5 hover:bg-white/10 rounded-lg transition-colors">
              <ArrowRight className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-extrabold">{typeLabel}</h1>
                {isLocked && <Lock className="w-4 h-4 text-indigo-300" />}
              </div>
              <div className="flex items-center gap-1.5 text-indigo-300 text-xs mt-0.5">
                {protocol.snapshot?.building_name && <span>{protocol.snapshot.building_name}</span>}
                {protocol.snapshot?.unit_name && <><span>·</span><span>{protocol.snapshot.unit_name}</span></>}
              </div>
            </div>
            <span className={`text-[10px] px-2.5 py-1 rounded-full font-medium ${statusInfo.color}`}>
              {statusInfo.label} — {pct}%
            </span>
          </div>

          <div className="flex items-center justify-center mb-4">
            <ProgressRing checked={checkedItems} total={totalItems} size={64} strokeWidth={5}
              textClass="text-sm text-white font-extrabold" />
          </div>

          <div className="grid grid-cols-4 gap-2">
            {[
              { label: 'נבדקו', value: `${checkedItems}/${totalItems}`, color: 'bg-purple-400/20', textColor: 'text-purple-200' },
              { label: 'תקין', value: okItems, color: 'bg-green-400/20', textColor: 'text-green-300' },
              { label: 'ליקויים', value: defectCount, color: 'bg-red-400/20', textColor: 'text-red-300' },
              { label: 'נותרו', value: remainingItems, color: 'bg-slate-400/20', textColor: 'text-slate-300' },
            ].map(stat => (
              <div key={stat.label} className={`${stat.color} rounded-xl p-2.5 text-center`}>
                <div className={`text-lg font-extrabold ${stat.textColor}`}>{stat.value}</div>
                <div className="text-[10px] text-indigo-300 font-medium">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {isLocked && (
        <div className="max-w-lg mx-auto px-4 mt-3">
          <div className="bg-green-50 border border-green-200 rounded-xl p-3 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-green-600 flex-shrink-0" />
            <span className="text-sm text-green-700 font-medium">{t('handover', 'readOnly')}</span>
            {protocol.signed_at && (
              <span className="text-xs text-green-600">
                {t('handover', 'signedOn')} {new Date(protocol.signed_at).toLocaleDateString('he-IL')}
              </span>
            )}
            <div className="mr-auto flex items-center gap-1.5">
              <button
                onClick={handleSharePdf}
                disabled={shareLoading}
                className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-60"
              >
                {shareLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Share2 className="w-3.5 h-3.5" />}
                שתף
              </button>
              <button
                onClick={handleDownloadPdf}
                disabled={pdfLoading}
                className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-60"
              >
                {pdfLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />}
                PDF
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-lg mx-auto px-4">
        {continueSection && (
          <button
            onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}/sections/${continueSection.section_id}`)}
            className="w-full mt-4 flex items-center gap-3 p-3.5 rounded-xl bg-gradient-to-l from-purple-500 to-purple-600 text-white shadow-lg active:scale-[0.98] transition-all"
          >
            <div className="flex-1 text-right min-w-0">
              <div className="text-[11px] text-purple-200 font-medium">המשך מאיפה שעצרת</div>
              <div className="text-sm font-bold truncate">
                {continueSection.name} ({sectionStats(continueSection).checked}/{sectionStats(continueSection).total} נבדקו)
              </div>
            </div>
            <ChevronLeft className="w-5 h-5 text-purple-200" />
          </button>
        )}

        <div className="mt-4">
          <button
            onClick={() => setMetadataOpen(!metadataOpen)}
            className="w-full flex items-center gap-2.5 p-3 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-colors"
          >
            <span className="text-base">📋</span>
            <span className="flex-1 text-right text-sm font-medium text-slate-700 truncate">
              פרטי פרוטוקול — נכס · דיירים
            </span>
            {metadataOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>

          {metadataOpen && (
            <div className="mt-1.5 space-y-1.5">
              {visibleEngineSections.map(es => (
                <div key={es.key} className="border border-slate-200 rounded-xl bg-white overflow-hidden">
                  <button
                    onClick={() => setExpandedEngine(expandedEngine === es.key ? null : es.key)}
                    className="w-full p-3 flex items-center gap-3 text-right hover:bg-slate-50 transition-colors"
                  >
                    <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center flex-shrink-0">
                      <es.icon className="w-4 h-4 text-indigo-500" />
                    </div>
                    <span className="flex-1 text-sm font-medium text-slate-700">{es.label}</span>
                    {expandedEngine === es.key
                      ? <ChevronUp className="w-4 h-4 text-slate-400" />
                      : <ChevronDown className="w-4 h-4 text-slate-400" />}
                  </button>
                  {expandedEngine === es.key && (
                    <div className="px-3 pb-3 pt-1 border-t border-slate-100">
                      {renderEngineContent(es.key)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="mt-5 space-y-1.5">
          <h2 className="text-sm font-semibold text-slate-500 px-1">
            סקציות ({templateSections.length})
          </h2>

          {templateSections.length === 0 && (
            <p className="text-sm text-slate-400 text-center py-6">{t('handover', 'noSections')}</p>
          )}

          {allSameGroup ? (
            templateSections.map(section => {
              const stats = sectionStats(section);
              return renderSectionCard({ section, stats }, 'none');
            })
          ) : (
            <>
              {renderGroup('⚠️ דורש תשומת לב', groupedSections.issues, 'red')}
              {renderGroup('▶ בתהליך', groupedSections.inProgress, 'blue')}
              {renderGroup('○ טרם התחיל', groupedSections.notStarted, 'none')}
              {renderGroup('✅ הושלם', groupedSections.completed, 'green')}
            </>
          )}
        </div>

        <div ref={signatureRef} className="mt-6 pb-24 space-y-4">
          {hasLegalSections && (
            <div className="border border-slate-200 rounded-xl bg-white overflow-hidden">
              <button
                onClick={() => setLegalOpen(!legalOpen)}
                className="w-full p-3 flex items-center gap-3 text-right hover:bg-slate-50 transition-colors"
              >
                <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center flex-shrink-0">
                  <Scale className="w-4 h-4 text-indigo-500" />
                </div>
                <span className="flex-1 text-sm font-bold text-slate-700">נסחים משפטיים ({(protocol?.legal_sections || []).length})</span>
                {legalOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
              </button>
              {legalOpen && (
                <div className="px-4 pb-4 pt-1 border-t border-slate-100">
                  <HandoverLegalSections protocol={protocol} projectId={projectId} isSigned={isLocked} userRole={userRole} onUpdated={handleFormUpdated} />
                </div>
              )}
            </div>
          )}

          <div className="border border-slate-200 rounded-xl bg-white overflow-hidden">
            <button
              onClick={() => setSignaturesOpen(!signaturesOpen)}
              className="w-full p-3 flex items-center gap-3 text-right hover:bg-slate-50 transition-colors"
            >
              <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center flex-shrink-0">
                <PenLine className="w-4 h-4 text-indigo-500" />
              </div>
              <span className="flex-1 text-sm font-bold text-slate-700">חתימות פרוטוקול</span>
              {signaturesOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
            </button>
            {signaturesOpen && (
              <div className="px-4 pb-4 pt-1 border-t border-slate-100">
                <SignatureSection protocol={protocol} projectId={projectId} userRole={userRole} onUpdated={handleFormUpdated} />
              </div>
            )}
          </div>
        </div>
      </div>

      {!isLocked && checkedItems > 0 && (
        <div className="fixed bottom-0 inset-x-0 bg-white/0 pb-safe z-40 pointer-events-none">
          <div className="max-w-lg mx-auto px-4 pb-4 pointer-events-auto">
            <button
              onClick={handleSignFAB}
              className="w-full py-3.5 rounded-xl bg-gradient-to-l from-purple-600 to-indigo-600 text-white font-bold text-sm
                shadow-xl shadow-purple-500/30 flex items-center justify-center gap-2 active:scale-[0.97] transition-all"
            >
              <PenLine className="w-4 h-4" />
              חתום על הפרוטוקול
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default HandoverProtocolPage;
