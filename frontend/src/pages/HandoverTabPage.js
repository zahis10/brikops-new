import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { handoverService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { t } from '../i18n';
import {
  ArrowRight, Loader2, Plus, CheckCircle2, Clock, FileCheck,
  AlertTriangle, Home, ShieldCheck
} from 'lucide-react';
import { Card } from '../components/ui/card';

const STATUS_LABELS = {
  draft: { label: t('handover', 'draft'), color: 'bg-slate-100 text-slate-600' },
  in_progress: { label: t('handover', 'inProgress'), color: 'bg-blue-100 text-blue-700' },
  signed: { label: t('handover', 'signed'), color: 'bg-green-100 text-green-700' },
};

const ProgressRing = ({ checked, total, size = 40, strokeWidth = 3 }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = total > 0 ? checked / total : 0;
  const offset = circumference * (1 - pct);

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="rotate-[-90deg]">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke="#e2e8f0" strokeWidth={strokeWidth} />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={pct >= 1 ? '#22c55e' : '#3b82f6'} strokeWidth={strokeWidth}
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round" />
      </svg>
      <span className="absolute text-[10px] font-bold text-slate-600">
        {total > 0 ? Math.round(pct * 100) : 0}%
      </span>
    </div>
  );
};

const computeProgress = (protocol) => {
  if (!protocol?.sections) return { checked: 0, total: 0 };
  let checked = 0, total = 0;
  for (const section of protocol.sections) {
    if (!section.items) continue;
    for (const item of section.items) {
      total++;
      if (item.status && item.status !== 'not_checked') checked++;
    }
  }
  return { checked, total };
};

const HandoverTabPage = () => {
  const { projectId, unitId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [protocols, setProtocols] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const loadProtocols = useCallback(async () => {
    try {
      setLoading(true);
      const data = await handoverService.listProtocols(projectId, { unit_id: unitId });
      setProtocols(data);
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'loadError'));
    } finally {
      setLoading(false);
    }
  }, [projectId, unitId]);

  useEffect(() => { loadProtocols(); }, [loadProtocols]);

  const initial = protocols.find(p => p.type === 'initial');
  const final = protocols.find(p => p.type === 'final');

  const initialSigned = initial?.status === 'signed';
  const finalSigned = final?.status === 'signed';

  let state;
  if (!initial && !final) state = 'A';
  else if (initial && !initialSigned && !final) state = 'B';
  else if (initialSigned && !final) state = 'C';
  else if (initial && final && !finalSigned) state = 'D';
  else if (initialSigned && finalSigned) state = 'E';
  else state = 'B';

  const handleCreate = async (protocolType) => {
    if (creating) return;
    try {
      setCreating(true);
      const result = await handoverService.createProtocol(projectId, {
        unit_id: unitId,
        type: protocolType,
      });
      toast.success(t('handover', 'protocolCreated'));
      navigate(`/projects/${projectId}/units/${unitId}/handover/${result.id}`);
    } catch (err) {
      if (err?.response?.status === 409) {
        toast.error(t('handover', 'duplicateProtocol'));
        try {
          const refreshedData = await handoverService.listProtocols(projectId, { unit_id: unitId });
          setProtocols(refreshedData);
          const existing = refreshedData.find(p => p.type === protocolType);
          if (existing) {
            navigate(`/projects/${projectId}/units/${unitId}/handover/${existing.id}`);
          }
        } catch (_) { /* best effort */ }
      } else {
        toast.error(t('handover', 'createError'));
        console.error(err);
      }
    } finally {
      setCreating(false);
    }
  };

  const renderProtocolCard = (protocol, typeLabel, typeIcon) => {
    if (!protocol) return null;

    const isSigned = protocol.status === 'signed';
    const statusInfo = STATUS_LABELS[protocol.status] || STATUS_LABELS.draft;

    return (
      <Card
        className={`p-4 cursor-pointer transition-all active:scale-[0.98] border ${
          isSigned ? 'border-green-200 bg-green-50/50' : 'border-slate-200 hover:border-blue-300'
        }`}
        onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover/${protocol.id}`)}
      >
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
            isSigned ? 'bg-green-100' : 'bg-blue-50'
          }`}>
            {isSigned ? (
              <ShieldCheck className="w-5 h-5 text-green-600" />
            ) : (
              typeIcon
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-800">{typeLabel}</h3>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${statusInfo.color}`}>
                {statusInfo.label}
              </span>
              {isSigned && (
                <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-green-100 text-green-700">
                  {t('handover', 'readOnly')}
                </span>
              )}
            </div>
            {isSigned && protocol.signed_at && (
              <p className="text-xs text-green-600 mt-0.5">
                {t('handover', 'signedOn')} {new Date(protocol.signed_at).toLocaleDateString('he-IL')}
              </p>
            )}
            {!isSigned && (
              <p className="text-xs text-slate-500 mt-0.5">
                {t('handover', 'inProgress')}
              </p>
            )}
          </div>
          <ArrowRight className="w-4 h-4 text-slate-300 rotate-180 flex-shrink-0" />
        </div>
      </Card>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="bg-gradient-to-l from-purple-600 to-purple-700 text-white">
        <div className="max-w-lg mx-auto px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/projects/${projectId}/units/${unitId}`)}
              className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-bold">{t('handover', 'tabTitle')}</h1>
              <p className="text-purple-200 text-xs">{t('handover', 'tabDesc')}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 mt-4 space-y-4">
        {state === 'A' && (
          <div className="text-center py-12 space-y-4">
            <div className="w-16 h-16 bg-purple-100 rounded-2xl flex items-center justify-center mx-auto">
              <Home className="w-8 h-8 text-purple-500" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-800">{t('handover', 'stateEmpty')}</h2>
              <p className="text-sm text-slate-500 mt-1">{t('handover', 'tabDesc')}</p>
            </div>
            <button
              onClick={() => handleCreate('initial')}
              disabled={creating}
              className="inline-flex items-center gap-2 bg-purple-600 text-white px-6 py-3 rounded-xl font-medium
                hover:bg-purple-700 active:scale-[0.98] transition-all disabled:opacity-50"
            >
              {creating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              {t('handover', 'startInitial')}
            </button>
          </div>
        )}

        {state === 'B' && (
          <>
            {renderProtocolCard(
              initial,
              t('handover', 'initialProtocol'),
              <FileCheck className="w-5 h-5 text-blue-500" />
            )}
          </>
        )}

        {state === 'C' && (
          <>
            {renderProtocolCard(
              initial,
              t('handover', 'initialProtocol'),
              <FileCheck className="w-5 h-5 text-green-600" />
            )}

            <div className="pt-2">
              <button
                onClick={() => handleCreate('final')}
                disabled={creating}
                className="w-full flex items-center justify-center gap-2 bg-purple-600 text-white px-6 py-3
                  rounded-xl font-medium hover:bg-purple-700 active:scale-[0.98] transition-all disabled:opacity-50"
              >
                {creating ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
                {t('handover', 'startFinal')}
              </button>
            </div>
          </>
        )}

        {state === 'D' && (
          <>
            {renderProtocolCard(
              initial,
              t('handover', 'initialProtocol'),
              <FileCheck className="w-5 h-5 text-green-600" />
            )}

            <Card className="p-3 border border-amber-200 bg-amber-50">
              <div className="flex items-center gap-2 text-amber-700 text-sm">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{t('handover', 'openDefects')}</span>
              </div>
            </Card>

            {renderProtocolCard(
              final,
              t('handover', 'finalProtocol'),
              <Clock className="w-5 h-5 text-blue-500" />
            )}
          </>
        )}

        {state === 'E' && (
          <>
            <div className="text-center py-4">
              <div className="w-14 h-14 bg-green-100 rounded-2xl flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-7 h-7 text-green-600" />
              </div>
              <h2 className="text-lg font-bold text-green-700 mt-3">{t('handover', 'unitDelivered')}</h2>
              {final?.signed_at && (
                <p className="text-sm text-green-600 mt-1">
                  {new Date(final.signed_at).toLocaleDateString('he-IL')}
                </p>
              )}
            </div>

            {renderProtocolCard(
              initial,
              t('handover', 'initialProtocol'),
              <FileCheck className="w-5 h-5 text-green-600" />
            )}

            {renderProtocolCard(
              final,
              t('handover', 'finalProtocol'),
              <FileCheck className="w-5 h-5 text-green-600" />
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default HandoverTabPage;
