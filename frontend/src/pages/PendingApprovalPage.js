import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Clock, LogOut } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';

const PendingApprovalPage = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/phone-login');
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)' }}>
      <Card className="w-full max-w-md p-8 bg-white shadow-2xl rounded-2xl text-center" dir="rtl">
        <div className="flex flex-col items-center">
          <img src="/logo-orange.png" alt="BrikOps" style={{ height: 48, marginBottom: 16 }} />

          <div className="w-12 h-12 bg-amber-50 rounded-full flex items-center justify-center mb-4">
            <Clock className="w-6 h-6 text-amber-500" />
          </div>

          <h1 className="text-2xl font-bold text-slate-900 mb-2" style={{ fontFamily: 'Rubik, sans-serif' }}>
            ממתין לאישור מנהל הפרויקט
          </h1>

          <p className="text-slate-500 text-sm mb-8">
            החלטה תתקבל בקרוב
          </p>

          <div className="w-full p-4 bg-amber-50 rounded-xl border border-amber-200 mb-6">
            <p className="text-sm text-amber-700">
              הבקשה שלך נשלחה בהצלחה. מנהל הפרויקט יבדוק ויאשר את הבקשה בהקדם.
            </p>
          </div>

          <Button
            onClick={handleLogout}
            variant="outline"
            className="w-full h-11 text-sm font-medium border-slate-300 text-slate-600 hover:bg-slate-50"
          >
            <LogOut className="w-4 h-4 ml-2" />
            התנתק
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default PendingApprovalPage;
