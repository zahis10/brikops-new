import React, { useState, useEffect, useCallback } from 'react';
import { Bell, CheckCheck, Clock, ShieldCheck, ShieldX, Send, RotateCcw, X } from 'lucide-react';
import { qcNotificationService } from '../services/api';
import { useNavigate } from 'react-router-dom';
import { Popover, PopoverTrigger, PopoverContent } from './ui/popover';

const ACTION_ICONS = {
  submit_for_review: { icon: Send, color: 'text-blue-500' },
  qc_approved: { icon: ShieldCheck, color: 'text-emerald-500' },
  qc_rejected: { icon: ShieldX, color: 'text-red-500' },
  qc_reopened: { icon: RotateCcw, color: 'text-orange-500' },
};

const formatTimeAgo = (dateStr) => {
  if (!dateStr) return '';
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return 'עכשיו';
  if (diff < 3600) return `לפני ${Math.floor(diff / 60)} דק'`;
  if (diff < 86400) return `לפני ${Math.floor(diff / 3600)} שע'`;
  return `לפני ${Math.floor(diff / 86400)} ימים`;
};

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const fetchUnread = useCallback(async () => {
    try {
      const data = await qcNotificationService.getUnreadCount();
      setUnreadCount(data.unread_count || 0);
    } catch {}
  }, []);

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const data = await qcNotificationService.getNotifications(20, 0);
      setNotifications(data.notifications || []);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchUnread();
    const iv = setInterval(fetchUnread, 30000);
    return () => clearInterval(iv);
  }, [fetchUnread]);

  useEffect(() => {
    if (open) fetchNotifications();
  }, [open, fetchNotifications]);

  const handleMarkAllRead = async () => {
    try {
      await qcNotificationService.markAllRead();
      setUnreadCount(0);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch {}
  };

  const handleClick = async (notif) => {
    if (!notif.read) {
      try {
        await qcNotificationService.markRead(notif.id);
        setUnreadCount(prev => Math.max(0, prev - 1));
        setNotifications(prev => prev.map(n => n.id === notif.id ? { ...n, read: true } : n));
      } catch {}
    }
    if (notif.link) {
      setOpen(false);
      navigate(notif.link);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          className="relative h-11 w-11 flex items-center justify-center hover:bg-slate-700 rounded-lg transition-colors"
          aria-label="התראות"
          aria-haspopup="true"
          aria-expanded={open}
        >
          <Bell className="w-5 h-5 text-white" />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 flex items-center justify-center text-[9px] font-bold bg-red-500 text-white rounded-full px-1">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>

      <PopoverContent
        className="w-80 p-0 rounded-xl shadow-2xl border border-slate-200 overflow-hidden"
        align="end"
        sideOffset={8}
        collisionPadding={16}
      >
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-100 bg-slate-50">
          <h3 className="text-sm font-bold text-slate-700">התראות</h3>
          <div className="flex items-center gap-1">
            {unreadCount > 0 && (
              <button onClick={handleMarkAllRead} className="text-[10px] text-amber-600 hover:text-amber-700 font-medium flex items-center gap-1">
                <CheckCheck className="w-3 h-3" />
                סמן הכל כנקרא
              </button>
            )}
            <button onClick={() => setOpen(false)} className="p-1 hover:bg-slate-200 rounded">
              <X className="w-3.5 h-3.5 text-slate-400" />
            </button>
          </div>
        </div>

        <div className="max-h-80 overflow-y-auto">
          {loading && notifications.length === 0 ? (
            <div className="py-8 text-center text-slate-400 text-xs">טוען...</div>
          ) : notifications.length === 0 ? (
            <div className="py-8 text-center text-slate-400 text-xs">
              <Bell className="w-6 h-6 mx-auto mb-2 text-slate-300" />
              אין התראות
            </div>
          ) : (
            notifications.map(notif => {
              const actionCfg = ACTION_ICONS[notif.action] || { icon: Clock, color: 'text-slate-400' };
              const Icon = actionCfg.icon;
              return (
                <button
                  key={notif.id}
                  onClick={() => handleClick(notif)}
                  className={`w-full text-right px-3 py-2.5 border-b border-slate-50 hover:bg-slate-50 transition-colors flex items-start gap-2.5 ${
                    !notif.read ? 'bg-amber-50/50' : ''
                  }`}
                >
                  <div className={`mt-0.5 flex-shrink-0 ${actionCfg.color}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-[11px] leading-relaxed ${!notif.read ? 'font-medium text-slate-800' : 'text-slate-600'}`}>
                      {notif.body}
                    </p>
                    <p className="text-[9px] text-slate-400 mt-0.5">{formatTimeAgo(notif.created_at)}</p>
                  </div>
                  {!notif.read && (
                    <div className="w-2 h-2 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
                  )}
                </button>
              );
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
