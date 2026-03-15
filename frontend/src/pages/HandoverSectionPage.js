import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { t } from '../i18n';
import { ArrowRight, Construction } from 'lucide-react';

const HandoverSectionPage = () => {
  const { projectId, unitId, protocolId, sectionId } = useParams();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50" dir="rtl">
      <div className="bg-gradient-to-l from-purple-600 to-purple-700 text-white">
        <div className="max-w-lg mx-auto px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/projects/${projectId}/units/${unitId}/handover/${protocolId}`)}
              className="p-1.5 hover:bg-white/20 rounded-lg transition-colors"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-bold">{t('handover', 'backToProtocol')}</h1>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 mt-12 text-center space-y-4">
        <div className="w-16 h-16 bg-purple-100 rounded-2xl flex items-center justify-center mx-auto">
          <Construction className="w-8 h-8 text-purple-500" />
        </div>
        <p className="text-slate-500 text-sm">{t('handover', 'sectionPlaceholder')}</p>
      </div>
    </div>
  );
};

export default HandoverSectionPage;
