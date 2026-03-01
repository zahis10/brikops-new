import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { projectService } from '../services/api';
import { ChevronDown, FolderOpen } from 'lucide-react';
import { navigateToProject } from '../utils/navigation';

const normalizeList = (data) => {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  if (data && typeof data === 'object') {
    const arrKey = Object.keys(data).find(k => Array.isArray(data[k]));
    if (arrKey) return data[arrKey];
  }
  return [];
};

export default function ProjectSwitcher({ currentProjectId, currentProjectName }) {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    projectService.list()
      .then(data => setProjects(normalizeList(data)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const otherProjects = projects.filter(p => p.id !== currentProjectId && p._id !== currentProjectId);
  const showSwitcher = otherProjects.length > 0;

  const handleSelect = (project) => {
    setOpen(false);
    navigateToProject(project, navigate);
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => showSwitcher && setOpen(!open)}
        className={`flex items-center gap-1.5 min-w-0 ${showSwitcher ? 'cursor-pointer hover:bg-slate-700/50 rounded-lg px-2 py-1 -mx-2 -my-1 transition-colors' : ''}`}
        disabled={!showSwitcher}
      >
        <h1 className="text-lg font-bold leading-tight truncate">{currentProjectName}</h1>
        {showSwitcher && <ChevronDown className={`w-4 h-4 flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />}
      </button>

      {open && (
        <div className="absolute top-full mt-2 right-0 w-64 bg-white rounded-xl shadow-xl border border-slate-200 py-1 z-[100] max-h-72 overflow-y-auto">
          <div className="px-3 py-2 text-xs font-medium text-slate-400 border-b border-slate-100">
            החלפת פרויקט
          </div>
          {otherProjects.map(p => {
            const pid = p.id || p._id;
            return (
              <button
                key={pid}
                onClick={() => handleSelect(p)}
                className="w-full text-right px-3 py-2.5 hover:bg-amber-50 transition-colors flex items-center gap-2"
              >
                <FolderOpen className="w-4 h-4 text-slate-400 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-slate-700 truncate">{p.name}</div>
                  {p.code && <div className="text-xs text-slate-400">{p.code}</div>}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
