import React, { useState, useEffect } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { useAuth } from '../../contexts/AuthContext';
import { CheckCircle2, PenLine, Lock, Trash2, Loader2, AlertTriangle } from 'lucide-react';
import { Card } from '../ui/card';
import SignaturePadModal from './SignaturePadModal';

const ROLES = [
  { key: 'manager', label: t('handover', 'signatureManager') },
  { key: 'tenant', label: t('handover', 'signatureTenant') },
  { key: 'contractor_rep', label: t('handover', 'signatureContractorRep') },
];

const ALLOWED_ROLES = {
  manager: ['project_manager', 'owner', 'super_admin'],
  tenant: ['project_manager', 'owner', 'contractor', 'super_admin'],
  contractor_rep: ['contractor', 'super_admin'],
};

const SignatureSection = ({ protocol, projectId, userRole, onUpdated }) => {
  const { user } = useAuth();
  const [signingRole, setSigningRole] = useState(null);
  const [signatureImages, setSignatureImages] = useState({});
  const [deletingRole, setDeletingRole] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [editingLabels, setEditingLabels] = useState({});
  const [savingLabel, setSavingLabel] = useState(null);

  const isLocked = protocol?.locked === true;
  const sigLabels = protocol?.signature_labels || {};
  const signatures = (protocol?.signatures && typeof protocol.signatures === 'object' && !Array.isArray(protocol.signatures))
    ? protocol.signatures
    : {};

  const unsignedLegalSections = (protocol?.legal_sections || []).filter(
    s => s.requires_signature && !s.signed_at
  );
  const hasLegalGate = unsignedLegalSections.length > 0;

  useEffect(() => {
    const sigs = (protocol?.signatures && typeof protocol.signatures === 'object' && !Array.isArray(protocol.signatures))
      ? protocol.signatures
      : {};
    const loadImages = async () => {
      const imgs = {};
      for (const role of ROLES) {
        const sig = sigs[role.key];
        if (sig && sig.type === 'canvas' && sig.image_key) {
          try {
            const data = await handoverService.getSignatureImage(projectId, protocol.id, role.key);
            if (data.url) imgs[role.key] = data.url;
          } catch {
          }
        }
      }
      setSignatureImages(imgs);
    };
    if (protocol?.id) loadImages();
  }, [protocol?.id, protocol?.signatures, projectId]);

  const canEditLabel = (roleKey) => {
    if (isLocked) return false;
    if (signatures[roleKey]) return false;
    return ['project_manager', 'owner', 'super_admin'].includes(userRole);
  };

  const handleLabelBlur = async (roleKey) => {
    const newText = (editingLabels[roleKey] ?? '').trim();
    const oldText = (sigLabels[roleKey] ?? '').trim();
    if (newText === oldText) return;
    try {
      setSavingLabel(roleKey);
      const updated = { ...sigLabels, [roleKey]: newText };
      await handoverService.updateProtocol(projectId, protocol.id, { signature_labels: updated });
      onUpdated?.();
    } catch {
      toast.error(t('handover', 'updateError'));
    } finally {
      setSavingLabel(null);
    }
  };

  const canSign = (roleKey) => {
    if (isLocked) return false;
    if (hasLegalGate) return false;
    if (signatures[roleKey]) return false;
    const allowed = ALLOWED_ROLES[roleKey] || [];
    return allowed.includes(userRole);
  };

  const canDelete = (roleKey) => {
    if (isLocked) return false;
    if (!signatures[roleKey]) return false;
    return ['project_manager', 'owner', 'super_admin'].includes(userRole);
  };

  const handleDelete = async (roleKey) => {
    setConfirmDelete(null);
    try {
      setDeletingRole(roleKey);
      await handoverService.deleteSignature(projectId, protocol.id, roleKey);
      toast.success(t('handover', 'signatureDeleted'));
      onUpdated?.();
    } catch (err) {
      if (err?.response?.status === 403) {
        toast.error(t('handover', 'protocolLocked'));
      } else {
        toast.error(t('handover', 'updateError'));
      }
    } finally {
      setDeletingRole(null);
    }
  };

  const currentUserName = user?.name || user?.full_name || '';

  return (
    <div className="space-y-3 p-1">
      {hasLegalGate && !isLocked && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span className="text-sm text-amber-800 font-medium">יש נסחים משפטיים שטרם נחתמו:</span>
          </div>
          <ul className="mr-6 space-y-0.5">
            {unsignedLegalSections.map(s => (
              <li key={s.id} className="text-xs text-amber-700">• {s.title}</li>
            ))}
          </ul>
          <p className="text-[11px] text-amber-600">יש לחתום על כל הנסחים המשפטיים קודם</p>
        </div>
      )}

      {isLocked && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-2.5 flex items-center gap-2">
          <Lock className="w-4 h-4 text-green-600 flex-shrink-0" />
          <span className="text-sm text-green-700 font-medium flex-1">
            {t('handover', 'protocolSignedDate')} {protocol.signed_at ? new Date(protocol.signed_at).toLocaleDateString('he-IL') : ''}
          </span>
        </div>
      )}

      {ROLES.map(({ key, label }) => {
        const sig = signatures[key];
        const isSigned = !!sig;
        const labelText = (key in editingLabels) ? editingLabels[key] : (sigLabels[key] || '');
        const showLabel = labelText || canEditLabel(key);

        return (
          <Card key={key} className={`p-3 border ${isSigned ? 'border-green-200 bg-green-50/30' : 'border-slate-200'}`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-slate-700">{label}</span>
              {isSigned && <CheckCircle2 className="w-4 h-4 text-green-500" />}
            </div>

            {showLabel && (
              canEditLabel(key) ? (
                <div className="mb-2 relative">
                  <textarea
                    value={labelText}
                    onChange={(e) => setEditingLabels(prev => ({ ...prev, [key]: e.target.value }))}
                    onBlur={() => handleLabelBlur(key)}
                    rows={2}
                    placeholder="טקסט הצהרה..."
                    className="w-full text-xs text-slate-600 border border-slate-200 rounded-lg px-2.5 py-2 focus:outline-none focus:ring-2 focus:ring-purple-300 resize-none bg-slate-50"
                    dir="rtl"
                  />
                  {savingLabel === key && <Loader2 className="w-3 h-3 animate-spin text-purple-500 absolute top-2 left-2" />}
                </div>
              ) : labelText ? (
                <p className="text-xs text-slate-500 mb-2 leading-relaxed bg-slate-50 rounded-lg px-2.5 py-2">{labelText}</p>
              ) : null
            )}

            {isSigned ? (
              <div className="space-y-2">
                {sig.type === 'canvas' && signatureImages[key] ? (
                  <div className="bg-white border border-slate-100 rounded-lg p-2">
                    <img src={signatureImages[key]} alt="signature" className="h-12 object-contain mx-auto" />
                  </div>
                ) : sig.type === 'typed' && sig.typed_name ? (
                  <div className="bg-white border border-slate-100 rounded-lg p-3 text-center">
                    <div style={{ fontFamily: "'Caveat', cursive", fontSize: '28px' }} className="text-slate-800">
                      {sig.typed_name}
                    </div>
                    <div className="border-t border-slate-300 mt-1 w-32 mx-auto" />
                  </div>
                ) : null}
                <div className="flex items-center justify-between">
                  <div className="text-xs text-slate-500">
                    <span className="font-medium">{sig.signer_name}</span>
                    {sig.signed_at && (
                      <span className="mr-2">
                        {new Date(sig.signed_at).toLocaleDateString('he-IL')} {new Date(sig.signed_at).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>
                  {canDelete(key) && (
                    confirmDelete === key ? (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleDelete(key)}
                          disabled={deletingRole === key}
                          className="text-[10px] text-red-600 hover:text-red-800 font-medium px-2 py-0.5 bg-red-50 rounded"
                        >
                          {deletingRole === key ? <Loader2 className="w-3 h-3 animate-spin" /> : t('handover', 'deleteSignature')}
                        </button>
                        <button
                          onClick={() => setConfirmDelete(null)}
                          className="text-[10px] text-slate-500 px-2 py-0.5"
                        >
                          ביטול
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmDelete(key)}
                        className="text-slate-400 hover:text-red-500 p-1"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )
                  )}
                </div>
              </div>
            ) : (
              canSign(key) ? (
                <button
                  onClick={() => setSigningRole(key)}
                  className="w-full flex items-center justify-center gap-2 py-2.5 bg-amber-500 text-white rounded-lg
                    text-sm font-bold hover:bg-amber-600 active:scale-[0.98]"
                >
                  <PenLine className="w-4 h-4" />
                  {t('handover', 'sign')}
                </button>
              ) : hasLegalGate && !isLocked && !signatures[key] && (ALLOWED_ROLES[key] || []).includes(userRole) ? (
                <button
                  disabled
                  onClick={() => toast.error('יש לחתום על כל הנסחים המשפטיים קודם')}
                  className="w-full flex items-center justify-center gap-2 py-2.5 bg-slate-300 text-white rounded-lg
                    text-sm font-bold cursor-not-allowed opacity-60"
                  title="יש לחתום על כל הנסחים המשפטיים קודם"
                >
                  <PenLine className="w-4 h-4" />
                  {t('handover', 'sign')}
                </button>
              ) : (
                <div className="text-xs text-slate-400 text-center py-2">
                  {t('handover', 'sectionPlaceholder')}
                </div>
              )
            )}
          </Card>
        );
      })}

      <SignaturePadModal
        open={!!signingRole}
        onClose={() => setSigningRole(null)}
        role={signingRole}
        projectId={projectId}
        protocolId={protocol?.id}
        currentUserName={currentUserName}
        onSigned={onUpdated}
      />
    </div>
  );
};

export default SignatureSection;
