import React, { useState } from 'react';
import { toast } from 'sonner';
import { Pencil, Trash2, Check, X, Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from './ui/dialog';
import { disciplineService } from '../services/api';

const DisciplineManagerModal = ({ projectId, disciplines, open, onClose, onChanged }) => {
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const customDisciplines = (disciplines || []).filter(d => d.source === 'custom');

  const resetState = () => {
    setEditingId(null);
    setEditValue('');
    setConfirmDeleteId(null);
    setBusyId(null);
  };

  const handleOpenChange = (next) => {
    if (!next) {
      resetState();
      onClose && onClose();
    }
  };

  const startEdit = (d) => {
    setEditingId(d.id);
    setEditValue(d.label || '');
    setConfirmDeleteId(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditValue('');
  };

  const saveEdit = async (d) => {
    const label = editValue.trim();
    if (!label) {
      toast.error('שם תחום נדרש');
      return;
    }
    setBusyId(d.id);
    try {
      await disciplineService.update(projectId, d.id, label);
      toast.success('התחום עודכן');
      setEditingId(null);
      setEditValue('');
      onChanged && onChanged();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'שגיאה בעדכון');
    } finally {
      setBusyId(null);
    }
  };

  const startDelete = (d) => {
    setConfirmDeleteId(d.id);
    setEditingId(null);
  };

  const cancelDelete = () => setConfirmDeleteId(null);

  const confirmDelete = async (d) => {
    setBusyId(d.id);
    try {
      await disciplineService.remove(projectId, d.id);
      toast.success('התחום נמחק');
      setConfirmDeleteId(null);
      onChanged && onChanged();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'שגיאה במחיקה');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>ניהול תחומים</DialogTitle>
        </DialogHeader>
        <div className="py-2 max-h-[60vh] overflow-y-auto">
          {customDisciplines.length === 0 ? (
            <div className="text-center py-8 text-sm text-slate-400">אין תחומים מותאמים אישית</div>
          ) : (
            <div className="space-y-1">
              {customDisciplines.map((d) => {
                const busy = busyId === d.id;
                if (editingId === d.id) {
                  return (
                    <div key={d.id} className="flex items-center gap-2 py-2 px-2 rounded-lg bg-amber-50">
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') saveEdit(d);
                          if (e.key === 'Escape') cancelEdit();
                        }}
                        className="flex-1 h-8 px-2 text-sm bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-300"
                      />
                      <button
                        onClick={() => saveEdit(d)}
                        disabled={busy || !editValue.trim()}
                        className="h-8 px-3 text-xs font-medium bg-amber-500 hover:bg-amber-600 text-white rounded-lg disabled:opacity-50 flex items-center gap-1"
                      >
                        {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                        שמור
                      </button>
                      <button
                        onClick={cancelEdit}
                        disabled={busy}
                        className="h-8 px-2 text-xs text-slate-500 hover:text-slate-700"
                      >
                        ביטול
                      </button>
                    </div>
                  );
                }
                if (confirmDeleteId === d.id) {
                  return (
                    <div key={d.id} className="flex items-center gap-2 py-2 px-2 rounded-lg bg-red-50">
                      <span className="flex-1 text-sm text-slate-700 truncate">{d.label}</span>
                      <span className="text-xs text-red-600">בטוח?</span>
                      <button
                        onClick={() => confirmDelete(d)}
                        disabled={busy}
                        className="h-8 px-3 text-xs font-medium bg-red-500 hover:bg-red-600 text-white rounded-lg disabled:opacity-50 flex items-center gap-1"
                      >
                        {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                        מחק
                      </button>
                      <button
                        onClick={cancelDelete}
                        disabled={busy}
                        className="h-8 px-2 text-xs text-slate-500 hover:text-slate-700"
                      >
                        ביטול
                      </button>
                    </div>
                  );
                }
                return (
                  <div key={d.id} className="flex items-center gap-2 py-2 px-2 rounded-lg hover:bg-slate-50">
                    <span className="flex-1 text-sm text-slate-700 truncate">{d.label}</span>
                    <button
                      onClick={() => startEdit(d)}
                      className="p-1.5 text-slate-400 hover:text-amber-600 rounded hover:bg-amber-50"
                      title="ערוך שם"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => startDelete(d)}
                      className="p-1.5 text-slate-400 hover:text-red-600 rounded hover:bg-red-50"
                      title="מחק תחום"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <button className="px-4 py-2 text-sm text-slate-500 hover:text-slate-700 rounded-lg">סגור</button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default DisciplineManagerModal;
