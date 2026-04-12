import React, { useState } from 'react';
import { Sheet, SheetPortal, SheetOverlay, SheetClose, SheetTitle, SheetDescription } from './ui/sheet';
import * as SheetPrimitive from '@radix-ui/react-dialog';
import { Menu, KeyRound, FilePen, ClipboardCheck, CreditCard, Settings, Globe, LogOut, X } from 'lucide-react';

const MENU_ITEMS = [
  { id: 'handover-template', label: 'תבנית מסירה', icon: KeyRound, type: 'tab' },
  { id: 'qc-template', label: 'תבנית בקרת ביצוע', icon: FilePen, type: 'tab' },
  { id: 'settings', label: 'מאשרי בקרת ביצוע', icon: ClipboardCheck, type: 'tab' },
  { id: 'billing', label: 'מנוי ותשלום', icon: CreditCard, type: 'tab', billingOnly: true },
  { id: 'divider-1', type: 'divider' },
  { id: 'account-settings', label: 'הגדרות חשבון', icon: Settings, type: 'navigate', path: '/settings/account' },
  { id: 'language', label: 'שפה', icon: Globe, type: 'navigate', path: '/settings/account' },
  { id: 'divider-2', type: 'divider' },
  { id: 'logout', label: 'התנתקות', icon: LogOut, type: 'action', action: 'logout' },
];

export default function HamburgerMenu({ onSelectTab, showBilling, onNavigate, onLogout }) {
  const [open, setOpen] = useState(false);

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
    if (item.billingOnly && !showBilling) return false;
    return true;
  });

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="p-1.5 bg-white/[0.07] border border-white/10 rounded-[10px] hover:bg-white/[0.14] transition-colors"
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

            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
              <span className="text-base font-semibold text-slate-800">תפריט</span>
              <SheetClose className="p-1 rounded-md hover:bg-slate-100">
                <X className="w-5 h-5 text-slate-500" />
              </SheetClose>
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
