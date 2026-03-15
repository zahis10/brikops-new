import React, { useState, useEffect, useCallback } from 'react';
import { handoverService } from '../../services/api';
import { toast } from 'sonner';
import { t } from '../../i18n';
import { Loader2, PenLine } from 'lucide-react';

const HandoverLegalText = ({ protocol, projectId, isSigned, onUpdated }) => {
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setText(protocol?.legal_text || '');
  }, [protocol]);

  const isEdited = protocol?.legal_text_edited === true;

  const handleSave = useCallback(async () => {
    if (isSigned || saving) return;
    try {
      setSaving(true);
      await handoverService.updateProtocol(projectId, protocol.id, {
        legal_text: text,
      });
      toast.success(t('handover', 'saved'));
      onUpdated?.();
    } catch (err) {
      console.error(err);
      toast.error(t('handover', 'updateError'));
    } finally {
      setSaving(false);
    }
  }, [text, isSigned, saving, projectId, protocol?.id, onUpdated]);

  return (
    <div className="space-y-2 p-1">
      {isEdited && (
        <div className="flex items-center gap-1.5 text-amber-600">
          <PenLine className="w-3.5 h-3.5" />
          <span className="text-xs font-medium">{t('handover', 'legalTextEdited')}</span>
        </div>
      )}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={isSigned}
        className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none h-40
          focus:outline-none focus:ring-2 focus:ring-purple-300
          disabled:bg-slate-50 disabled:text-slate-500 leading-relaxed"
        dir="rtl"
      />
      {!isSigned && (
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full flex items-center justify-center gap-2 py-2 bg-purple-600 text-white rounded-lg
            text-sm font-medium hover:bg-purple-700 active:scale-[0.98] disabled:opacity-50"
        >
          {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          {saving ? t('handover', 'saving') : t('handover', 'save')}
        </button>
      )}
    </div>
  );
};

export default HandoverLegalText;
