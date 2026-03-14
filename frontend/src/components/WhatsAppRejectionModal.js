import React, { useState, useEffect, useCallback } from 'react';
import { qcService } from '../services/api';
import { getRoleLabel } from '../utils/roleLabels';
import { toast } from 'sonner';
import { X, Loader2, Send, Phone, PhoneOff, Users } from 'lucide-react';
import * as DialogPrimitive from '@radix-ui/react-dialog';

export default function WhatsAppRejectionModal({ runId, stageId, itemId, rejectionContext, onClose }) {
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);

  const buildDefaultMessage = useCallback(() => {
    const parts = [];
    if (rejectionContext?.stageTitle) {
      parts.push(`שלב: ${rejectionContext.stageTitle}`);
    }
    if (rejectionContext?.itemTitle) {
      parts.push(`סעיף: ${rejectionContext.itemTitle}`);
    }
    if (rejectionContext?.reason) {
      parts.push(`סיבת דחייה: ${rejectionContext.reason}`);
    }
    if (rejectionContext?.buildingName || rejectionContext?.floorName) {
      const location = [rejectionContext.buildingName, rejectionContext.floorName].filter(Boolean).join(' / ');
      parts.push(`מיקום: ${location}`);
    }
    return parts.length > 0 ? parts.join('\n') : 'הודעת דחייה מבקרת ביצוע';
  }, [rejectionContext]);

  useEffect(() => {
    setMessage(buildDefaultMessage());
  }, [buildDefaultMessage]);

  useEffect(() => {
    const fetchContacts = async () => {
      try {
        setLoading(true);
        const data = await qcService.getTeamContacts(runId);
        setContacts(data.contacts || data.members || []);
      } catch (err) {
        toast.error('שגיאה בטעינת אנשי קשר');
        onClose();
      } finally {
        setLoading(false);
      }
    };
    fetchContacts();
  }, [runId, onClose]);

  const handleSend = async () => {
    if (!selectedUserId) {
      toast.error('יש לבחור נמען');
      return;
    }
    setSending(true);
    try {
      const payload = {
        recipient_user_id: selectedUserId,
        message: message.trim() || undefined,
      };
      if (itemId) {
        payload.item_id = itemId;
      }
      await qcService.notifyRejection(runId, stageId, payload);
      toast.success('הודעת WhatsApp נשלחה בהצלחה');
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : (typeof detail === 'object' ? detail.message : 'שגיאה בשליחת ההודעה');
      toast.error(msg);
    } finally {
      setSending(false);
    }
  };

  const availableContacts = contacts.filter(c => c.has_whatsapp);
  const hasAnyAvailable = availableContacts.length > 0;

  return (
    <DialogPrimitive.Root open={true} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 bg-black/40 z-50" />
        <DialogPrimitive.Content
          className="fixed inset-x-0 bottom-0 sm:bottom-auto sm:left-[50%] sm:top-[50%] sm:-translate-x-1/2 sm:-translate-y-1/2 z-50 bg-white rounded-t-2xl sm:rounded-2xl w-full max-w-md sm:mx-auto max-h-[85vh] flex flex-col outline-none"
          dir="rtl"
        >
          <DialogPrimitive.Title className="sr-only">שלח הודעת דחייה ב-WhatsApp</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">בחירת נמען ושליחת הודעת דחייה באמצעות WhatsApp</DialogPrimitive.Description>
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between flex-shrink-0">
            <h3 className="font-bold text-slate-800 flex items-center gap-2 text-sm">
              <Phone className="w-4 h-4 text-green-600" />
              שלח הודעת דחייה ב-WhatsApp
            </h3>
            <DialogPrimitive.Close asChild>
              <button className="p-1 hover:bg-slate-100 rounded-lg">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </DialogPrimitive.Close>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
              </div>
            ) : !hasAnyAvailable ? (
              <div className="text-center py-6">
                <PhoneOff className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                <p className="text-sm font-medium text-slate-600 mb-1">אין אנשי צוות ניהול עם WhatsApp זמין</p>
                <p className="text-xs text-slate-400">אנשי הצוות צריכים להוסיף מספר טלפון לפרופיל שלהם</p>
              </div>
            ) : (
              <>
                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-2 flex items-center gap-1.5">
                    <Users className="w-3.5 h-3.5 text-slate-500" />
                    בחר נמען מצוות הניהול
                  </label>
                  <p className="text-[11px] text-slate-400 mb-1.5">ניתן לשלוח רק לצוות ניהול הפרויקט</p>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {contacts.map(contact => {
                      const isAvailable = contact.has_whatsapp;
                      const isSelected = selectedUserId === contact.user_id;
                      return (
                        <button
                          key={contact.user_id}
                          disabled={!isAvailable}
                          onClick={() => setSelectedUserId(isSelected ? null : contact.user_id)}
                          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border text-right transition-all min-h-[48px] ${
                            !isAvailable
                              ? 'opacity-50 cursor-not-allowed bg-slate-50 border-slate-100'
                              : isSelected
                                ? 'bg-green-50 border-green-300 ring-2 ring-green-200'
                                : 'bg-white border-slate-200 hover:border-slate-300 active:bg-slate-50'
                          }`}
                          dir="rtl"
                        >
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                            isSelected ? 'bg-green-200 text-green-800' : 'bg-slate-100 text-slate-600'
                          }`}>
                            {(contact.name || '?')[0]}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className={`text-sm font-medium truncate ${!isAvailable ? 'text-slate-400' : 'text-slate-700'}`}>
                              {contact.name || 'משתמש'}
                            </p>
                            <p className="text-[11px] text-slate-400">{getRoleLabel(contact.role)}</p>
                          </div>
                          <div className="flex-shrink-0">
                            {isAvailable ? (
                              <span className="flex items-center gap-1 text-[10px] text-green-600 font-medium">
                                <Phone className="w-3 h-3" />
                                זמין
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-[10px] text-slate-400">
                                <PhoneOff className="w-3 h-3" />
                                אין טלפון
                              </span>
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-600 mb-1.5">תוכן ההודעה</label>
                  <textarea
                    value={message}
                    onChange={e => setMessage(e.target.value)}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-300"
                    rows={4}
                    dir="rtl"
                    placeholder="הודעת דחייה..."
                  />
                </div>
              </>
            )}
          </div>

          <div className="px-4 py-3 border-t border-slate-100 flex gap-2 flex-shrink-0">
            <DialogPrimitive.Close asChild>
              <button
                className="flex-1 py-2.5 rounded-lg border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 active:bg-slate-100 min-h-[44px]">
                {hasAnyAvailable ? 'ביטול' : 'סגור'}
              </button>
            </DialogPrimitive.Close>
            {hasAnyAvailable && (
              <button onClick={handleSend} disabled={sending || !selectedUserId}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-bold transition-all min-h-[44px] ${
                  selectedUserId
                    ? 'bg-green-600 hover:bg-green-700 active:bg-green-800 text-white'
                    : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                }`}>
                {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                {sending ? 'שולח...' : 'שלח'}
              </button>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
