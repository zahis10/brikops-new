import React, { useState, useEffect, useCallback, useRef } from 'react';
import { qcService, projectService } from '../services/api';
import { toast } from 'sonner';
import {
  Loader2, Plus, Trash2, ShieldCheck, X, Users, Check, Info, AlertTriangle, Search
} from 'lucide-react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { getRoleLabel, CONTRACTOR_ROLE } from '../utils/roleLabels';
import * as DialogPrimitive from '@radix-ui/react-dialog';

const QCApproversTab = ({ projectId, canManageApprovers = false }) => {
  const [approvers, setApprovers] = useState([]);
  const [stages, setStages] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [removingId, setRemovingId] = useState(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [approversData, stagesData, membersData] = await Promise.all([
        qcService.getApprovers(projectId),
        qcService.getStagesMeta(),
        projectService.getMemberships(projectId).then(d =>
          Array.isArray(d) ? d : (d?.items || d?.members || [])
        ),
      ]);
      setApprovers(approversData);
      setStages(stagesData);
      setMembers(membersData);
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error('אין הרשאה לצפות במאשרים');
      } else {
        toast.error('שגיאה בטעינת מאשרים');
      }
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRemove = async (approver) => {
    if (!window.confirm(`להסיר את ${approver.user_name || approver.user_email} מרשימת המאשרים?`)) return;
    setRemovingId(approver.id);
    try {
      await qcService.removeApprover(projectId, approver.user_id);
      toast.success('מאשר הוסר בהצלחה');
      loadData();
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error('אין הרשאה להסיר מאשרים — רק מנהל הפרויקט יכול לבצע פעולה זו');
      } else {
        toast.error('שגיאה בהסרת מאשר: ' + (err.response?.data?.detail || err.message));
      }
    } finally {
      setRemovingId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
      </div>
    );
  }

  const approverUserIds = new Set(approvers.map(a => a.user_id));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-amber-600" />
            <h3 className="font-bold text-slate-800 text-base">מאשרי בקרת ביצוע</h3>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {canManageApprovers ? 'ניהול מי יכול לאשר / לדחות שלבי בקרת ביצוע' : 'צפייה במאשרי בקרת ביצוע בפרויקט'}
          </p>
        </div>
        {canManageApprovers && approvers.length > 0 && (
          <Button
            onClick={() => setShowAdd(true)}
            size="sm"
            className="bg-amber-500 hover:bg-amber-600 text-white text-xs flex-shrink-0 min-h-[44px] px-4"
          >
            <Plus className="w-3.5 h-3.5 ml-1" />
            הוסף מאשר
          </Button>
        )}
      </div>

      {!canManageApprovers && (
        <div className="flex items-center gap-2 px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600">
          <Info className="w-4 h-4 text-slate-400 flex-shrink-0" />
          <span>צפייה בלבד — רק מנהל הפרויקט יכול להוסיף או להסיר מאשרים</span>
        </div>
      )}

      {approvers.length === 0 ? (
        <Card className="p-6 text-center">
          <ShieldCheck className="w-10 h-10 text-amber-300 mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-700">ברירת מחדל: מנהל הפרויקט הוא המאשר היחיד</p>
          <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
            {canManageApprovers
              ? 'ניתן להוסיף מאשרים נוספים לפי שלבים ספציפיים או לכל השלבים.'
              : 'לא הוגדרו מאשרים נוספים בפרויקט זה.'}
          </p>
          {canManageApprovers && (
            <Button
              onClick={() => setShowAdd(true)}
              size="sm"
              className="bg-amber-500 hover:bg-amber-600 text-white text-xs mt-4 min-h-[44px] px-5"
            >
              <Plus className="w-3.5 h-3.5 ml-1" />
              הוסף מאשר
            </Button>
          )}
        </Card>
      ) : (
        <div className="space-y-2.5">
          {approvers.map(approver => {
            const isRemoving = removingId === approver.id;
            return (
              <Card key={approver.id} className={`p-3.5 ${approver.invalid_role ? 'border-red-200 bg-red-50/20' : ''}`}>
                <div className="flex items-start gap-3">
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0 mt-0.5 ${approver.invalid_role ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>
                    {(approver.user_name || approver.user_email || '?')[0]}
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-[15px] font-semibold text-slate-800 truncate leading-snug">
                      {approver.user_name || approver.user_email}
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5 truncate">
                      {getRoleLabel(approver.user_role)}
                      {approver.user_email && approver.user_name ? ` · ${approver.user_email}` : ''}
                    </p>

                    {approver.invalid_role ? (
                      <div className="mt-2 flex items-start gap-1.5 text-xs text-red-600/80 bg-red-50 border border-red-100 rounded-lg px-2.5 py-2">
                        <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                        <span className="leading-relaxed">הרשאה לא פעילה — קבלנים אינם יכולים לאשר שלבי בקרת ביצוע. רשומה ישנה שלא תחשב כמאשר.</span>
                      </div>
                    ) : (
                      <div className="mt-2">
                        {approver.mode === 'all' ? (
                          <span className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                            <Check className="w-3 h-3" />
                            מאשר כל השלבים
                          </span>
                        ) : (
                          <div>
                            <span className="text-[11px] text-slate-400 mb-1 block">שלבים נבחרים:</span>
                            <div className="flex flex-wrap gap-1">
                              {(approver.stages_display || []).map(s => (
                                <span key={s.code} className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                                  {s.label_he}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {canManageApprovers && (
                    <button
                      onClick={() => handleRemove(approver)}
                      disabled={isRemoving}
                      className={`p-2.5 rounded-xl transition-all flex-shrink-0 min-w-[44px] min-h-[44px] flex items-center justify-center ${isRemoving ? 'bg-red-50 text-red-300 cursor-wait' : 'hover:bg-red-50 active:bg-red-100 text-slate-400 hover:text-red-500'}`}
                      title="הסר מאשר"
                    >
                      {isRemoving ? <Loader2 className="w-4.5 h-4.5 animate-spin" /> : <Trash2 className="w-4.5 h-4.5" />}
                    </button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {canManageApprovers && showAdd && (
        <AddApproverModal
          projectId={projectId}
          stages={stages}
          members={members.filter(m => !approverUserIds.has(m.user_id) && m.role !== CONTRACTOR_ROLE)}
          onClose={() => setShowAdd(false)}
          onSuccess={() => { setShowAdd(false); loadData(); }}
        />
      )}
    </div>
  );
};


const AddApproverModal = ({ projectId, stages, members, onClose, onSuccess }) => {
  const [selectedUserId, setSelectedUserId] = useState('');
  const [mode, setMode] = useState('all');
  const [selectedStages, setSelectedStages] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchRef = useRef(null);

  const handleSubmit = async () => {
    if (!selectedUserId) {
      toast.error('יש לבחור משתמש');
      return;
    }
    if (mode === 'stages' && selectedStages.length === 0) {
      toast.error('יש לבחור לפחות שלב אחד');
      return;
    }

    setSubmitting(true);
    try {
      await qcService.addApprover(projectId, {
        user_id: selectedUserId,
        mode,
        stages: mode === 'stages' ? selectedStages : undefined,
      });
      toast.success('מאשר נוסף בהצלחה');
      onSuccess();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בהוספת מאשר');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleStage = (code) => {
    setSelectedStages(prev =>
      prev.includes(code) ? prev.filter(s => s !== code) : [...prev, code]
    );
  };

  const selectedUser = members.find(m => m.user_id === selectedUserId);

  const filteredMembers = members.filter(m => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.trim().toLowerCase();
    return (m.user_name || '').toLowerCase().includes(q)
      || (m.user_email || '').toLowerCase().includes(q);
  });

  return (
    <DialogPrimitive.Root open={true} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 bg-black/40 z-50" />
        <DialogPrimitive.Content
          className="fixed inset-x-0 bottom-0 sm:bottom-auto sm:left-[50%] sm:top-[50%] sm:-translate-x-1/2 sm:-translate-y-1/2 z-50 bg-white rounded-t-2xl sm:rounded-2xl w-full max-w-md sm:mx-auto flex flex-col outline-none"
          style={{ maxHeight: 'min(85vh, 680px)' }}
          dir="rtl"
        >
          <DialogPrimitive.Title className="sr-only">הוסף מאשר</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">בחירת משתמש והגדרת היקף אישור לבקרת ביצוע</DialogPrimitive.Description>

          <div className="flex-shrink-0 bg-white border-b border-slate-100 px-4 py-3 flex items-center justify-between rounded-t-2xl">
            <h3 className="font-bold text-slate-800 flex items-center gap-2 text-base">
              <ShieldCheck className="w-4.5 h-4.5 text-amber-600" />
              הוסף מאשר
            </h3>
            <DialogPrimitive.Close asChild>
              <button className="p-2 hover:bg-slate-100 active:bg-slate-200 rounded-xl min-w-[44px] min-h-[44px] flex items-center justify-center transition-colors">
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </DialogPrimitive.Close>
          </div>

          <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-4 space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-2">בחר משתמש</label>

              {selectedUser && (
                <div className="flex items-center gap-2.5 p-2.5 bg-amber-50 border border-amber-200 rounded-xl mb-2">
                  <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center text-amber-700 font-bold text-sm flex-shrink-0">
                    {(selectedUser.user_name || selectedUser.user_email || '?')[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-800 truncate">{selectedUser.user_name || selectedUser.user_email}</p>
                    <p className="text-[11px] text-slate-500">{getRoleLabel(selectedUser.role)}</p>
                  </div>
                  <button onClick={() => setSelectedUserId('')} className="p-1.5 hover:bg-amber-100 rounded-lg transition-colors">
                    <X className="w-3.5 h-3.5 text-amber-600" />
                  </button>
                </div>
              )}

              {!selectedUser && (
                <>
                  <div className="sticky top-0 z-10 bg-white pb-2">
                    <div className="relative">
                      <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                      <input
                        ref={searchRef}
                        type="text"
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        placeholder="חפש לפי שם או אימייל..."
                        className="w-full pr-9 pl-3 py-2.5 border border-slate-200 rounded-xl text-sm text-right focus:outline-none focus:ring-2 focus:ring-amber-200 focus:border-amber-300 min-h-[44px] transition-all"
                        dir="rtl"
                      />
                    </div>
                  </div>

                  <div className="max-h-[200px] overflow-y-auto overscroll-contain border border-slate-200 rounded-xl divide-y divide-slate-100">
                    {filteredMembers.length === 0 ? (
                      <div className="px-4 py-6 text-center">
                        <Users className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                        <p className="text-sm text-slate-500 font-medium">
                          {members.length === 0 ? 'אין משתמשים מתאימים להוספה' : 'לא נמצאו תוצאות'}
                        </p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {members.length === 0 ? 'כל חברי הפרויקט כבר מוגדרים כמאשרים' : 'נסה מילות חיפוש אחרות'}
                        </p>
                      </div>
                    ) : (
                      filteredMembers.map(m => (
                        <button
                          key={m.user_id}
                          onClick={() => { setSelectedUserId(m.user_id); setSearchQuery(''); }}
                          className="w-full px-3 py-2.5 text-right hover:bg-amber-50 active:bg-amber-100 transition-colors flex items-center gap-2.5 min-h-[52px]"
                        >
                          <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 font-bold text-sm flex-shrink-0">
                            {(m.user_name || m.user_email || '?')[0]}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-slate-800 truncate">{m.user_name || m.user_email || m.user_id}</p>
                            <p className="text-[11px] text-slate-400">{getRoleLabel(m.role)}</p>
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-2">היקף אישור</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setMode('all')}
                  className={`flex-1 py-2.5 px-3 rounded-xl border text-sm font-medium transition-all min-h-[44px] ${
                    mode === 'all'
                      ? 'bg-amber-50 border-amber-300 text-amber-700'
                      : 'bg-white border-slate-200 text-slate-500 active:bg-slate-50'
                  }`}
                >
                  כל השלבים
                </button>
                <button
                  onClick={() => setMode('stages')}
                  className={`flex-1 py-2.5 px-3 rounded-xl border text-sm font-medium transition-all min-h-[44px] ${
                    mode === 'stages'
                      ? 'bg-amber-50 border-amber-300 text-amber-700'
                      : 'bg-white border-slate-200 text-slate-500 active:bg-slate-50'
                  }`}
                >
                  שלבים נבחרים
                </button>
              </div>
            </div>

            {mode === 'stages' && (
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-2">בחר שלבים</label>
                <div className="space-y-1.5">
                  {stages.map(s => {
                    const isSelected = selectedStages.includes(s.code);
                    return (
                      <button
                        key={s.code}
                        onClick={() => toggleStage(s.code)}
                        className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl border text-sm text-right transition-all min-h-[44px] ${
                          isSelected
                            ? 'bg-amber-50 border-amber-300 text-amber-700'
                            : 'bg-white border-slate-200 text-slate-600 active:bg-slate-50'
                        }`}
                      >
                        <div className={`w-5 h-5 rounded border flex items-center justify-center flex-shrink-0 ${
                          isSelected ? 'bg-amber-500 border-amber-500' : 'border-slate-300'
                        }`}>
                          {isSelected && <Check className="w-3 h-3 text-white" />}
                        </div>
                        <span>{s.label_he}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="flex-shrink-0 border-t border-slate-100 px-4 py-3 bg-white rounded-b-2xl"
            style={{ paddingBottom: 'max(12px, env(safe-area-inset-bottom))' }}>
            <Button
              onClick={handleSubmit}
              disabled={submitting || !selectedUserId}
              className="w-full bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white min-h-[48px] text-sm font-bold rounded-xl transition-all"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin ml-1.5" /> : <Plus className="w-4 h-4 ml-1.5" />}
              {submitting ? 'מוסיף...' : 'הוסף מאשר'}
            </Button>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
};

export default QCApproversTab;
