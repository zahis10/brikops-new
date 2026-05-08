import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { onboardingService, companyService, projectService } from '../services/api';
import { toast } from 'sonner';
import { Loader2, Users, Wrench } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { t } from '../i18n';

const RegisterPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const phoneFromState = location.state?.phone || '';

  const [track, setTrack] = useState('');
  const [roles, setRoles] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(false);
  const [rolesLoading, setRolesLoading] = useState(false);
  // 2026-05-08 — ToS consent (Israeli Spam Law). MANDATORY.
  const [termsAccepted, setTermsAccepted] = useState(false);

  const detectLanguage = () => {
    const lang = (navigator.language || '').toLowerCase();
    if (lang.startsWith('ar')) return 'ar';
    if (lang.startsWith('zh')) return 'zh';
    if (lang.startsWith('en')) return 'en';
    return 'he';
  };

  const [formData, setFormData] = useState({
    full_name: '',
    phone_e164: phoneFromState,
    track: '',
    role: '',
    company_id: '',
    project_id: '',
  });

  useEffect(() => {
    const loadProjects = async () => {
      try {
        const data = await projectService.list();
        setProjects(Array.isArray(data) ? data : data.projects || []);
      } catch (err) {
        console.error('Failed to load projects:', err);
      }
    };
    loadProjects();
  }, []);

  useEffect(() => {
    if (!track) {
      setRoles([]);
      return;
    }
    const loadRoles = async () => {
      setRolesLoading(true);
      try {
        let data;
        if (track === 'management') {
          data = await onboardingService.getManagementRoles();
        } else {
          data = await onboardingService.getSubcontractorRoles();
        }
        setRoles(Array.isArray(data) ? data : data.roles || []);
      } catch (err) {
        console.error('Failed to load roles:', err);
        setRoles([]);
      } finally {
        setRolesLoading(false);
      }
    };
    loadRoles();
  }, [track]);

  useEffect(() => {
    if (track === 'subcontractor') {
      const loadCompanies = async () => {
        try {
          const data = await companyService.list();
          setCompanies(Array.isArray(data) ? data : data.companies || []);
        } catch (err) {
          console.error('Failed to load companies:', err);
        }
      };
      loadCompanies();
    }
  }, [track]);

  const handleTrackSelect = (selectedTrack) => {
    setTrack(selectedTrack);
    setFormData(prev => ({ ...prev, track: selectedTrack, role: '', company_id: '' }));
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.full_name.trim()) {
      toast.error(t('register', 'err_name_required'));
      return;
    }
    if (!formData.track) {
      toast.error(t('register', 'err_track_required'));
      return;
    }
    if (!formData.role) {
      toast.error(t('register', 'err_role_required'));
      return;
    }
    if (!formData.project_id) {
      toast.error(t('register', 'err_project_required'));
      return;
    }
    if (track === 'subcontractor' && !formData.company_id) {
      toast.error(t('register', 'err_company_required'));
      return;
    }

    // 2026-05-08 — ToS consent gate (Israeli Spam Law).
    if (!termsAccepted) {
      toast.error('יש לאשר את תנאי השימוש');
      return;
    }
    setLoading(true);
    try {
      const payload = {
        full_name: formData.full_name,
        phone_e164: formData.phone_e164,
        track: formData.track,
        role: formData.role,
        project_id: formData.project_id,
        preferred_language: detectLanguage(),
        terms_accepted: termsAccepted,
      };
      if (track === 'subcontractor' && formData.company_id) {
        payload.company_id = formData.company_id;
      }

      await onboardingService.registerWithPhone(payload);
      toast.success(t('register', 'toast_registered'));
      navigate('/pending');
    } catch (error) {
      toast.error(error.response?.data?.detail || t('register', 'err_register'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #334155 50%, #475569 100%)' }}>
      <Card className="w-full max-w-md p-8 bg-white shadow-2xl rounded-2xl relative z-10">
        <div className="flex flex-col items-center mb-8">
          <img src="/logo-orange.png" alt="BrikOps" style={{ height: 48, marginBottom: 8 }} />
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Rubik, sans-serif' }}>
            {t('register', 'title')}
          </h1>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" dir="rtl">
          <div className="space-y-2">
            <label htmlFor="phone_display" className="block text-sm font-medium text-slate-700">
              {t('register', 'phone_label')}
            </label>
            <input
              id="phone_display"
              type="text"
              value={formData.phone_e164}
              readOnly
              className="w-full h-11 px-3 py-2 text-right text-slate-500 bg-slate-50 border border-slate-200 rounded-lg cursor-not-allowed"
              dir="ltr"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="full_name" className="block text-sm font-medium text-slate-700">
              {t('register', 'full_name')}
              <span className="text-red-500 mr-1">*</span>
            </label>
            <input
              id="full_name"
              name="full_name"
              type="text"
              value={formData.full_name}
              onChange={handleChange}
              placeholder={t('register', 'full_name_placeholder')}
              className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
            />
          </div>

          <div className="space-y-2">
            <span className="block text-sm font-medium text-slate-700">
              {t('register', 'track')}
              <span className="text-red-500 mr-1">*</span>
            </span>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => handleTrackSelect('management')}
                className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all touch-manipulation ${
                  track === 'management'
                    ? 'border-amber-500 bg-amber-50 text-amber-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                <Users className="w-6 h-6" />
                <span className="text-sm font-medium">{t('register', 'management')}</span>
              </button>
              <button
                type="button"
                onClick={() => handleTrackSelect('subcontractor')}
                className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all touch-manipulation ${
                  track === 'subcontractor'
                    ? 'border-amber-500 bg-amber-50 text-amber-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                <Wrench className="w-6 h-6" />
                <span className="text-sm font-medium">{t('register', 'subcontractor')}</span>
              </button>
            </div>
          </div>

          {track && (
            <div className="space-y-2">
              <label htmlFor="role" className="block text-sm font-medium text-slate-700">
                {t('register', 'role_label')}
                <span className="text-red-500 mr-1">*</span>
              </label>
              {rolesLoading ? (
                <div className="flex items-center justify-center h-11">
                  <Loader2 className="w-5 h-5 animate-spin text-amber-500" />
                </div>
              ) : (
                <select
                  id="role"
                  name="role"
                  value={formData.role}
                  onChange={handleChange}
                  className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
                >
                  <option value="">{t('register', 'select_role')}</option>
                  {roles.map((role) => (
                    <option key={role.value || role.id || role} value={role.value || role.id || role}>
                      {role.label || role.name || role}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {track === 'subcontractor' && (
            <div className="space-y-2">
              <label htmlFor="company_id" className="block text-sm font-medium text-slate-700">
                {t('register', 'company_label')}
                <span className="text-red-500 mr-1">*</span>
              </label>
              <select
                id="company_id"
                name="company_id"
                value={formData.company_id}
                onChange={handleChange}
                className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
              >
                <option value="">{t('register', 'select_company')}</option>
                {companies.map((company) => (
                  <option key={company._id || company.id} value={company._id || company.id}>
                    {company.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="space-y-2">
            <label htmlFor="project_id" className="block text-sm font-medium text-slate-700">
              {t('register', 'project_label')}
              <span className="text-red-500 mr-1">*</span>
            </label>
            <select
              id="project_id"
              name="project_id"
              value={formData.project_id}
              onChange={handleChange}
              className="w-full h-11 px-3 py-2 text-right text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
            >
              <option value="">{t('register', 'select_project')}</option>
              {projects.map((project) => (
                <option key={project._id || project.id} value={project._id || project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>

          {/* 2026-05-08 — ToS consent (Israeli Spam Law). MANDATORY. */}
          <div className="flex items-start gap-2 pt-2">
            <input
              id="reg-terms"
              type="checkbox"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
              className="mt-1 h-4 w-4 text-amber-500 border-slate-300 rounded focus:ring-amber-500"
            />
            <label htmlFor="reg-terms" className="text-xs text-slate-700">
              אני מאשר/ת את <a href="/legal/terms.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">תנאי השימוש</a> ואת <a href="/legal/privacy.html" target="_blank" rel="noopener noreferrer" className="text-amber-600 hover:text-amber-700 underline">מדיניות הפרטיות</a>
            </label>
          </div>

          <Button
            type="submit"
            className="w-full h-12 text-base font-medium mt-6 touch-manipulation bg-amber-500 hover:bg-amber-600 text-white"
            disabled={loading}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                {t('register', 'submitting')}
              </span>
            ) : (
              t('register', 'submit')

            )}
          </Button>
        </form>
      </Card>
    </div>
  );
};

export default RegisterPage;
