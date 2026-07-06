import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Wrench, ArrowRight, ChevronLeft, Plus, Pencil, History, FileText, Search, X,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { safetyService } from '../../services/api';
import { EQUIPMENT_CATEGORY_HE } from './safetyLabels';
import SafetyEquipmentForm from './SafetyEquipmentForm';
import SafetyEquipmentCheckModal from './SafetyEquipmentCheckModal';
import SafetyEquipmentHistory from './SafetyEquipmentHistory';

// The whole ציוד experience (batch safety-p3b). Category screen → items screen →
// renewal / edit / history. Drill-down state lives in the URL (?equipCat=) so the
// hardware BACK button pops items → categories → previous tab. The page owns the
// summary (tab counter + category counters); this tab fetches ONLY item lists.
const EMPTY = { items: [], total: 0 };
const CAT_KEYS = Object.keys(EQUIPMENT_CATEGORY_HE);
const catLabel = (c) => EQUIPMENT_CATEGORY_HE[c] || c;
const heDate = (v) => (v ? new Date(v).toLocaleDateString('he-IL') : '');
const isHttp = (u) => typeof u === 'string' && /^https?:\/\//i.test(u);

function TrackChip({ track }) {
  if (track.state === 'valid') {
    return (
      <span className="inline-block px-2 py-0.5 rounded text-xs bg-emerald-100 text-emerald-800">
        {track.expires_at ? `בתוקף עד ${heDate(track.expires_at)}` : 'בתוקף'}
      </span>
    );
  }
  if (track.state === 'expired') {
    return (
      <span className="inline-block px-2 py-0.5 rounded text-xs bg-red-100 text-red-800">
        {`פג תוקף ${heDate(track.expires_at)}`}
      </span>
    );
  }
  return (
    <span className="inline-block px-2 py-0.5 rounded text-xs border border-red-300 text-red-700">
      לא בוצע
    </span>
  );
}

function ItemCard({ item, showCategory, isWriter, onEdit, onHistory, onRenew }) {
  const decommissioned = item.status === 'decommissioned';
  let badge;
  if (decommissioned) {
    badge = { cls: 'bg-slate-200 text-slate-700', text: 'הוצא משימוש' };
  } else if ((item.check_status || []).some((t) => t.state === 'expired' || t.state === 'missing')) {
    badge = { cls: 'bg-red-100 text-red-800', text: 'לא תקין' };
  } else {
    badge = { cls: 'bg-emerald-100 text-emerald-800', text: 'תקין' };
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-slate-900">{item.internal_code}</span>
            <Badge className={badge.cls}>{badge.text}</Badge>
          </div>
          {showCategory && (
            <p className="text-xs text-slate-400 mt-0.5">{catLabel(item.category)}</p>
          )}
          {item.description && <p className="text-sm text-slate-500 mt-0.5">{item.description}</p>}
          {(item.serial_number || item.manufacturer) && (
            <p className="text-xs text-slate-400 mt-0.5">
              {[item.serial_number, item.manufacturer].filter(Boolean).join(' · ')}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {isWriter && (
            <button type="button" aria-label="ערוך" onClick={() => onEdit(item)} className="p-2 rounded-lg hover:bg-slate-100">
              <Pencil className="w-4 h-4 text-slate-600" />
            </button>
          )}
          <button type="button" aria-label="היסטוריה" onClick={() => onHistory(item)} className="p-2 rounded-lg hover:bg-slate-100">
            <History className="w-4 h-4 text-slate-600" />
          </button>
        </div>
      </div>

      <div className="space-y-1.5 border-t border-slate-100 pt-2">
        {(item.check_status || []).map((track) => (
          <div key={track.check_name} className="flex items-center justify-between gap-2 flex-wrap">
            <div className="min-w-0">
              <span className="text-sm text-slate-700">{track.check_name}</span>
              <span className="text-xs text-slate-400 mr-2">
                {track.period_days ? `כל ${track.period_days} ימים` : 'לפי אירוע'}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <TrackChip track={track} />
              {isHttp(track.document_display_url) && (
                <button
                  type="button"
                  aria-label="מסמך תסקיר"
                  onClick={() => window.open(track.document_display_url, '_blank', 'noopener')}
                  className="p-1.5 rounded-lg hover:bg-slate-100"
                >
                  <FileText className="w-4 h-4 text-purple-600" />
                </button>
              )}
              {isWriter && !decommissioned && (
                <Button
                  type="button"
                  variant="outline"
                  className="h-8 px-3 text-xs"
                  onClick={() => onRenew(item, { check_name: track.check_name, period_days: track.period_days })}
                >
                  חידוש
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SafetyEquipmentTab({ projectId, isWriter, summary, onChanged }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedCategory = searchParams.get('equipCat');

  const [items, setItems] = useState(EMPTY);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [itemForm, setItemForm] = useState({ open: false, record: null, presetCategory: null });
  const [checkModal, setCheckModal] = useState({ open: false, equipment: null, track: null });
  const [historyFor, setHistoryFor] = useState(null);

  // Items view — fetch when a category is selected.
  useEffect(() => {
    if (!selectedCategory) return undefined;
    let cancelled = false;
    setItemsLoading(true);
    (async () => {
      try {
        const r = await safetyService.listEquipment(projectId, { category: selectedCategory, limit: 200 });
        if (!cancelled) setItems(r || EMPTY);
      } catch (e) {
        if (!cancelled) toast.error('שגיאה בטעינת ציוד');
      } finally {
        if (!cancelled) setItemsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [projectId, selectedCategory]);

  // Search mode (category screen only) — debounced cross-category search.
  useEffect(() => {
    if (selectedCategory) return undefined;
    const q = searchQ.trim();
    if (!q) { setItems(EMPTY); return undefined; }
    let cancelled = false;
    const t = setTimeout(async () => {
      setItemsLoading(true);
      try {
        const r = await safetyService.listEquipment(projectId, { q, limit: 100 });
        if (!cancelled) setItems(r || EMPTY);
      } catch (e) {
        if (!cancelled) toast.error('שגיאה בטעינת ציוד');
      } finally {
        if (!cancelled) setItemsLoading(false);
      }
    }, 400);
    return () => { cancelled = true; clearTimeout(t); };
  }, [projectId, selectedCategory, searchQ]);

  const refreshItems = async () => {
    if (selectedCategory) {
      setItemsLoading(true);
      try {
        const r = await safetyService.listEquipment(projectId, { category: selectedCategory, limit: 200 });
        setItems(r || EMPTY);
      } catch (e) {
        toast.error('שגיאה בטעינת ציוד');
      } finally {
        setItemsLoading(false);
      }
    } else if (searchQ.trim()) {
      setItemsLoading(true);
      try {
        const r = await safetyService.listEquipment(projectId, { q: searchQ.trim(), limit: 100 });
        setItems(r || EMPTY);
      } catch (e) {
        toast.error('שגיאה בטעינת ציוד');
      } finally {
        setItemsLoading(false);
      }
    }
  };

  const afterMutation = () => { refreshItems(); onChanged?.(); };

  const enterCategory = (value) => {
    const next = new URLSearchParams(searchParams);
    next.set('equipCat', value);
    setSearchParams(next);
  };
  const backToCategories = () => {
    const next = new URLSearchParams(searchParams);
    next.delete('equipCat');
    setSearchParams(next);
  };

  // ---- VIEW B: items inside a category ----
  if (selectedCategory) {
    const sorted = [...(items.items || [])].sort((a, b) => {
      const av = a.status === 'active' ? 0 : 1;
      const bv = b.status === 'active' ? 0 : 1;
      return av - bv;
    });

    return (
      <div className="p-4 space-y-3">
        <div className="flex items-center gap-2">
          <button type="button" aria-label="חזור לקטגוריות" onClick={backToCategories} className="p-2 rounded-lg hover:bg-slate-100">
            <ArrowRight className="w-5 h-5 text-slate-700" />
          </button>
          <h2 className="flex-1 min-w-0 text-base font-bold text-slate-900 truncate">{catLabel(selectedCategory)}</h2>
          {isWriter && (
            <Button
              type="button"
              onClick={() => setItemForm({ open: true, record: null, presetCategory: selectedCategory })}
              className="h-9 px-3 text-sm"
            >
              <Plus className="w-4 h-4 ml-1" />
              הוסף פריט
            </Button>
          )}
        </div>

        {itemsLoading ? (
          <p className="text-center text-sm text-slate-400 py-8">טוען…</p>
        ) : sorted.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center space-y-3">
            <p className="text-sm text-slate-500">אין פריטים בקטגוריה זו</p>
            {isWriter && (
              <Button type="button" onClick={() => setItemForm({ open: true, record: null, presetCategory: selectedCategory })} className="h-9 px-3 text-sm">
                <Plus className="w-4 h-4 ml-1" />
                הוסף פריט
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {sorted.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                showCategory={false}
                isWriter={isWriter}
                onEdit={(it) => setItemForm({ open: true, record: it, presetCategory: null })}
                onHistory={(it) => setHistoryFor(it)}
                onRenew={(it, track) => setCheckModal({ open: true, equipment: it, track })}
              />
            ))}
          </div>
        )}

        <SafetyEquipmentForm
          projectId={projectId}
          item={itemForm.record}
          presetCategory={itemForm.presetCategory}
          open={itemForm.open}
          onClose={() => setItemForm({ open: false, record: null, presetCategory: null })}
          onSaved={afterMutation}
        />
        <SafetyEquipmentCheckModal
          projectId={projectId}
          equipment={checkModal.equipment}
          track={checkModal.track}
          open={checkModal.open}
          onClose={() => setCheckModal({ open: false, equipment: null, track: null })}
          onSaved={afterMutation}
        />
        <SafetyEquipmentHistory
          projectId={projectId}
          equipment={historyFor}
          open={!!historyFor}
          onClose={() => setHistoryFor(null)}
        />
      </div>
    );
  }

  // ---- VIEW A: categories (+ search) ----
  const summaryByCat = {};
  (summary?.items || []).forEach((s) => { summaryByCat[s.category] = s; });
  const customCats = [...new Set((summary?.items || []).map((s) => s.category).filter((c) => !CAT_KEYS.includes(c)))];
  const allCats = [...CAT_KEYS, ...customCats];

  const searching = searchQ.trim().length > 0;

  return (
    <div className="p-4 space-y-3">
      <div className="relative">
        <Search className="w-4 h-4 text-slate-400 absolute top-1/2 -translate-y-1/2 right-3" />
        <Input
          dir="rtl"
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
          placeholder="חפש פריט ציוד…"
          className="pr-9 pl-9"
        />
        {searchQ && (
          <button
            type="button"
            aria-label="נקה חיפוש"
            onClick={() => setSearchQ('')}
            className="absolute top-1/2 -translate-y-1/2 left-2 p-1 rounded-lg hover:bg-slate-100"
          >
            <X className="w-4 h-4 text-slate-500" />
          </button>
        )}
      </div>

      {searching ? (
        itemsLoading ? (
          <p className="text-center text-sm text-slate-400 py-8">טוען…</p>
        ) : (items.items || []).length === 0 ? (
          <p className="text-center text-sm text-slate-500 py-8">לא נמצאו פריטים</p>
        ) : (
          <div className="space-y-3">
            {(items.items || []).map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                showCategory
                isWriter={isWriter}
                onEdit={(it) => setItemForm({ open: true, record: it, presetCategory: null })}
                onHistory={(it) => setHistoryFor(it)}
                onRenew={(it, track) => setCheckModal({ open: true, equipment: it, track })}
              />
            ))}
          </div>
        )
      ) : (
        <div className="space-y-2">
          {allCats.map((cat) => {
            const s = summaryByCat[cat];
            return (
              <button
                key={cat}
                type="button"
                onClick={() => enterCategory(cat)}
                className="w-full min-h-[56px] flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-right hover:bg-slate-50"
              >
                <Wrench className="w-5 h-5 text-slate-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-900 truncate">{catLabel(cat)}</p>
                  <div className="flex items-center gap-2 flex-wrap mt-0.5">
                    {s && s.total > 0 ? (
                      <>
                        <span className="text-xs text-slate-500">{`${s.total} פריטים`}</span>
                        {s.expired > 0 && (
                          <span className="text-xs px-2 py-0.5 rounded bg-red-100 text-red-800">{`${s.expired} לא תקין`}</span>
                        )}
                        {s.ok > 0 && (
                          <span className="text-xs px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">{`${s.ok} תקין`}</span>
                        )}
                      </>
                    ) : (
                      <span className="text-xs text-slate-400">אין פריטים</span>
                    )}
                  </div>
                </div>
                <ChevronLeft className="w-5 h-5 text-slate-400 shrink-0" />
              </button>
            );
          })}
        </div>
      )}

      <SafetyEquipmentForm
        projectId={projectId}
        item={itemForm.record}
        presetCategory={itemForm.presetCategory}
        open={itemForm.open}
        onClose={() => setItemForm({ open: false, record: null, presetCategory: null })}
        onSaved={afterMutation}
      />
      <SafetyEquipmentCheckModal
        projectId={projectId}
        equipment={checkModal.equipment}
        track={checkModal.track}
        open={checkModal.open}
        onClose={() => setCheckModal({ open: false, equipment: null, track: null })}
        onSaved={afterMutation}
      />
      <SafetyEquipmentHistory
        projectId={projectId}
        equipment={historyFor}
        open={!!historyFor}
        onClose={() => setHistoryFor(null)}
      />
    </div>
  );
}
