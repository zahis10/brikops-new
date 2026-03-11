import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { projectService, projectPlanService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { t } from '../i18n';
import {
  ArrowRight, Loader2, FileText, Download, Eye,
  Calendar, User, AlertCircle, Clock
} from 'lucide-react';

const ProjectPlanHistoryPage = () => {
  const { projectId, planId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [project, setProject] = useState(null);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const loadProject = useCallback(async () => {
    try {
      const data = await projectService.get(projectId);
      setProject(data);
    } catch (err) {
      if (err?.response?.status === 403) {
        setLoadError('forbidden');
      }
    }
  }, [projectId]);

  const loadHistory = useCallback(async () => {
    try {
      setLoading(true);
      const data = await projectPlanService.history(projectId, planId);
      setVersions(Array.isArray(data?.versions) ? data.versions : []);
    } catch (err) {
      if (err?.response?.status === 404) {
        setLoadError('not_found');
      } else if (err?.response?.status === 403) {
        setLoadError('forbidden');
      } else {
        toast.error('שגיאה בטעינת היסטוריית תוכנית');
        setLoadError('error');
      }
    } finally {
      setLoading(false);
    }
  }, [projectId, planId]);

  useEffect(() => { loadProject(); loadHistory(); }, [loadProject, loadHistory]);

  const getDisciplineLabel = (key) => {
    const fromI18n = t('unitPlans', 'disciplines')?.[key];
    return fromI18n || key;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch { return dateStr; }
  };

  const formatDateTime = (dateStr) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString('he-IL', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch { return dateStr; }
  };

  const currentVersion = versions.length > 0 ? versions[0] : null;
  const previousVersions = versions.slice(1);

  const headerBlock = (
    <div className="bg-slate-800 text-white sticky top-0 z-30">
      <div className="max-w-2xl mx-auto px-4 py-3">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => navigate(`/projects/${projectId}/plans`)}
            className="p-1.5 hover:bg-slate-700 rounded-lg transition-colors flex-shrink-0"
          >
            <ArrowRight className="w-5 h-5" />
          </button>
          <div className="min-w-0">
            <h1 className="text-base font-bold flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-400" />
              היסטוריית תוכנית
            </h1>
            {project?.name && (
              <p className="text-[11px] text-slate-400 truncate">{project.name}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50" dir="rtl">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="min-h-screen bg-slate-50" dir="rtl">
        {headerBlock}
        <div className="max-w-2xl mx-auto px-4 py-12 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          {loadError === 'forbidden' ? (
            <p className="text-slate-600 font-medium">אין הרשאה לצפייה בתוכנית</p>
          ) : loadError === 'not_found' ? (
            <p className="text-slate-600 font-medium">תוכנית לא נמצאה</p>
          ) : (
            <>
              <p className="text-slate-600 font-medium mb-4">לא הצלחנו לטעון את היסטוריית התוכנית</p>
              <button
                onClick={() => { setLoadError(null); setLoading(true); loadHistory(); }}
                className="px-4 py-2.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl font-bold text-sm shadow-sm transition-colors"
              >
                נסה שוב
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      {headerBlock}

      <div className="max-w-2xl mx-auto px-4 py-4 space-y-4">
        {currentVersion && (
          <div className="space-y-2">
            <p className="text-[11px] text-slate-400 px-1 font-medium">
              {versions.length} {versions.length === 1 ? 'גרסה' : 'גרסאות'}
              {currentVersion.discipline && ` · ${getDisciplineLabel(currentVersion.discipline)}`}
            </p>

            <div className="relative">
              <div className="absolute right-[19px] top-[52px] bottom-0 w-px bg-slate-200" style={{ display: previousVersions.length > 0 ? 'block' : 'none' }} />

              <div className="relative flex gap-3">
                <div className="flex flex-col items-center flex-shrink-0 z-10">
                  <div className="w-[10px] h-[10px] rounded-full bg-amber-500 mt-[14px] ring-2 ring-white" />
                </div>
                <div className="flex-1 bg-white rounded-xl border-2 border-amber-200 px-4 py-3 shadow-sm">
                  <div className="flex items-start gap-2.5">
                    <div className="w-8 h-8 bg-amber-50 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                      <FileText className="w-4 h-4 text-amber-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500 text-white font-bold">
                          נוכחית
                        </span>
                      </div>
                      <h3 className="text-[13px] font-bold text-slate-800 leading-snug break-words line-clamp-2">
                        {currentVersion.original_filename || currentVersion.file_url}
                      </h3>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
                          {getDisciplineLabel(currentVersion.discipline)}
                        </span>
                        {currentVersion.uploaded_by_name && (
                          <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                            <User className="w-3 h-3" />
                            {currentVersion.uploaded_by_name}
                          </span>
                        )}
                        <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                          <Calendar className="w-3 h-3" />
                          {formatDateTime(currentVersion.created_at)}
                        </span>
                      </div>
                      {currentVersion.note && (
                        <p className="text-xs text-slate-500 mt-1.5">{currentVersion.note}</p>
                      )}
                    </div>
                    <div className="flex gap-0.5 flex-shrink-0">
                      <a
                        href={currentVersion.file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                        title="צפה"
                      >
                        <Eye className="w-3.5 h-3.5 text-slate-400" />
                      </a>
                      <a
                        href={currentVersion.file_url}
                        download
                        className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                        title="הורד"
                      >
                        <Download className="w-3.5 h-3.5 text-slate-400" />
                      </a>
                    </div>
                  </div>
                </div>
              </div>

              {previousVersions.map((version, idx) => (
                <div key={version.id} className="relative flex gap-3 mt-3">
                  <div className="flex flex-col items-center flex-shrink-0 z-10">
                    <div className="w-[10px] h-[10px] rounded-full bg-slate-300 mt-[14px] ring-2 ring-white" />
                    {idx < previousVersions.length - 1 && (
                      <div className="w-px flex-1 bg-slate-200" />
                    )}
                  </div>
                  <div className="flex-1 bg-white rounded-xl border border-slate-200 px-4 py-3 opacity-85">
                    <div className="flex items-start gap-2.5">
                      <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                        <FileText className="w-4 h-4 text-slate-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 font-medium">
                            הוחלפה
                          </span>
                          <span className="text-[10px] text-slate-300 font-medium">
                            גרסה {versions.length - idx - 1}
                          </span>
                        </div>
                        <h3 className="text-[13px] font-bold text-slate-600 leading-snug break-words line-clamp-2">
                          {version.original_filename || version.file_url}
                        </h3>
                        <div className="flex items-center gap-2 mt-1 flex-wrap">
                          {version.uploaded_by_name && (
                            <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                              <User className="w-3 h-3" />
                              {version.uploaded_by_name}
                            </span>
                          )}
                          <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                            <Calendar className="w-3 h-3" />
                            הועלה: {formatDate(version.created_at)}
                          </span>
                          {version.archived_at && (
                            <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                              <Clock className="w-3 h-3" />
                              הוחלפה: {formatDate(version.archived_at)}
                            </span>
                          )}
                        </div>
                        {version.note && (
                          <p className="text-xs text-slate-400 mt-1">{version.note}</p>
                        )}
                      </div>
                      <div className="flex gap-0.5 flex-shrink-0">
                        <a
                          href={version.file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                          title="צפה"
                        >
                          <Eye className="w-3.5 h-3.5 text-slate-400" />
                        </a>
                        <a
                          href={version.file_url}
                          download
                          className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                          title="הורד"
                        >
                          <Download className="w-3.5 h-3.5 text-slate-400" />
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {!currentVersion && (
          <div className="py-12 text-center">
            <Clock className="w-10 h-10 text-slate-200 mx-auto mb-2" />
            <p className="text-sm text-slate-400">לא נמצאה היסטוריה לתוכנית זו</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProjectPlanHistoryPage;
