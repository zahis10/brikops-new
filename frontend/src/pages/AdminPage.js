import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { projectService, buildingService, floorService, companyService, userService, BACKEND_URL } from '../services/api';
import { toast } from 'sonner';
import { formatUnitLabel } from '../utils/formatters';
import {
  HardHat, LogOut, Building2, Layers, DoorOpen, Users, Plus, ChevronDown, ChevronUp,
  Loader2, ArrowRight, Briefcase, FolderOpen, RefreshCw, UserPlus, ChevronRight,
  Server, Database, Shield
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';

const CATEGORIES = [
  { value: 'electrical', label: 'חשמל' },
  { value: 'plumbing', label: 'אינסטלציה' },
  { value: 'hvac', label: 'מיזוג' },
  { value: 'painting', label: 'צביעה' },
  { value: 'flooring', label: 'ריצוף' },
  { value: 'carpentry', label: 'נגרות' },
  { value: 'masonry', label: 'בנייה' },
  { value: 'windows', label: 'חלונות' },
  { value: 'doors', label: 'דלתות' },
  { value: 'general', label: 'כללי' },
];

const normalizeList = (data) => {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.items)) return data.items;
  if (data && Array.isArray(data.projects)) return data.projects;
  if (data && Array.isArray(data.buildings)) return data.buildings;
  if (data && Array.isArray(data.floors)) return data.floors;
  if (data && Array.isArray(data.units)) return data.units;
  if (data && Array.isArray(data.companies)) return data.companies;
  return [];
};

const SectionHeader = ({ icon: Icon, title, isOpen, onToggle, count }) => (
  <button
    onClick={onToggle}
    className="w-full flex items-center justify-between p-4 bg-slate-50 rounded-xl hover:bg-slate-100 transition-colors touch-manipulation"
    dir="rtl"
  >
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
        <Icon className="w-5 h-5 text-amber-600" />
      </div>
      <div className="text-right">
        <h3 className="text-base font-semibold text-slate-800">{title}</h3>
        {count !== undefined && <p className="text-xs text-slate-500">{count} פריטים</p>}
      </div>
    </div>
    {isOpen ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
  </button>
);

const InputField = ({ label, value, onChange, placeholder, required, type = 'text' }) => (
  <div className="space-y-1" dir="rtl">
    <label className="block text-sm font-medium text-slate-700">
      {label} {required && <span className="text-red-500">*</span>}
    </label>
    <input
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className="w-full h-10 px-3 py-2 text-right text-sm text-slate-900 bg-white border border-slate-300 rounded-lg hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 placeholder:text-slate-400"
    />
  </div>
);

const AdminPage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [buildings, setBuildings] = useState([]);
  const [selectedBuilding, setSelectedBuilding] = useState(null);
  const [floors, setFloors] = useState([]);
  const [selectedFloor, setSelectedFloor] = useState(null);
  const [units, setUnits] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState({});
  const [openSections, setOpenSections] = useState({ projects: true });
  const [openProjects, setOpenProjects] = useState({});

  const [newProject, setNewProject] = useState({ name: '', code: '', description: '', client_name: '' });
  const [newBuilding, setNewBuilding] = useState({ name: '', code: '' });
  const [newFloor, setNewFloor] = useState({ name: '', floor_number: '' });
  const [newUnit, setNewUnit] = useState({ unit_no: '', unit_type: 'apartment' });
  const [newCompany, setNewCompany] = useState({ name: '', trade: '', contact_name: '', contact_phone: '' });
  const [pmAssignment, setPmAssignment] = useState({ user_id: '' });

  const [showForm, setShowForm] = useState({});
  const [systemInfo, setSystemInfo] = useState(null);
  const [systemInfoLoading, setSystemInfoLoading] = useState(false);

  const loadSystemInfo = useCallback(async () => {
    setSystemInfoLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${BACKEND_URL}/api/admin/system-info`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setSystemInfo(await res.json());
      }
    } catch (err) {
      // silently fail for non-super-admins
    } finally {
      setSystemInfoLoading(false);
    }
  }, []);

  const toggleSection = (section) => {
    setOpenSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const toggleForm = (form) => {
    setShowForm(prev => ({ ...prev, [form]: !prev[form] }));
  };

  const toggleProject = (project) => {
    const projectId = project.id;
    const isCurrentlyOpen = openProjects[projectId];
    if (!isCurrentlyOpen) {
      selectProject(project);
    }
    setOpenProjects(prev => ({ ...prev, [projectId]: !prev[projectId] }));
  };

  const loadProjects = useCallback(async () => {
    setLoading(l => ({ ...l, projects: true }));
    try {
      const data = await projectService.list();
      setProjects(normalizeList(data));
    } catch (err) {
      toast.error('שגיאה בטעינת פרויקטים');
    } finally {
      setLoading(l => ({ ...l, projects: false }));
    }
  }, []);

  const loadBuildings = useCallback(async (projectId) => {
    setLoading(l => ({ ...l, buildings: true }));
    try {
      const data = await projectService.getBuildings(projectId);
      setBuildings(normalizeList(data));
    } catch (err) {
      toast.error('שגיאה בטעינת בניינים');
    } finally {
      setLoading(l => ({ ...l, buildings: false }));
    }
  }, []);

  const loadFloors = useCallback(async (buildingId) => {
    setLoading(l => ({ ...l, floors: true }));
    try {
      const data = await buildingService.getFloors(buildingId);
      setFloors(normalizeList(data));
    } catch (err) {
      toast.error('שגיאה בטעינת קומות');
    } finally {
      setLoading(l => ({ ...l, floors: false }));
    }
  }, []);

  const loadUnits = useCallback(async (floorId) => {
    setLoading(l => ({ ...l, units: true }));
    try {
      const data = await floorService.getUnits(floorId);
      setUnits(normalizeList(data));
    } catch (err) {
      toast.error('שגיאה בטעינת דירות');
    } finally {
      setLoading(l => ({ ...l, units: false }));
    }
  }, []);

  const loadCompanies = useCallback(async () => {
    setLoading(l => ({ ...l, companies: true }));
    try {
      const data = await companyService.list();
      setCompanies(normalizeList(data));
    } catch (err) {
      toast.error('שגיאה בטעינת חברות');
    } finally {
      setLoading(l => ({ ...l, companies: false }));
    }
  }, []);

  const loadUsers = useCallback(async () => {
    setLoading(l => ({ ...l, users: true }));
    try {
      const data = await userService.list();
      setUsers(normalizeList(data));
    } catch (err) {
      toast.error('שגיאה בטעינת משתמשים');
    } finally {
      setLoading(l => ({ ...l, users: false }));
    }
  }, []);

  useEffect(() => {
    loadProjects();
    loadCompanies();
    loadUsers();
    loadSystemInfo();
  }, [loadProjects, loadCompanies, loadUsers, loadSystemInfo]);

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!newProject.name.trim() || !newProject.code.trim()) {
      toast.error('שם וקוד פרויקט הם שדות חובה');
      return;
    }
    setLoading(l => ({ ...l, createProject: true }));
    try {
      await projectService.create(newProject);
      toast.success('פרויקט נוצר בהצלחה!');
      setNewProject({ name: '', code: '', description: '', client_name: '' });
      setShowForm(f => ({ ...f, project: false }));
      loadProjects();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת פרויקט');
    } finally {
      setLoading(l => ({ ...l, createProject: false }));
    }
  };

  const handleCreateBuilding = async (e) => {
    e.preventDefault();
    if (!newBuilding.name.trim() || !selectedProject) {
      toast.error('יש לבחור פרויקט ולהזין שם בניין');
      return;
    }
    setLoading(l => ({ ...l, createBuilding: true }));
    try {
      await projectService.createBuilding(selectedProject.id, {
        ...newBuilding,
        project_id: selectedProject.id,
      });
      toast.success('בניין נוצר בהצלחה!');
      setNewBuilding({ name: '', code: '' });
      setShowForm(f => ({ ...f, building: false }));
      loadBuildings(selectedProject.id);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת בניין');
    } finally {
      setLoading(l => ({ ...l, createBuilding: false }));
    }
  };

  const handleCreateFloor = async (e) => {
    e.preventDefault();
    if (!newFloor.name.trim() || !selectedBuilding) {
      toast.error('יש לבחור בניין ולהזין שם קומה');
      return;
    }
    setLoading(l => ({ ...l, createFloor: true }));
    try {
      await buildingService.createFloor(selectedBuilding.id, {
        ...newFloor,
        building_id: selectedBuilding.id,
        project_id: selectedProject.id,
        floor_number: parseInt(newFloor.floor_number) || 0,
      });
      toast.success('קומה נוצרה בהצלחה!');
      setNewFloor({ name: '', floor_number: '' });
      setShowForm(f => ({ ...f, floor: false }));
      loadFloors(selectedBuilding.id);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת קומה');
    } finally {
      setLoading(l => ({ ...l, createFloor: false }));
    }
  };

  const handleCreateUnit = async (e) => {
    e.preventDefault();
    if (!newUnit.unit_no.trim() || !selectedFloor) {
      toast.error('יש לבחור קומה ולהזין מספר יחידה');
      return;
    }
    setLoading(l => ({ ...l, createUnit: true }));
    try {
      await floorService.createUnit(selectedFloor.id, {
        ...newUnit,
        floor_id: selectedFloor.id,
        building_id: selectedBuilding.id,
        project_id: selectedProject.id,
      });
      toast.success('יחידה נוצרה בהצלחה!');
      setNewUnit({ unit_no: '', unit_type: 'apartment' });
      setShowForm(f => ({ ...f, unit: false }));
      loadUnits(selectedFloor.id);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת יחידה');
    } finally {
      setLoading(l => ({ ...l, createUnit: false }));
    }
  };

  const handleCreateCompany = async (e) => {
    e.preventDefault();
    if (!newCompany.name.trim()) {
      toast.error('שם חברה הוא שדה חובה');
      return;
    }
    setLoading(l => ({ ...l, createCompany: true }));
    try {
      const payload = { ...newCompany };
      if (payload.trade) {
        payload.specialties = [payload.trade];
      }
      await companyService.create(payload);
      toast.success('חברה נוצרה בהצלחה!');
      setNewCompany({ name: '', trade: '', contact_name: '', contact_phone: '' });
      setShowForm(f => ({ ...f, company: false }));
      loadCompanies();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה ביצירת חברה');
    } finally {
      setLoading(l => ({ ...l, createCompany: false }));
    }
  };

  const handleAssignPM = async (e) => {
    e.preventDefault();
    if (!pmAssignment.user_id || !selectedProject) {
      toast.error('יש לבחור פרויקט ומשתמש');
      return;
    }
    setLoading(l => ({ ...l, assignPM: true }));
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${BACKEND_URL}/api/projects/${selectedProject.id}/assign-pm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ user_id: pmAssignment.user_id }),
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'שגיאה');
      }
      toast.success('מנהל פרויקט מונה בהצלחה!');
      setPmAssignment({ user_id: '' });
      setShowForm(f => ({ ...f, pm: false }));
      loadUsers();
    } catch (err) {
      toast.error(err.message || 'שגיאה במינוי מנהל פרויקט');
    } finally {
      setLoading(l => ({ ...l, assignPM: false }));
    }
  };

  const selectProject = (project) => {
    setSelectedProject(project);
    setSelectedBuilding(null);
    setSelectedFloor(null);
    setBuildings([]);
    setFloors([]);
    setUnits([]);
    loadBuildings(project.id);
    setOpenSections(prev => ({ ...prev, buildings: true }));
  };

  const selectBuilding = (building) => {
    setSelectedBuilding(building);
    setSelectedFloor(null);
    setFloors([]);
    setUnits([]);
    loadFloors(building.id);
    setOpenSections(prev => ({ ...prev, floors: true }));
  };

  const selectFloor = (floor) => {
    setSelectedFloor(floor);
    setUnits([]);
    loadUnits(floor.id);
    setOpenSections(prev => ({ ...prev, units: true }));
  };

  const pmCandidates = users.filter(u =>
    u.role === 'project_manager'
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-slate-800 text-white shadow-lg sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-amber-500 rounded-lg flex items-center justify-center">
              <HardHat className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold leading-tight">ניהול מערכת</h1>
              <p className="text-xs text-slate-400">{user?.name} • בעלים</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => navigate('/projects')} className="text-slate-300 hover:text-white hover:bg-slate-700">
              <ArrowRight className="w-4 h-4 ml-1" />
              חזרה
            </Button>
            <Button variant="ghost" size="sm" onClick={() => { logout(); navigate('/login'); }} className="text-slate-300 hover:text-white hover:bg-slate-700">
              <LogOut className="w-4 h-4 ml-1" />
              יציאה
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-4 space-y-4">

        {systemInfo && (
          <Card className="overflow-hidden">
            <div className="p-4 bg-slate-50 rounded-xl" dir="rtl">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Server className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-800">מידע מערכת</h3>
                  <p className="text-xs text-slate-500">System Info</p>
                </div>
                <Button variant="ghost" size="sm" onClick={loadSystemInfo} className="mr-auto" disabled={systemInfoLoading}>
                  <RefreshCw className={`w-4 h-4 ${systemInfoLoading ? 'animate-spin' : ''}`} />
                </Button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                <div className="bg-white rounded-lg p-3 border border-slate-200">
                  <div className="flex items-center gap-2 mb-1">
                    <Database className="w-4 h-4 text-blue-500" />
                    <span className="text-xs font-medium text-slate-500">DB Host</span>
                  </div>
                  <p className="text-sm font-semibold text-slate-800 break-all">{systemInfo.db_host}</p>
                </div>
                <div className="bg-white rounded-lg p-3 border border-slate-200">
                  <div className="flex items-center gap-2 mb-1">
                    <Database className="w-4 h-4 text-green-500" />
                    <span className="text-xs font-medium text-slate-500">DB Name</span>
                  </div>
                  <p className="text-sm font-semibold text-slate-800">{systemInfo.db_name}</p>
                </div>
                <div className="bg-white rounded-lg p-3 border border-slate-200">
                  <div className="flex items-center gap-2 mb-1">
                    <Shield className="w-4 h-4 text-amber-500" />
                    <span className="text-xs font-medium text-slate-500">App Mode</span>
                  </div>
                  <p className={`text-sm font-semibold ${systemInfo.app_mode === 'prod' ? 'text-red-600' : 'text-green-600'}`}>
                    {systemInfo.app_mode}
                  </p>
                </div>
                <div className="bg-white rounded-lg p-3 border border-slate-200">
                  <div className="flex items-center gap-2 mb-1">
                    <Server className="w-4 h-4 text-slate-500" />
                    <span className="text-xs font-medium text-slate-500">Git SHA</span>
                  </div>
                  <p className="text-sm font-mono font-semibold text-slate-800">{systemInfo.git_sha}</p>
                </div>
              </div>
              {systemInfo.counts && (
                <div className="mt-3 grid grid-cols-3 sm:grid-cols-5 gap-2">
                  {Object.entries(systemInfo.counts).map(([key, val]) => (
                    <div key={key} className="bg-white rounded-lg p-2 border border-slate-200 text-center">
                      <p className="text-lg font-bold text-amber-600">{val.toLocaleString()}</p>
                      <p className="text-xs text-slate-500">{key}</p>
                    </div>
                  ))}
                </div>
              )}
              {systemInfo.seed_guard && (
                <div className="mt-3 flex items-center gap-2 text-xs text-slate-500 bg-white rounded-lg p-2 border border-slate-200" dir="ltr">
                  <Shield className="w-3 h-3 text-green-500" />
                  <span>Seed Guard: {systemInfo.seed_guard.seed_blocked_in_prod ? 'ACTIVE' : 'INACTIVE'}</span>
                  <span className="text-slate-400">|</span>
                  <span>RUN_SEED: {systemInfo.seed_guard.run_seed}</span>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Projects Section */}
        <Card className="overflow-hidden">
          <SectionHeader icon={FolderOpen} title="פרויקטים" isOpen={openSections.projects}
            onToggle={() => toggleSection('projects')} count={projects.length} />
          {openSections.projects && (
            <div className="p-4 space-y-3">
              <Button size="sm" onClick={() => toggleForm('project')}
                className="bg-amber-500 hover:bg-amber-600 text-white w-full sm:w-auto">
                <Plus className="w-4 h-4 ml-1" />
                פרויקט חדש
              </Button>

              {showForm.project && (
                <form onSubmit={handleCreateProject} className="bg-amber-50 rounded-xl p-4 space-y-3 border border-amber-200">
                  <h4 className="text-sm font-semibold text-amber-800 text-right">פרויקט חדש</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <InputField label="שם פרויקט" value={newProject.name} required
                      onChange={e => setNewProject(p => ({ ...p, name: e.target.value }))} placeholder="לדוגמה: מגדל הים" />
                    <InputField label="קוד פרויקט" value={newProject.code} required
                      onChange={e => setNewProject(p => ({ ...p, code: e.target.value }))} placeholder="לדוגמה: SEA-001" />
                    <InputField label="שם לקוח" value={newProject.client_name}
                      onChange={e => setNewProject(p => ({ ...p, client_name: e.target.value }))} placeholder="שם החברה/לקוח" />
                    <InputField label="תיאור" value={newProject.description}
                      onChange={e => setNewProject(p => ({ ...p, description: e.target.value }))} placeholder="תיאור קצר" />
                  </div>
                  <div className="flex gap-2 justify-end">
                    <Button type="button" variant="outline" size="sm" onClick={() => setShowForm(f => ({ ...f, project: false }))}>ביטול</Button>
                    <Button type="submit" size="sm" className="bg-amber-500 hover:bg-amber-600 text-white" disabled={loading.createProject}>
                      {loading.createProject ? <Loader2 className="w-4 h-4 animate-spin" /> : 'צור פרויקט'}
                    </Button>
                  </div>
                </form>
              )}

              {loading.projects ? (
                <div className="flex justify-center py-4"><Loader2 className="w-6 h-6 animate-spin text-amber-500" /></div>
              ) : projects.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-4">אין פרויקטים עדיין</p>
              ) : (
                <div className="space-y-2">
                  {projects.map(project => {
                    const isExpanded = !!openProjects[project.id];
                    const isSelected = selectedProject?.id === project.id;
                    return (
                      <Card key={project.id} className="overflow-hidden border border-slate-200">
                        <button
                          onClick={() => toggleProject(project)}
                          className={`w-full flex items-center justify-between p-4 transition-colors touch-manipulation ${
                            isExpanded ? 'bg-amber-50 border-b border-amber-200' : 'bg-white hover:bg-slate-50'
                          }`}
                          dir="rtl"
                        >
                          <div className="flex items-center gap-3">
                            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${isExpanded ? 'bg-amber-200' : 'bg-amber-100'}`}>
                              <Building2 className="w-5 h-5 text-amber-600" />
                            </div>
                            <div className="text-right">
                              <p className="text-sm font-semibold text-slate-800">{project.name}</p>
                              <p className="text-xs text-slate-500">קוד: {project.code}{project.client_name ? ` • ${project.client_name}` : ''}</p>
                            </div>
                          </div>
                          <ChevronRight className={`w-5 h-5 text-slate-400 transition-transform duration-200 ${isExpanded ? 'rotate-90' : 'rotate-0'}`} />
                        </button>

                        <div
                          className="overflow-hidden transition-all duration-300 ease-in-out"
                          style={{ maxHeight: isExpanded ? '2000px' : '0', opacity: isExpanded ? 1 : 0 }}
                        >
                          {isExpanded && isSelected && (
                            <div className="p-4 space-y-4 bg-slate-50/50">

                              {/* PM Assignment inline */}
                              <div className="space-y-3">
                                <div className="flex items-center gap-2 mb-2" dir="rtl">
                                  <UserPlus className="w-4 h-4 text-blue-500" />
                                  <h4 className="text-sm font-semibold text-slate-700">מינוי מנהל פרויקט</h4>
                                </div>
                                <Button size="sm" onClick={() => toggleForm('pm')}
                                  className="bg-blue-500 hover:bg-blue-600 text-white w-full sm:w-auto">
                                  <UserPlus className="w-4 h-4 ml-1" />
                                  מנה מנהל פרויקט
                                </Button>

                                {showForm.pm && (
                                  <form onSubmit={handleAssignPM} className="bg-blue-50 rounded-xl p-4 space-y-3 border border-blue-200">
                                    <h4 className="text-sm font-semibold text-blue-800 text-right">מינוי מנהל פרויקט</h4>
                                    <div className="space-y-1" dir="rtl">
                                      <label className="block text-sm font-medium text-slate-700">בחר משתמש <span className="text-red-500">*</span></label>
                                      <select
                                        value={pmAssignment.user_id}
                                        onChange={e => setPmAssignment({ user_id: e.target.value })}
                                        className="w-full h-10 px-3 py-2 text-right text-sm bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500"
                                      >
                                        <option value="">בחר משתמש...</option>
                                        {pmCandidates.map(u => (
                                          <option key={u.id} value={u.id}>{u.name} ({u.email || u.phone_e164 || 'ללא'})</option>
                                        ))}
                                      </select>
                                      {pmCandidates.length === 0 && (
                                        <p className="text-xs text-slate-500 mt-1">אין משתמשים מתאימים. יש להוסיף משתמשים עם תפקיד מנהל פרויקט.</p>
                                      )}
                                    </div>
                                    <div className="flex gap-2 justify-end">
                                      <Button type="button" variant="outline" size="sm" onClick={() => setShowForm(f => ({ ...f, pm: false }))}>ביטול</Button>
                                      <Button type="submit" size="sm" className="bg-blue-500 hover:bg-blue-600 text-white" disabled={loading.assignPM}>
                                        {loading.assignPM ? <Loader2 className="w-4 h-4 animate-spin" /> : 'מנה PM'}
                                      </Button>
                                    </div>
                                  </form>
                                )}

                                <div className="bg-slate-50 rounded-lg p-3" dir="rtl">
                                  <h5 className="text-xs font-medium text-slate-500 mb-2">מנהלי פרויקטים רשומים</h5>
                                  {users.filter(u => u.role === 'project_manager').length === 0 ? (
                                    <p className="text-xs text-slate-400">אין מנהלי פרויקטים</p>
                                  ) : (
                                    <div className="space-y-1">
                                      {users.filter(u => u.role === 'project_manager').map(u => (
                                        <div key={u.id} className="flex items-center gap-2 text-sm text-slate-700">
                                          <Users className="w-4 h-4 text-blue-500" />
                                          <span>{u.name}</span>
                                          <span className="text-xs text-slate-400">{u.email || (u.phone_e164 ? <bdi className="font-mono" dir="ltr">{u.phone_e164}</bdi> : '')}</span>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>

                              <hr className="border-slate-200" />

                              {/* Buildings inline */}
                              <div className="space-y-3">
                                <div className="flex items-center gap-2 mb-2" dir="rtl">
                                  <Building2 className="w-4 h-4 text-amber-500" />
                                  <h4 className="text-sm font-semibold text-slate-700">בניינים ({buildings.length})</h4>
                                </div>
                                <div className="flex gap-2">
                                  <Button size="sm" onClick={() => toggleForm('building')}
                                    className="bg-amber-500 hover:bg-amber-600 text-white">
                                    <Plus className="w-4 h-4 ml-1" />
                                    בניין חדש
                                  </Button>
                                  <Button size="sm" variant="outline" onClick={() => loadBuildings(selectedProject.id)}>
                                    <RefreshCw className="w-4 h-4" />
                                  </Button>
                                </div>

                                {showForm.building && (
                                  <form onSubmit={handleCreateBuilding} className="bg-amber-50 rounded-xl p-4 space-y-3 border border-amber-200">
                                    <h4 className="text-sm font-semibold text-amber-800 text-right">בניין חדש</h4>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                      <InputField label="שם בניין" value={newBuilding.name} required
                                        onChange={e => setNewBuilding(b => ({ ...b, name: e.target.value }))} placeholder="לדוגמה: בניין A" />
                                      <InputField label="קוד" value={newBuilding.code}
                                        onChange={e => setNewBuilding(b => ({ ...b, code: e.target.value }))} placeholder="A" />
                                    </div>
                                    <div className="flex gap-2 justify-end">
                                      <Button type="button" variant="outline" size="sm" onClick={() => setShowForm(f => ({ ...f, building: false }))}>ביטול</Button>
                                      <Button type="submit" size="sm" className="bg-amber-500 hover:bg-amber-600 text-white" disabled={loading.createBuilding}>
                                        {loading.createBuilding ? <Loader2 className="w-4 h-4 animate-spin" /> : 'צור בניין'}
                                      </Button>
                                    </div>
                                  </form>
                                )}

                                {loading.buildings ? (
                                  <div className="flex justify-center py-4"><Loader2 className="w-6 h-6 animate-spin text-amber-500" /></div>
                                ) : buildings.length === 0 ? (
                                  <p className="text-sm text-slate-400 text-center py-4">אין בניינים בפרויקט זה</p>
                                ) : (
                                  <div className="space-y-2">
                                    {buildings.map(building => (
                                      <div key={building.id}
                                        onClick={() => selectBuilding(building)}
                                        className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors touch-manipulation ${
                                          selectedBuilding?.id === building.id ? 'bg-amber-100 border border-amber-300' : 'bg-white border border-slate-200 hover:bg-slate-50'
                                        }`} dir="rtl"
                                      >
                                        <div className="flex items-center gap-3">
                                          <Building2 className="w-4 h-4 text-slate-500" />
                                          <p className="text-sm font-medium text-slate-800">{building.name}</p>
                                        </div>
                                        <ChevronDown className="w-4 h-4 text-slate-400" />
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>

                              {/* Floors inline */}
                              {selectedBuilding && (
                                <>
                                  <hr className="border-slate-200" />
                                  <div className="space-y-3">
                                    <div className="flex items-center gap-2 mb-2" dir="rtl">
                                      <Layers className="w-4 h-4 text-slate-500" />
                                      <h4 className="text-sm font-semibold text-slate-700">קומות - {selectedBuilding.name} ({floors.length})</h4>
                                    </div>
                                    <Button size="sm" onClick={() => toggleForm('floor')}
                                      className="bg-amber-500 hover:bg-amber-600 text-white">
                                      <Plus className="w-4 h-4 ml-1" />
                                      קומה חדשה
                                    </Button>

                                    {showForm.floor && (
                                      <form onSubmit={handleCreateFloor} className="bg-amber-50 rounded-xl p-4 space-y-3 border border-amber-200">
                                        <h4 className="text-sm font-semibold text-amber-800 text-right">קומה חדשה</h4>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                          <InputField label="שם קומה" value={newFloor.name} required
                                            onChange={e => setNewFloor(f => ({ ...f, name: e.target.value }))} placeholder="לדוגמה: קומה 1" />
                                          <InputField label="מספר קומה" value={newFloor.floor_number} type="number"
                                            onChange={e => setNewFloor(f => ({ ...f, floor_number: e.target.value }))} placeholder="1" />
                                        </div>
                                        <div className="flex gap-2 justify-end">
                                          <Button type="button" variant="outline" size="sm" onClick={() => setShowForm(f => ({ ...f, floor: false }))}>ביטול</Button>
                                          <Button type="submit" size="sm" className="bg-amber-500 hover:bg-amber-600 text-white" disabled={loading.createFloor}>
                                            {loading.createFloor ? <Loader2 className="w-4 h-4 animate-spin" /> : 'צור קומה'}
                                          </Button>
                                        </div>
                                      </form>
                                    )}

                                    {loading.floors ? (
                                      <div className="flex justify-center py-4"><Loader2 className="w-6 h-6 animate-spin text-amber-500" /></div>
                                    ) : floors.length === 0 ? (
                                      <p className="text-sm text-slate-400 text-center py-4">אין קומות בבניין זה</p>
                                    ) : (
                                      <div className="space-y-2">
                                        {floors.map(floor => (
                                          <div key={floor.id}
                                            onClick={() => selectFloor(floor)}
                                            className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors touch-manipulation ${
                                              selectedFloor?.id === floor.id ? 'bg-amber-100 border border-amber-300' : 'bg-white border border-slate-200 hover:bg-slate-50'
                                            }`} dir="rtl"
                                          >
                                            <div className="flex items-center gap-3">
                                              <Layers className="w-4 h-4 text-slate-500" />
                                              <p className="text-sm font-medium text-slate-800">{floor.name}</p>
                                            </div>
                                            <ChevronDown className="w-4 h-4 text-slate-400" />
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                </>
                              )}

                              {/* Units inline */}
                              {selectedFloor && (
                                <>
                                  <hr className="border-slate-200" />
                                  <div className="space-y-3">
                                    <div className="flex items-center gap-2 mb-2" dir="rtl">
                                      <DoorOpen className="w-4 h-4 text-slate-500" />
                                      <h4 className="text-sm font-semibold text-slate-700">דירות - {selectedFloor.name} ({units.length})</h4>
                                    </div>
                                    <Button size="sm" onClick={() => toggleForm('unit')}
                                      className="bg-amber-500 hover:bg-amber-600 text-white">
                                      <Plus className="w-4 h-4 ml-1" />
                                      יחידה חדשה
                                    </Button>

                                    {showForm.unit && (
                                      <form onSubmit={handleCreateUnit} className="bg-amber-50 rounded-xl p-4 space-y-3 border border-amber-200">
                                        <h4 className="text-sm font-semibold text-amber-800 text-right">יחידה חדשה</h4>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                          <InputField label="מספר יחידה" value={newUnit.unit_no} required
                                            onChange={e => setNewUnit(u => ({ ...u, unit_no: e.target.value }))} placeholder="לדוגמה: 101" />
                                          <div className="space-y-1" dir="rtl">
                                            <label className="block text-sm font-medium text-slate-700">סוג יחידה</label>
                                            <select value={newUnit.unit_type}
                                              onChange={e => setNewUnit(u => ({ ...u, unit_type: e.target.value }))}
                                              className="w-full h-10 px-3 py-2 text-right text-sm bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                                            >
                                              <option value="apartment">דירה</option>
                                              <option value="office">משרד</option>
                                              <option value="commercial">מסחרי</option>
                                              <option value="storage">מחסן</option>
                                              <option value="parking">חניה</option>
                                            </select>
                                          </div>
                                        </div>
                                        <div className="flex gap-2 justify-end">
                                          <Button type="button" variant="outline" size="sm" onClick={() => setShowForm(f => ({ ...f, unit: false }))}>ביטול</Button>
                                          <Button type="submit" size="sm" className="bg-amber-500 hover:bg-amber-600 text-white" disabled={loading.createUnit}>
                                            {loading.createUnit ? <Loader2 className="w-4 h-4 animate-spin" /> : 'צור יחידה'}
                                          </Button>
                                        </div>
                                      </form>
                                    )}

                                    {loading.units ? (
                                      <div className="flex justify-center py-4"><Loader2 className="w-6 h-6 animate-spin text-amber-500" /></div>
                                    ) : units.length === 0 ? (
                                      <p className="text-sm text-slate-400 text-center py-4">אין דירות בקומה זו</p>
                                    ) : (
                                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                        {units.map(unit => (
                                          <div key={unit.id} className="p-3 bg-white border border-slate-200 rounded-lg text-center">
                                            <DoorOpen className="w-4 h-4 text-slate-400 mx-auto mb-1" />
                                            <p className="text-sm font-medium text-slate-800">{formatUnitLabel(unit.unit_no)}</p>
                                            <p className="text-xs text-slate-500">{unit.status || 'פנויה'}</p>
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                </>
                              )}

                            </div>
                          )}
                        </div>
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Companies Section */}
        <Card className="overflow-hidden">
          <SectionHeader icon={Briefcase} title="חברות קבלן" isOpen={openSections.companies}
            onToggle={() => toggleSection('companies')} count={companies.length} />
          {openSections.companies && (
            <div className="p-4 space-y-3">
              <Button size="sm" onClick={() => toggleForm('company')}
                className="bg-amber-500 hover:bg-amber-600 text-white w-full sm:w-auto">
                <Plus className="w-4 h-4 ml-1" />
                חברה חדשה
              </Button>

              {showForm.company && (
                <form onSubmit={handleCreateCompany} className="bg-amber-50 rounded-xl p-4 space-y-3 border border-amber-200">
                  <h4 className="text-sm font-semibold text-amber-800 text-right">חברה חדשה</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <InputField label="שם חברה" value={newCompany.name} required
                      onChange={e => setNewCompany(c => ({ ...c, name: e.target.value }))} placeholder="שם החברה" />
                    <div className="space-y-1" dir="rtl">
                      <label className="block text-sm font-medium text-slate-700">תחום</label>
                      <select value={newCompany.trade}
                        onChange={e => setNewCompany(c => ({ ...c, trade: e.target.value }))}
                        className="w-full h-10 px-3 py-2 text-right text-sm bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                      >
                        <option value="">בחר תחום...</option>
                        {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                      </select>
                    </div>
                    <InputField label="איש קשר" value={newCompany.contact_name}
                      onChange={e => setNewCompany(c => ({ ...c, contact_name: e.target.value }))} placeholder="שם איש קשר" />
                    <InputField label="טלפון" value={newCompany.contact_phone}
                      onChange={e => setNewCompany(c => ({ ...c, contact_phone: e.target.value }))} placeholder="050-1234567" />
                  </div>
                  <div className="flex gap-2 justify-end">
                    <Button type="button" variant="outline" size="sm" onClick={() => setShowForm(f => ({ ...f, company: false }))}>ביטול</Button>
                    <Button type="submit" size="sm" className="bg-amber-500 hover:bg-amber-600 text-white" disabled={loading.createCompany}>
                      {loading.createCompany ? <Loader2 className="w-4 h-4 animate-spin" /> : 'צור חברה'}
                    </Button>
                  </div>
                </form>
              )}

              {loading.companies ? (
                <div className="flex justify-center py-4"><Loader2 className="w-6 h-6 animate-spin text-amber-500" /></div>
              ) : companies.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-4">אין חברות</p>
              ) : (
                <div className="space-y-2">
                  {companies.map(company => (
                    <div key={company.id} className="p-3 bg-white border border-slate-200 rounded-lg" dir="rtl">
                      <div className="flex items-center gap-3">
                        <Briefcase className="w-4 h-4 text-amber-500" />
                        <div>
                          <p className="text-sm font-medium text-slate-800">{company.name}</p>
                          <p className="text-xs text-slate-500">
                            {company.trade ? CATEGORIES.find(c => c.value === company.trade)?.label || company.trade : 'כללי'}
                            {company.contact_name ? ` • ${company.contact_name}` : ''}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>

      </div>
    </div>
  );
};

export default AdminPage;
