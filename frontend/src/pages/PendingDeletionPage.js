import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { deletionService } from '../services/api';
import { toast } from 'sonner';
import { Loader2, AlertTriangle, Clock, XCircle } from 'lucide-react';
import { Button } from '../components/ui/button';

const PendingDeletionPage = () => {
  const { user, logout, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    if (!user) {
      navigate('/login', { replace: true });
      return;
    }
    if (user.user_status !== 'pending_deletion') {
      navigate('/projects', { replace: true });
      return;
    }
    deletionService.getStatus()
      .then(data => {
        setStatus(data);
        if (!data.pending) {
          navigate('/projects', { replace: true });
        }
      })
      .catch(err => {
        const httpStatus = err.response?.status;
        if (httpStatus === 401 || httpStatus === 403) {
          logout();
          navigate('/login', { replace: true });
        } else {
          navigate('/projects', { replace: true });
        }
      })
      .finally(() => setLoading(false));
  }, [navigate, user, logout]);

  const getDaysRemaining = () => {
    if (!status?.scheduled_for) return null;
    const scheduled = new Date(status.scheduled_for);
    const now = new Date();
    const diff = Math.ceil((scheduled - now) / (1000 * 60 * 60 * 24));
    return Math.max(0, diff);
  };

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await deletionService.cancelDeletion();
      toast.success('המחיקה בוטלה בהצלחה');
      if (refreshUser) {
        await refreshUser();
      }
      navigate('/projects', { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'object' ? detail.message : detail;
      toast.error(msg || 'שגיאה בביטול המחיקה');
    } finally {
      setCancelling(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  const daysRemaining = getDaysRemaining();
  const deletionType = status?.deletion_type;

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-slate-50 flex items-center justify-center px-4 py-8" dir="rtl">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-3">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
            <AlertTriangle className="w-8 h-8 text-red-500" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">החשבון שלך בתהליך מחיקה</h1>
          <p className="text-slate-600">
            {deletionType === 'full_purge'
              ? 'החשבון והארגון שלך מתוכננים למחיקה מלאה.'
              : 'החשבון שלך מתוכנן למחיקה.'}
          </p>
        </div>

        {daysRemaining !== null && (
          <div className="bg-white rounded-2xl shadow-lg border border-red-200 p-6 text-center space-y-2">
            <Clock className="w-6 h-6 text-red-500 mx-auto" />
            <p className="text-4xl font-black text-red-600">{daysRemaining}</p>
            <p className="text-sm text-slate-600">ימים נותרו לפני מחיקה סופית</p>
          </div>
        )}

        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-6 space-y-3">
          <h2 className="font-semibold text-slate-900">מה יקרה?</h2>
          <ul className="space-y-2 text-sm text-slate-600">
            <li className="flex items-start gap-2">
              <XCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
              <span>כל הנתונים האישיים שלך יימחקו לצמיתות</span>
            </li>
            <li className="flex items-start gap-2">
              <XCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
              <span>לא תוכל לגשת לחשבון שלך יותר</span>
            </li>
            {deletionType === 'full_purge' && (
              <>
                <li className="flex items-start gap-2">
                  <XCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                  <span>כל הפרויקטים, המשימות והנתונים של הארגון יימחקו</span>
                </li>
                <li className="flex items-start gap-2">
                  <XCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                  <span>כל חברי הארגון יאבדו את הגישה שלהם</span>
                </li>
              </>
            )}
          </ul>
          <p className="text-xs text-slate-400 pt-2">
            ניתן לבטל את המחיקה בכל עת לפני תום תקופת ההמתנה.
          </p>
        </div>

        <div className="space-y-3">
          <Button
            onClick={handleCancel}
            disabled={cancelling}
            className="w-full h-12 bg-amber-500 hover:bg-amber-600 text-white font-bold text-base rounded-xl shadow-lg"
          >
            {cancelling ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                מבטל...
              </span>
            ) : 'בטל מחיקה'}
          </Button>

          <button
            onClick={handleLogout}
            className="w-full text-center text-sm text-slate-500 hover:text-slate-700 py-2"
          >
            התנתק
          </button>
        </div>
      </div>
    </div>
  );
};

export default PendingDeletionPage;
