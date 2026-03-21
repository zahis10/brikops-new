import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import { CheckCircle2, PenLine, AlertTriangle, Loader2, Clock } from 'lucide-react';
import SignaturePadModal from './SignaturePadModal';

const ROLE_LABELS = {
  manager: 'מנהל פרויקט / מפקח',
  tenant: 'רוכש/ת ראשי/ת',
  tenant_2: 'רוכש/ת נוסף/ת',
  contractor_rep: 'נציג קבלן',
};

const ALLOWED_ROLES = {
  manager: ['project_manager', 'owner', 'super_admin', 'management_team'],
  tenant: ['project_manager', 'owner', 'contractor', 'super_admin', 'management_team'],
  tenant_2: ['project_manager', 'owner', 'contractor', 'super_admin', 'management_team'],
  contractor_rep: ['contractor', 'super_admin'],
};

const HandoverLegalSections = ({ protocol, projectId, isSigned, userRole, onUpdated }) => {
  const { user } = useAuth();
  const [signingSection, setSigningSection] = useState(null);
  const [signingSlot, setSigningSlot] = useState(null);
  const [signatureImages, setSignatureImages] = useState({});
  const [editingBodies, setEditingBodies] = useState({});
  const [savingBody, setSavingBody] = useState(null);
  const blurSaveRef = useRef({});
  const sectionRefsMap = useRef({});

  const sections = useMemo(() => protocol?.legal_sections || [], [protocol?.legal_sections]);
  const isLocked = protocol?.locked === true;
  const isPM = ['project_manager', 'owner', 'super_admin'].includes(userRole);
  const validTenants = (protocol?.tenants || []).filter(tt => tt && tt.name && tt.name.trim() !== '');
  const numTenants = validTenants.length;

  useEffect(() => {
    const loadImages = async () => {
      const imgs = {};
      for (const s of sections) {
        const sigs = s.signatures || {};
        for (const slot of ['tenant', 'tenant_2']) {
          const slotSig = sigs[slot];
          if (slotSig && slotSig.type === 'canvas' && slotSig.image_key) {
            try {
              const data = await handoverService.getLegalSectionSignatureImage(projectId, protocol.id, s.id, slot);
              if (data.url) imgs[`${s.id}_${slot}`] = data.url;
            } catch {}
          }
        }
        if (s.signature && s.signature.type === 'canvas' && s.signature.image_key) {
          try {
            const data = await handoverService.getLegalSectionSignatureImage(projectId, protocol.id, s.id);
            if (data.url) imgs[s.id] = data.url;
          } catch {}
        }
      }
      setSignatureImages(imgs);
    };
    if (protocol?.id && sections.length > 0) loadImages();
  }, [protocol?.id, sections, projectId]);

  useEffect(() => {
    const bodies = {};
    for (const s of sections) {
      bodies[s.id] = s.body || '';
    }
    setEditingBodies(bodies);
  }, [protocol?.id, sections]);

  const handleBodyChange = useCallback((sectionId, value) => {
    setEditingBodies(prev => ({ ...prev, [sectionId]: value }));
  }, []);

  const handleBodyBlur = useCallback(async (section) => {
    if (section.signed_at || isLocked) return;
    const newBody = (editingBodies[section.id] || '').trim();
    if (!newBody || newBody === (section.body || '').trim()) return;

    if (blurSaveRef.current[section.id]) return;
    blurSaveRef.current[section.id] = true;
    setSavingBody(section.id);
    try {
      await handoverService.updateLegalSectionBody(projectId, protocol.id, section.id, newBody);
      toast.success('נשמר');
      onUpdated?.();
    } catch (err) {
      console.error(err);
      toast.error(err?.response?.data?.detail || 'שגיאה בשמירת הנסח');
    } finally {
      setSavingBody(null);
      blurSaveRef.current[section.id] = false;
    }
  }, [editingBodies, isLocked, projectId, protocol?.id, onUpdated]);

  const canSignSlot = (section, slot) => {
    if (isLocked) return false;
    if (!section.requires_signature) return false;
    const allowed = ALLOWED_ROLES[slot] || [];
    if (!allowed.includes(userRole)) return false;
    const sigs = section.signatures || {};
    if (sigs[slot]?.signed_at) return false;
    return true;
  };

  const canSignSection = (section) => {
    if (isLocked) return false;
    if (!section.requires_signature) return false;
    if (section.signed_at) return false;
    const role = section.signature_role;
    if (!role) return false;
    const allowed = ALLOWED_ROLES[role] || [];
    return allowed.includes(userRole);
  };

  const handleSignLegalSection = useCallback(async (sectionId, formData, slot) => {
    try {
      if (slot) {
        formData.append('signer_slot', slot);
      }
      const responseData = await handoverService.signLegalSection(projectId, protocol.id, sectionId, formData);
      const currentSectionId = sectionId;
      setSigningSection(null);
      setSigningSlot(null);

      const updatedSections = (responseData && responseData.legal_sections) || sections;
      const updatedSection = updatedSections.find(s => s.id === currentSectionId);

      setTimeout(() => {
        if (updatedSection) {
          const sigs = updatedSection.signatures || {};
          if (updatedSection.requires_both_tenants && numTenants >= 2) {
            if (!sigs.tenant_2?.signed_at && sigs.tenant?.signed_at) {
              const nextSec = updatedSections.find(s => s.id === currentSectionId);
              if (nextSec) {
                setSigningSection(nextSec);
                setSigningSlot('tenant_2');
              }
              return;
            }
          }
        }

        let foundNext = false;
        const currentIdx = updatedSections.findIndex(s => s.id === currentSectionId);
        for (let i = currentIdx + 1; i < updatedSections.length; i++) {
          const s = updatedSections[i];
          if (!s.requires_signature) continue;
          const isDual = s.requires_both_tenants;
          let sectionDone;
          if (isDual) {
            const ss = s.signatures || {};
            const t1 = !!ss.tenant?.signed_at;
            const t2 = numTenants >= 2 ? !!ss.tenant_2?.signed_at : true;
            sectionDone = t1 && t2;
          } else {
            sectionDone = !!s.signed_at;
          }
          if (!sectionDone) {
            const el = sectionRefsMap.current[s.id];
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            let nextSlot = null;
            if (isDual) {
              const ss = s.signatures || {};
              if (!ss.tenant?.signed_at) nextSlot = 'tenant';
              else if (numTenants >= 2 && !ss.tenant_2?.signed_at) nextSlot = 'tenant_2';
            }
            setSigningSection(s);
            setSigningSlot(nextSlot);
            foundNext = true;
            break;
          }
        }

        if (!foundNext) {
          const allDone = updatedSections
            .filter(s => s.requires_signature)
            .every(s => {
              if (s.requires_both_tenants) {
                const ss = s.signatures || {};
                const t1 = !!ss.tenant?.signed_at;
                const t2 = numTenants >= 2 ? !!ss.tenant_2?.signed_at : true;
                return t1 && t2;
              }
              return !!s.signed_at;
            });
          if (allDone) {
            toast.success('כל הנסחים נחתמו!');
          }
        }
      }, 300);

      return responseData;
    } catch (err) {
      if (err?.response?.status === 409) {
        toast.info('הסעיף כבר נחתם, מרענן...');
        setSigningSection(null);
        setSigningSlot(null);
        onUpdated?.();
        return;
      }
      throw err;
    }
  }, [projectId, protocol?.id, onUpdated, sections, numTenants]);

  const openSignPad = (section, slot) => {
    setSigningSection(section);
    setSigningSlot(slot);
  };

  const currentUserName = user?.name || user?.full_name || '';

  if (sections.length === 0) return null;

  const renderSignatureBlock = (sig, imageKey, signerName, signedAt) => (
    <div className="space-y-2">
      {sig?.type === 'canvas' && signatureImages[imageKey] ? (
        <div className="bg-white border border-slate-100 rounded-lg p-2">
          <img src={signatureImages[imageKey]} alt="signature" className="h-12 object-contain mx-auto" />
        </div>
      ) : sig?.type === 'typed' && sig?.typed_name ? (
        <div className="bg-white border border-slate-100 rounded-lg p-3 text-center">
          <div style={{ fontFamily: "'Caveat', cursive", fontSize: '24px' }} className="text-slate-800">
            {sig.typed_name}
          </div>
          <div className="border-t border-slate-300 mt-1 w-24 mx-auto" />
        </div>
      ) : null}
      <div className="text-xs text-slate-500">
        <span className="font-medium">{signerName}</span>
        {signedAt && (
          <span className="mr-2">
            {new Date(signedAt).toLocaleDateString('he-IL')}{' '}
            {new Date(signedAt).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>
    </div>
  );

  const renderDualSignatureArea = (section) => {
    const sigs = section.signatures || {};
    const showSecondPad = section.requires_both_tenants && numTenants >= 2;
    const t1Sig = sigs.tenant;
    const t2Sig = sigs.tenant_2;
    const t1Signed = !!t1Sig?.signed_at;
    const t2Signed = showSecondPad ? !!t2Sig?.signed_at : true;
    const allDone = t1Signed && t2Signed;

    return (
      <div className={`border rounded-lg p-2.5 mt-1 ${allDone ? 'border-green-200 bg-green-50/30' : t1Signed || t2Sig?.signed_at ? 'border-amber-200 bg-amber-50/20' : 'border-slate-200'}`}>
        <div className="space-y-3">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-slate-600">חתימת רוכש/ת ראשי/ת</span>
              {t1Signed && <CheckCircle2 className="w-4 h-4 text-green-500" />}
            </div>
            {t1Signed ? (
              renderSignatureBlock(t1Sig, `${section.id}_tenant`, t1Sig.signer_name, t1Sig.signed_at)
            ) : canSignSlot(section, 'tenant') ? (
              <button
                onClick={() => openSignPad(section, 'tenant')}
                className="w-full flex items-center justify-center gap-2 py-2 bg-amber-500 text-white rounded-lg text-sm font-bold hover:bg-amber-600 active:scale-[0.98]"
              >
                <PenLine className="w-3.5 h-3.5" />
                חתום
              </button>
            ) : (
              <div className="text-xs text-slate-400 text-center py-1.5">ממתין לחתימה</div>
            )}
          </div>

          {showSecondPad && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-slate-600">חתימת רוכש/ת נוסף/ת</span>
                {t2Signed ? (
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                ) : t1Signed ? (
                  <Clock className="w-4 h-4 text-amber-500" />
                ) : null}
              </div>
              {t2Signed ? (
                renderSignatureBlock(t2Sig, `${section.id}_tenant_2`, t2Sig.signer_name, t2Sig.signed_at)
              ) : canSignSlot(section, 'tenant_2') ? (
                <button
                  onClick={() => openSignPad(section, 'tenant_2')}
                  className="w-full flex items-center justify-center gap-2 py-2 bg-amber-500 text-white rounded-lg text-sm font-bold hover:bg-amber-600 active:scale-[0.98]"
                >
                  <PenLine className="w-3.5 h-3.5" />
                  חתום
                </button>
              ) : (
                <div className="text-xs text-amber-500 text-center py-1.5">ממתין לחתימת רוכש/ת נוסף/ת</div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderSingleSignatureArea = (section) => {
    const isSectionSigned = !!section.signed_at;

    return (
      <div className={`border rounded-lg p-2.5 mt-1 ${isSectionSigned ? 'border-green-200 bg-green-50/30' : 'border-slate-200'}`}>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-semibold text-slate-600">
            חתימת {ROLE_LABELS[section.signature_role] || section.signature_role}
          </span>
          {isSectionSigned && <CheckCircle2 className="w-4 h-4 text-green-500" />}
        </div>

        {isSectionSigned ? (
          renderSignatureBlock(section.signature, section.id, section.signer_name, section.signed_at)
        ) : canSignSection(section) ? (
          <button
            onClick={() => openSignPad(section, null)}
            className="w-full flex items-center justify-center gap-2 py-2 bg-amber-500 text-white rounded-lg text-sm font-bold hover:bg-amber-600 active:scale-[0.98]"
          >
            <PenLine className="w-3.5 h-3.5" />
            חתום
          </button>
        ) : (
          <div className="text-xs text-slate-400 text-center py-1.5">
            ממתין לחתימה
          </div>
        )}
      </div>
    );
  };

  const getSigningRole = () => {
    if (!signingSection) return null;
    if (signingSlot) return signingSlot;
    return signingSection.signature_role;
  };

  const getSigningTenantData = () => {
    const role = getSigningRole();
    if (role === 'tenant') return (protocol?.tenants || [])[0];
    if (role === 'tenant_2') return (protocol?.tenants || [])[1];
    return null;
  };

  return (
    <div className="space-y-3 p-1">
      {sections.map((section) => {
        const isDual = section.requires_both_tenants;
        const needsSignature = section.requires_signature;
        const sectionFullySigned = isDual
          ? (() => {
              const sigs = section.signatures || {};
              const t1 = !!sigs.tenant?.signed_at;
              const t2 = numTenants >= 2 ? !!sigs.tenant_2?.signed_at : true;
              return t1 && t2;
            })()
          : !!section.signed_at;
        const hasAnySig = isDual
          ? (() => {
              const sigs = section.signatures || {};
              return !!sigs.tenant?.signed_at || !!sigs.tenant_2?.signed_at;
            })()
          : !!section.signed_at;
        const canEdit = isPM && !hasAnySig && !isLocked;

        return (
          <div
            key={section.id}
            ref={el => { sectionRefsMap.current[section.id] = el; }}
            className={`border rounded-xl bg-white overflow-hidden ${
              sectionFullySigned ? 'border-r-[3px] border-r-green-400 border-green-200' :
              needsSignature ? 'border-r-[3px] border-r-amber-400 border-slate-200' :
              'border-slate-200'
            }`}
          >
            <div className="p-3 space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-slate-800">{section.title}</h4>
                {section.edited && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-medium flex items-center gap-1">
                    <PenLine className="w-2.5 h-2.5" />
                    נערך מהמקור
                  </span>
                )}
              </div>

              {canEdit ? (
                <div className="relative">
                  <textarea
                    value={editingBodies[section.id] ?? section.body}
                    onChange={(e) => handleBodyChange(section.id, e.target.value)}
                    onBlur={() => handleBodyBlur(section)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none
                      focus:outline-none focus:ring-2 focus:ring-purple-300 leading-relaxed min-h-[100px]"
                    dir="rtl"
                  />
                  {savingBody === section.id && (
                    <div className="absolute top-2 left-2">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-500" />
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap" dir="rtl">
                  {section.body}
                </p>
              )}

              {!needsSignature && (
                <div className="flex items-center gap-1.5 text-green-600 text-xs">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>אין צורך בחתימה</span>
                </div>
              )}

              {needsSignature && isDual && renderDualSignatureArea(section)}
              {needsSignature && !isDual && renderSingleSignatureArea(section)}
            </div>
          </div>
        );
      })}

      <SignaturePadModal
        open={!!signingSection}
        onClose={() => { setSigningSection(null); setSigningSlot(null); }}
        role={getSigningRole()}
        projectId={projectId}
        protocolId={protocol?.id}
        currentUserName={currentUserName}
        tenantData={getSigningTenantData()}
        onSigned={onUpdated}
        signFn={signingSection ? (formData) => handleSignLegalSection(signingSection.id, formData, signingSlot) : undefined}
      />
    </div>
  );
};

export default HandoverLegalSections;
