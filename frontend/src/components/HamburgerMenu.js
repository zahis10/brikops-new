import React, { useState, useRef } from 'react';
import { Sheet, SheetPortal, SheetOverlay, SheetClose, SheetTitle, SheetDescription } from './ui/sheet';
import * as SheetPrimitive from '@radix-ui/react-dialog';
import { Menu, KeyRound, FilePen, ClipboardCheck, CreditCard, Settings, Globe, LogOut, X, Camera, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { authService } from '../services/api';

const MENU_ITEMS = [
  { id: 'handover-template', label: 'תבנית מסירה', icon: KeyRound, type: 'tab' },
  { id: 'qc-template', label: 'תבנית בקרת ביצוע', icon: FilePen, type: 'tab' },
  { id: 'settings', label: 'מאשרי בקרת ביצוע', icon: ClipboardCheck, type: 'tab' },
  { id: 'billing', label: 'מנוי ותשלום', icon: CreditCard, type: 'tab', billingOnly: true },
  { id: 'divider-1', type: 'divider' },
  { id: 'account-settings', label: 'הגדרות חשבון', icon: Settings, type: 'navigate', path: '/settings/account' },
  { id: 'language', label: 'שפה', icon: Globe, type: 'navigate', path: '/settings/account#language' },
  { id: 'divider-2', type: 'divider' },
  { id: 'logout', label: 'התנתקות', icon: LogOut, type: 'action', action: 'logout' },
];

const ROLE_LABELS = {
  project_manager: 'מנהל פרויקט',
  management_team: 'צוות ניהול',
  contractor: 'קבלן',
  viewer: 'צופה',
};

export default function HamburgerMenu({ onSelectTab, showBilling, onNavigate, onLogout, slim = false }) {
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);
  const { user, refreshUser } = useAuth();

  const handleItem = (item) => {
    setOpen(false);
    if (item.type === 'tab') {
      onSelectTab(item.id);
    } else if (item.type === 'navigate') {
      onNavigate(item.path);
    } else if (item.action === 'logout') {
      onLogout();
    }
  };

  const visibleItems = MENU_ITEMS.filter(item => {
    if (slim && (item.type === 'tab' || item.id === 'divider-1')) return false;
    if (item.billingOnly && !showBilling) return false;
    return true;
  });

  const handlePhotoPick = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || uploading) return;
    setUploading(true);
    try {
      await authService.uploadProfilePhoto(file);
      await refreshUser();
      toast.success('התמונה עודכנה');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בהעלאת התמונה');
    } finally {
      setUploading(false);
    }
  };

  const handleRemovePhoto = async () => {
    if (uploading) return;
    setUploading(true);
    try {
      await authService.removeProfilePhoto();
      await refreshUser();
      toast.success('התמונה הוסרה');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה בהסרת התמונה');
    } finally {
      setUploading(false);
    }
  };

  const roleLabel = user?.platform_role === 'super_admin'
    ? 'Super Admin'
    : (ROLE_LABELS[user?.role] || user?.role || '');

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="h-11 w-11 flex items-center justify-center bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors"
        title="תפריט"
      >
        <Menu className="w-4 h-4" />
      </button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetPortal>
          <SheetOverlay className="fixed inset-0 z-[9998] bg-black/40" />
          <SheetPrimitive.Content
            className="fixed top-0 right-0 z-[9999] h-full w-72 max-w-[85vw] bg-white shadow-xl flex flex-col data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right data-[state=closed]:duration-300 data-[state=open]:duration-300"
            dir="rtl"
          >
            <SheetTitle className="sr-only">תפריט</SheetTitle>
            <SheetDescription className="sr-only">תפריט ניווט</SheetDescription>

            {/* BATCH visual-user-panel — scene band */}
            <div
              className="relative overflow-hidden"
              style={{
                height: 118,
                background: 'radial-gradient(200px 100px at 50% 18%, rgba(245,158,11,.16), transparent 70%), linear-gradient(178deg, #17202b 0%, #212d3b 100%)',
              }}
              aria-hidden
            >
              <div
                className="absolute left-0 right-0"
                style={{
                  bottom: 40,
                  height: 2,
                  background: 'linear-gradient(90deg, transparent, rgba(245,158,11,.5), transparent)',
                  filter: 'blur(1px)',
                }}
              />
              <svg
                className="absolute bottom-0 left-0 right-0 w-full"
                style={{ height: 70, opacity: 0.55 }}
                viewBox="0 0 300 70"
                preserveAspectRatio="xMidYMax slice"
              >
                <g fill="#111a24">
                  <rect x="0" y="32" width="38" height="38" /><rect x="42" y="42" width="26" height="28" />
                  <rect x="72" y="26" width="32" height="44" /><rect x="108" y="46" width="22" height="24" />
                  <rect x="172" y="36" width="36" height="34" /><rect x="212" y="45" width="24" height="25" />
                  <rect x="240" y="29" width="30" height="41" /><rect x="274" y="41" width="26" height="29" />
                  <rect x="138" y="8" width="3.5" height="62" /><rect x="110" y="8" width="84" height="3.5" />
                  <path d="M140 8 L126 22 L140 22 Z" opacity=".9" />
                </g>
                <g fill="#f5a623" opacity=".3">
                  <rect x="7" y="38" width="3.5" height="3.5" /><rect x="78" y="33" width="3.5" height="3.5" />
                  <rect x="180" y="42" width="3.5" height="3.5" /><rect x="248" y="36" width="3.5" height="3.5" />
                </g>
              </svg>
            </div>
            <SheetClose className="absolute top-2 left-2 p-1 rounded-md text-slate-300 hover:text-white">
              <X className="w-5 h-5" />
            </SheetClose>

            {/* Identity block */}
            <div className="text-center -mt-[34px] relative z-10 pb-3 border-b border-slate-200">
              <div className="relative inline-block">
                <div
                  className="w-[68px] h-[68px] rounded-full border-[3px] border-white overflow-hidden bg-white"
                  style={{ boxShadow: '0 8px 20px rgba(10,16,26,.25)' }}
                >
                  {user?.profile_photo_display_url ? (
                    <img
                      src={user.profile_photo_display_url}
                      alt=""
                      className="w-full h-full rounded-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full rounded-full bg-[#f59e0b] flex items-center justify-center">
                      <span className="text-white font-bold text-2xl">
                        {(user?.name || '?').charAt(0)}
                      </span>
                    </div>
                  )}
                  {uploading && (
                    <div className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center">
                      <Loader2 className="w-5 h-5 text-white animate-spin" />
                    </div>
                  )}
                </div>
                <button
                  onClick={() => !uploading && fileInputRef.current?.click()}
                  disabled={uploading}
                  className="absolute bottom-0 left-0 w-[22px] h-[22px] rounded-full bg-white border border-slate-200 flex items-center justify-center shadow-sm"
                  title="שינוי תמונה"
                >
                  <Camera className="w-3 h-3 text-slate-600" />
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  disabled={uploading}
                  onChange={handlePhotoPick}
                />
              </div>
              <div className="mt-1.5 px-3">
                <div className="text-sm font-bold text-slate-800 truncate">{user?.name || ''}</div>
                {(user?.email || user?.phone_e164 || user?.phone) && (
                  <div className="text-xs text-slate-500 truncate">
                    {user?.email || user?.phone_e164 || user?.phone}
                  </div>
                )}
                {roleLabel && (
                  <span className="inline-block mt-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-[11px] font-medium">
                    {roleLabel}
                  </span>
                )}
                {user?.profile_photo_display_url && (
                  <div>
                    <button
                      onClick={handleRemovePhoto}
                      disabled={uploading}
                      className="mt-1 text-[11px] text-slate-400 hover:text-red-600 transition-colors"
                    >
                      הסר תמונה
                    </button>
                  </div>
                )}
              </div>
            </div>

            <nav className="flex-1 overflow-y-auto py-2">
              {visibleItems.map(item => {
                if (item.type === 'divider') {
                  return <div key={item.id} className="my-2 mx-4 border-t border-slate-200" />;
                }
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleItem(item)}
                    className={`w-full flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors hover:bg-slate-50 active:bg-slate-100 ${
                      item.action === 'logout' ? 'text-red-600' : 'text-slate-700'
                    }`}
                  >
                    <Icon className="w-5 h-5 shrink-0" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </nav>
          </SheetPrimitive.Content>
        </SheetPortal>
      </Sheet>
    </>
  );
}
