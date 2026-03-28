import React, { useState, useEffect, useCallback, useRef } from 'react';
import { projectService } from '../services/api';
import { tRole } from '../i18n';
import {
  Users, ChevronDown, ChevronUp, Loader2,
  TrendingUp, TrendingDown, Minus, Sparkles,
  Camera, MessageSquare, AlertTriangle, CheckCircle2, ClipboardCheck, Info,
} from 'lucide-react';

const STATUS_CONFIG = {
  active: { label: 'פעיל', color: 'bg-green-500', badge: 'bg-green-100 text-green-700', dot: 'bg-green-500' },
  low: { label: 'נמוך', color: 'bg-orange-500', badge: 'bg-orange-100 text-orange-700', dot: 'bg-orange-400' },
  dormant: { label: 'רדום', color: 'bg-red-500', badge: 'bg-red-100 text-red-700', dot: 'bg-red-400' },
};

const TREND_ICON = {
  growing: { Icon: TrendingUp, color: 'text-green-500' },
  stable: { Icon: Minus, color: 'text-slate-400' },
  declining: { Icon: TrendingDown, color: 'text-red-500' },
  new: { Icon: Sparkles, color: 'text-blue-500' },
};

const ScoreRing = ({ score, size = 64, stroke = 5 }) => {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 60 ? '#22c55e' : score >= 30 ? '#f59e0b' : '#ef4444';

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e2e8f0" strokeWidth={stroke} />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-lg font-black text-slate-800">{score}</span>
      </div>
    </div>
  );
};

const PM_SCORE_LINES = [
  'כניסה לאפליקציה (30 נק׳)',
  'פתיחת ליקויים (20 נק׳)',
  'סגירת ליקויים (15 נק׳)',
  'בדיקות QC (15 נק׳)',
  'העלאת תמונות (10 נק׳)',
  'תגובות ועדכונים (10 נק׳)',
];

const ScoreInfoTooltip = () => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('pointerdown', handler);
    return () => document.removeEventListener('pointerdown', handler);
  }, [open]);

  return (
    <span className="relative inline-flex" ref={ref}>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen(o => !o); }}
        className="p-0.5 rounded-full hover:bg-slate-200/60 transition-colors"
        aria-label="הסבר ציון"
      >
        <Info className="w-3.5 h-3.5 text-slate-400" />
      </button>
      {open && (
        <div className="absolute z-50 top-full mt-1 start-0 w-52 bg-white rounded-lg shadow-lg border border-slate-200 p-3 text-right">
          <p className="text-xs font-bold text-slate-700 mb-1.5">הציון מבוסס על:</p>
          <ul className="space-y-0.5">
            {PM_SCORE_LINES.map((line, i) => (
              <li key={i} className="text-[11px] text-slate-600 flex items-start gap-1">
                <span className="text-slate-400 mt-px">•</span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </span>
  );
};

const Sparkline = ({ data, width = 120, height = 40, currentScore }) => {
  if (!data || data.length < 3) return null;
  const scores = data.map(d => d.team_score);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const range = max - min || 1;
  const padded_min = min - range * 0.1;
  const padded_max = max + range * 0.1;
  const padded_range = padded_max - padded_min || 1;

  const s = currentScore != null ? currentScore : scores[scores.length - 1];
  const color = s >= 60 ? '#22c55e' : s >= 30 ? '#f59e0b' : '#ef4444';

  const points = scores.map((s, i) => {
    const x = (i / (scores.length - 1)) * width;
    const y = height - ((s - padded_min) / padded_range) * height;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="shrink-0">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

const MetricPill = ({ icon: Icon, label, value, color }) => {
  if (!value) return null;
  return (
    <div className="flex items-center gap-1.5 text-xs bg-slate-50 rounded-lg px-2 py-1">
      <Icon className={`w-3 h-3 ${color}`} />
      <span className="text-slate-500">{label}</span>
      <span className="font-bold text-slate-700">{value}</span>
    </div>
  );
};

const MemberRow = ({ member }) => {
  const [expanded, setExpanded] = useState(false);
  const statusCfg = STATUS_CONFIG[member.status] || STATUS_CONFIG.dormant;
  const trendCfg = TREND_ICON[member.trend] || TREND_ICON.stable;
  const TrendIcon = trendCfg.Icon;
  const m = member.metrics || {};

  return (
    <div className="border-b border-slate-100 last:border-b-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 p-2.5 hover:bg-slate-50/50 transition-colors"
      >
        <div className={`w-2 h-2 rounded-full shrink-0 ${statusCfg.dot}`} />
        <div className="flex-1 min-w-0 text-right">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium text-slate-800 truncate">{member.name || 'ללא שם'}</span>
            {member.company_name && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 shrink-0">{member.company_name}</span>
            )}
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-[10px] text-slate-400">{tRole(member.role)}</span>
            {member.last_login_relative && (
              <span className="text-[10px] text-slate-400">· {member.last_login_relative}</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <TrendIcon className={`w-3 h-3 ${trendCfg.color}`} />
          <span className="text-sm font-bold text-slate-700 w-7 text-center">{member.activity_score}</span>
          {expanded ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
        </div>
      </button>
      {expanded && (
        <div className="px-3 pb-3 pt-0.5">
          <div className="flex flex-wrap gap-1.5">
            <MetricPill icon={AlertTriangle} label="נפתחו" value={m.defects_opened} color="text-red-500" />
            <MetricPill icon={CheckCircle2} label="נסגרו" value={m.defects_closed} color="text-green-500" />
            <MetricPill icon={ClipboardCheck} label="QC" value={m.qc_items_checked} color="text-indigo-500" />
            <MetricPill icon={Camera} label="תמונות" value={m.photos_uploaded} color="text-blue-500" />
            <MetricPill icon={MessageSquare} label="תגובות" value={m.comments} color="text-purple-500" />
          </div>
        </div>
      )}
    </div>
  );
};

export default function TeamActivitySection({ projectId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [period, setPeriod] = useState(7);
  const [trendData, setTrendData] = useState(null);

  const load = useCallback(async (p) => {
    setLoading(true);
    setError(false);
    try {
      const result = await projectService.getTeamActivity(projectId, p);
      setData(result);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(period); }, [load, period]);

  useEffect(() => {
    projectService.getActivityTrend(projectId, 30)
      .then(r => setTrendData(r.trend))
      .catch(() => {});
  }, [projectId]);

  if (error) return null;

  if (loading && !data) {
    return (
      <div className="bg-white rounded-xl border shadow-sm p-4">
        <div className="flex items-center gap-2 mb-3">
          <Users className="w-4 h-4 text-violet-500" />
          <h3 className="text-sm font-bold text-slate-700">פעילות צוות</h3>
        </div>
        <div className="flex justify-center py-6">
          <Loader2 className="w-5 h-5 animate-spin text-violet-400" />
        </div>
      </div>
    );
  }

  if (!data) return null;
  const { summary, members } = data;
  if (!summary || summary.total_members === 0) return null;

  return (
    <div className="bg-white rounded-xl border shadow-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-violet-500" />
          <h3 className="text-sm font-bold text-slate-700">פעילות צוות</h3>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500">{summary.total_members}</span>
        </div>
        <div className="flex items-center bg-slate-100 rounded-lg p-0.5">
          {[7, 30].map(p => (
            <button
              key={p}
              onClick={() => { if (p !== period) { setPeriod(p); } }}
              className={`text-[11px] px-2.5 py-1 rounded-md font-medium transition-all ${
                period === p ? 'bg-white text-slate-700 shadow-sm' : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              {p} ימים
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-4 mb-4 p-3 bg-gradient-to-l from-violet-50 to-slate-50 rounded-xl">
        <ScoreRing score={summary.team_score} />
        <Sparkline data={trendData} currentScore={summary.team_score} />
        <div className="flex-1">
          <p className="text-xs text-slate-500 mb-2 flex items-center gap-1">ציון פעילות צוות <ScoreInfoTooltip /></p>
          <div className="flex flex-wrap gap-1.5">
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
              {summary.active} פעילים
            </span>
            {summary.low > 0 && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 font-medium">
                {summary.low} נמוך
              </span>
            )}
            {summary.dormant > 0 && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">
                {summary.dormant} רדום
              </span>
            )}
          </div>
        </div>
      </div>

      {summary.team_score < 30 && summary.active === 0 && (
        <div className="flex items-center gap-2 p-2.5 bg-blue-50 border border-blue-200 rounded-lg mb-4">
          <Info className="w-4 h-4 text-blue-400 shrink-0" />
          <span className="text-[11px] text-blue-700">הציונים ישתפרו ככל שחברי הצוות ישתמשו באפליקציה</span>
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-2 mb-2">
          <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
        </div>
      )}

      <div className="border border-slate-100 rounded-xl overflow-hidden">
        {(() => {
          const nonContractors = (members || []).filter(m => m.role !== 'contractor');
          const contractors = (members || []).filter(m => m.role === 'contractor');
          const companyGroups = {};
          const ungrouped = [];
          contractors.forEach(m => {
            const company = m.company_name || '';
            if (company) {
              if (!companyGroups[company]) companyGroups[company] = [];
              companyGroups[company].push(m);
            } else {
              ungrouped.push(m);
            }
          });
          const sortedCompanyEntries = Object.entries(companyGroups)
            .map(([company, group]) => {
              group.sort((a, b) => b.activity_score - a.activity_score);
              return [company, group];
            })
            .sort((a, b) => b[1][0].activity_score - a[1][0].activity_score);
          return (
            <>
              {nonContractors.map(m => <MemberRow key={m.user_id} member={m} />)}
              {sortedCompanyEntries.map(([company, group]) => (
                <div key={company}>
                  <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-100">
                    <span className="text-[11px] font-semibold text-slate-500">{company}</span>
                  </div>
                  {group.map(m => <MemberRow key={m.user_id} member={m} />)}
                </div>
              ))}
              {ungrouped.map(m => <MemberRow key={m.user_id} member={m} />)}
            </>
          );
        })()}
      </div>
    </div>
  );
}
