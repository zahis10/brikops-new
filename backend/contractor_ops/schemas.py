from enum import Enum
from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field, validator


class TaskStatus(str, Enum):
    open = "open"
    assigned = "assigned"
    in_progress = "in_progress"
    waiting_verify = "waiting_verify"
    pending_contractor_proof = "pending_contractor_proof"
    pending_manager_approval = "pending_manager_approval"
    returned_to_contractor = "returned_to_contractor"
    closed = "closed"
    approved = "approved"
    reopened = "reopened"


VALID_TRANSITIONS = {
    TaskStatus.open: [TaskStatus.assigned, TaskStatus.in_progress],
    TaskStatus.assigned: [TaskStatus.in_progress],
    TaskStatus.in_progress: [TaskStatus.waiting_verify, TaskStatus.pending_contractor_proof],
    TaskStatus.waiting_verify: [TaskStatus.closed],
    TaskStatus.pending_contractor_proof: [TaskStatus.pending_manager_approval],
    TaskStatus.pending_manager_approval: [TaskStatus.closed, TaskStatus.returned_to_contractor],
    TaskStatus.returned_to_contractor: [TaskStatus.in_progress, TaskStatus.pending_contractor_proof],
    TaskStatus.closed: [TaskStatus.reopened],
    TaskStatus.reopened: [TaskStatus.in_progress, TaskStatus.closed],
}


class ManagementSubRole(str, Enum):
    site_manager = "site_manager"
    execution_engineer = "execution_engineer"
    safety_assistant = "safety_assistant"
    work_manager = "work_manager"
    safety_officer = "safety_officer"


class MembershipRole(str, Enum):
    project_manager = "project_manager"
    management_team = "management_team"
    contractor = "contractor"
    viewer = "viewer"


class OrgRole(str, Enum):
    member = "member"
    project_manager = "project_manager"
    org_admin = "org_admin"
    billing_admin = "billing_admin"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Role(str, Enum):
    project_manager = "project_manager"
    management_team = "management_team"
    contractor = "contractor"
    viewer = "viewer"


class UserStatus(str, Enum):
    active = "active"
    pending_pm_approval = "pending_pm_approval"
    rejected = "rejected"
    suspended = "suspended"
    pending_deletion = "pending_deletion"
    deleted = "deleted"


class Category(str, Enum):
    electrical = "electrical"
    plumbing = "plumbing"
    hvac = "hvac"
    painting = "painting"
    flooring = "flooring"
    carpentry = "carpentry"
    carpentry_kitchen = "carpentry_kitchen"
    masonry = "masonry"
    windows = "windows"
    doors = "doors"
    general = "general"
    bathroom_cabinets = "bathroom_cabinets"
    finishes = "finishes"
    structural = "structural"
    aluminum = "aluminum"
    metalwork = "metalwork"
    glazing = "glazing"


class ProjectStatus(str, Enum):
    draft = "draft"
    payment_pending = "payment_pending"
    active = "active"
    suspended = "suspended"


class UnitType(str, Enum):
    apartment = "apartment"
    commercial = "commercial"
    parking = "parking"
    storage = "storage"


class UnitStatus(str, Enum):
    available = "available"
    occupied = "occupied"


class UpdateType(str, Enum):
    comment = "comment"
    status_change = "status_change"
    attachment = "attachment"
    force_closed = "force_closed"


class Project(BaseModel):
    id: Optional[str] = None
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.active
    total_units: Optional[int] = None
    client_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    created_by: Optional[str] = None
    org_id: Optional[str] = None
    join_code: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    onboarding_complete: Optional[bool] = None
    onboarding_completed_at: Optional[str] = None


class Building(BaseModel):
    id: Optional[str] = None
    project_id: str
    name: str
    code: Optional[str] = None
    floors_count: Optional[int] = 0
    created_at: Optional[str] = None


class FloorKind(str, Enum):
    residential = "residential"
    technical = "technical"
    service = "service"
    roof = "roof"
    basement = "basement"
    ground = "ground"
    parking = "parking"
    commercial = "commercial"


class Floor(BaseModel):
    id: Optional[str] = None
    building_id: Optional[str] = None
    project_id: Optional[str] = None
    name: str
    floor_number: int = 0
    sort_index: Optional[int] = None
    display_label: Optional[str] = None
    kind: Optional[FloorKind] = None
    unit_count: int = 0
    created_at: Optional[str] = None
    insert_after_floor_id: Optional[str] = None


class Unit(BaseModel):
    id: Optional[str] = None
    floor_id: Optional[str] = None
    building_id: Optional[str] = None
    project_id: Optional[str] = None
    unit_no: str = ''
    unit_type: UnitType = UnitType.apartment
    status: UnitStatus = UnitStatus.available
    sort_index: Optional[int] = None
    display_label: Optional[str] = None
    unit_count: Optional[int] = None
    unit_type_tag: Optional[str] = None
    unit_note: Optional[str] = None
    spare_tiles_count: Optional[int] = None
    spare_tiles_notes: Optional[str] = None
    spare_tiles: Optional[List[Dict]] = None
    created_at: Optional[str] = None


class Company(BaseModel):
    id: Optional[str] = None
    name: str
    trade: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    specialties: Optional[List[Category]] = None
    phone_e164: Optional[str] = None
    whatsapp_enabled: bool = False
    whatsapp_opt_in: bool = False
    created_at: Optional[str] = None

    @validator('trade', pre=True, always=True)
    def validate_trade(cls, v):
        if v is None:
            return None
        if isinstance(v, Enum):
            v = v.value
        if not isinstance(v, str):
            raise ValueError('שם תחום חייב להיות טקסט')
        v = v.strip()
        if len(v) < 1:
            return None
        if len(v) > 50:
            raise ValueError('שם תחום ארוך מדי (עד 50 תווים)')
        return v


class UserCreate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    name: str
    phone: Optional[str] = None
    role: Role = Role.viewer
    company_id: Optional[str] = None
    specialties: Optional[List[str]] = None
    phone_e164: Optional[str] = None
    # 2026-05-08 — ToS consent capture (Israeli Spam Law).
    terms_accepted: bool = False


class ProjectMembershipSummary(BaseModel):
    project_id: str
    project_name: Optional[str] = None
    role: Optional[str] = None
    contractor_trade_key: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None


class OrgSummary(BaseModel):
    id: str
    name: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: Optional[str] = None
    name: str
    phone: Optional[str] = None
    role: Role
    company_id: Optional[str] = None
    specialties: Optional[List[str]] = None
    phone_e164: Optional[str] = None
    user_status: Optional[str] = None
    created_at: Optional[str] = None
    platform_role: Optional[str] = 'none'
    preferred_language: Optional[str] = None
    whatsapp_notifications_enabled: Optional[bool] = True
    organization: Optional[OrgSummary] = None
    project_memberships_summary: Optional[List[ProjectMembershipSummary]] = None


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user: UserResponse


class Task(BaseModel):
    id: Optional[str] = None
    project_id: str
    building_id: Optional[str] = None
    floor_id: Optional[str] = None
    unit_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: str = "general"
    priority: Priority = Priority.medium
    status: TaskStatus = TaskStatus.open
    company_id: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    short_ref: Optional[str] = None
    display_number: Optional[int] = None
    attachments_count: int = 0
    comments_count: int = 0
    source: Optional[str] = None
    force_closed_by: Optional[str] = None
    force_closed_reason: Optional[str] = None
    force_closed_at: Optional[str] = None
    force_closed_type: Optional[str] = None
    is_safety: Optional[bool] = False


class TaskCreate(BaseModel):
    project_id: str
    building_id: str
    floor_id: str
    unit_id: str
    title: str
    description: Optional[str] = None
    category: Category = Category.general
    priority: Priority = Priority.medium
    company_id: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[str] = None
    is_safety: Optional[bool] = False


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None
    due_date: Optional[str] = None
    company_id: Optional[str] = None
    assignee_id: Optional[str] = None
    category: Optional[Category] = None
    is_safety: Optional[bool] = None


class TaskAssign(BaseModel):
    company_id: Optional[str] = None
    assignee_id: Optional[str] = None
    force_category_change: Optional[bool] = None


class TaskStatusChange(BaseModel):
    status: TaskStatus
    note: Optional[str] = None


class TaskUpdateCreate(BaseModel):
    task_id: str
    content: str
    update_type: UpdateType = UpdateType.comment
    attachment_url: Optional[str] = None
    old_status: Optional[TaskStatus] = None
    new_status: Optional[TaskStatus] = None


class TaskUpdateResponse(BaseModel):
    id: str
    task_id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    content: Optional[str] = None
    update_type: UpdateType
    attachment_url: Optional[str] = None
    old_status: Optional[TaskStatus] = None
    new_status: Optional[TaskStatus] = None
    created_at: Optional[str] = None


class AuditEvent(BaseModel):
    id: Optional[str] = None
    entity_type: str
    entity_id: str
    action: str
    actor_id: str
    payload: Dict = Field(default_factory=dict)
    created_at: Optional[str] = None


class DashboardResponse(BaseModel):
    total_tasks: int = 0
    by_status: Dict = Field(default_factory=dict)
    by_building: List = Field(default_factory=list)
    by_category: Dict = Field(default_factory=dict)
    overdue_count: int = 0


class NotificationStatus(str, Enum):
    queued = "queued"
    skipped_dry_run = "skipped_dry_run"
    sent = "sent"
    delivered = "delivered"
    read = "read"
    failed = "failed"


class NotificationEventType(str, Enum):
    task_created = "task_created"
    task_assigned = "task_assigned"
    status_waiting_verify = "status_waiting_verify"
    status_closed = "status_closed"
    manual_send = "manual_send"
    contractor_proof_uploaded = "contractor_proof_uploaded"
    manager_approved = "manager_approved"
    manager_rejected = "manager_rejected"


class NotificationJob(BaseModel):
    id: Optional[str] = None
    task_id: str
    event_type: NotificationEventType
    target_phone: str
    payload: Dict = Field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.queued
    attempts: int = 0
    max_attempts: int = 3
    provider_message_id: Optional[str] = None
    last_error: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    next_retry_at: Optional[str] = None


class NotificationJobResponse(BaseModel):
    id: str
    task_id: str
    event_type: str
    target_phone: str
    status: str
    attempts: int
    provider_message_id: Optional[str] = None
    last_error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ManualNotifyRequest(BaseModel):
    message: Optional[str] = None


class ManagerDecisionRequest(BaseModel):
    decision: str
    reason: Optional[str] = None


class Track(str, Enum):
    management = "management"
    subcontractor = "subcontractor"


class JoinRequestStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class OTPRequest(BaseModel):
    phone_e164: str
    platform: Optional[str] = None


class OTPVerify(BaseModel):
    phone_e164: str
    code: str


class PhoneRegistration(BaseModel):
    phone_e164: str
    full_name: str
    project_id: str
    track: Track
    requested_role: str
    requested_company_id: Optional[str] = None
    # 2026-05-08 — ToS consent capture (Israeli Spam Law).
    terms_accepted: bool = False


class ManagementRegistration(BaseModel):
    full_name: str
    email: str
    password: str
    phone_e164: str
    requested_role: str
    join_code: str
    # 2026-05-08 — ToS consent capture (Israeli Spam Law).
    terms_accepted: bool = False


class SetPasswordRequest(BaseModel):
    password: str


class PhoneLoginRequest(BaseModel):
    phone_e164: str
    password: str


class JoinRequestResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    user_name: str
    user_phone: str
    track: str
    requested_role: str
    requested_company_id: Optional[str] = None
    company_name: Optional[str] = None
    status: str
    reason: Optional[str] = None
    created_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None


class ApproveRequest(BaseModel):
    role: Optional[str] = None
    company_id: Optional[str] = None


class RejectRequest(BaseModel):
    reason: str


class BulkFloorRequest(BaseModel):
    project_id: str
    building_id: str
    from_floor: int
    to_floor: int
    dry_run: bool = False
    batch_id: Optional[str] = None
    insert_after_floor_id: Optional[str] = None

class BulkUnitRequest(BaseModel):
    project_id: str
    building_id: str
    from_floor: int
    to_floor: int
    units_per_floor: int
    unit_start_number: int = 1
    unit_number_padding: int = 0
    unit_prefix: Optional[str] = None
    dry_run: bool = False
    batch_id: Optional[str] = None

class BulkResultResponse(BaseModel):
    created_count: int
    skipped_count: int = 0
    items: List = Field(default_factory=list)
    message: str = ""

class HierarchyBuilding(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    floors: List = Field(default_factory=list)

class HierarchyFloor(BaseModel):
    id: str
    name: str
    floor_number: int
    sort_index: int = 0
    display_label: Optional[str] = None
    kind: Optional[str] = None
    units: List = Field(default_factory=list)

class HierarchyUnit(BaseModel):
    id: str
    unit_no: str
    unit_type: str = "apartment"
    status: str = "available"
    sort_index: int = 0
    display_label: Optional[str] = None


class ResequencePreview(BaseModel):
    floors_affected: int = 0
    units_affected: int = 0
    changes: List = Field(default_factory=list)

class InsertFloorRequest(BaseModel):
    building_id: str
    name: str
    display_label: Optional[str] = None
    kind: Optional[FloorKind] = None
    insert_at_index: Optional[int] = None
    insert_after_floor_id: Optional[str] = None
    auto_renumber_units: bool = False
    unit_numbering_base: int = 100
    dry_run: bool = False

class HierarchyResponse(BaseModel):
    project_id: str
    project_name: str
    buildings: List[HierarchyBuilding] = Field(default_factory=list)

class ProjectCompany(BaseModel):
    id: Optional[str] = None
    project_id: str
    name: str
    trade: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    created_at: Optional[str] = None

    @validator('trade', pre=True, always=True)
    def validate_trade(cls, v):
        if v is None:
            return None
        if isinstance(v, Enum):
            v = v.value
        if not isinstance(v, str):
            raise ValueError('שם תחום חייב להיות טקסט')
        v = v.strip()
        if len(v) < 1:
            return None
        if len(v) > 50:
            raise ValueError('שם תחום ארוך מדי (עד 50 תווים)')
        return v

class TeamInvite(BaseModel):
    id: Optional[str] = None
    project_id: str
    phone: str
    full_name: Optional[str] = None
    role: Role = Role.contractor
    company_id: Optional[str] = None
    status: str = "pending"
    invited_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ProjectStatsResponse(BaseModel):
    buildings: int = 0
    floors: int = 0
    units: int = 0
    team_members: int = 0
    companies: int = 0
    open_defects: int = 0


class InviteStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    expired = "expired"
    cancelled = "cancelled"

class InviteRole(str, Enum):
    project_manager = "project_manager"
    management_team = "management_team"
    contractor = "contractor"

class InviteCreate(BaseModel):
    phone: str
    role: InviteRole
    sub_role: Optional[str] = None
    full_name: str
    trade_key: Optional[str] = None
    company_id: Optional[str] = None

class InviteResponse(BaseModel):
    id: str
    project_id: str
    inviter_user_id: str
    target_phone: str
    role: str
    sub_role: Optional[str] = None
    token: str
    status: str
    expires_at: str
    accepted_by_user_id: Optional[str] = None
    accepted_at: Optional[str] = None
    created_at: str
    updated_at: str

# =====================================================================
# Safety Module — Phase 1 data models
# Added: 2026-04-22 · Part 1 Foundation
# References: specs/safety-phase-1-master-plan.md §5 (Mac-side spec)
# =====================================================================

class SafetyCategory(str, Enum):
    """10 regulatory safety categories per תקנות התשע"ט-2019"""
    scaffolding = "scaffolding"          # פיגומים
    heights = "heights"                  # עבודה בגובה
    electrical_safety = "electrical_safety"  # בטיחות חשמל
    lifting = "lifting"                  # הרמה וציוד
    excavation = "excavation"            # חפירות
    fire_safety = "fire_safety"          # אש ובטיחות אש
    ppe = "ppe"                          # ציוד מגן אישי
    site_housekeeping = "site_housekeeping"  # סדר וניקיון
    hazardous_materials = "hazardous_materials"  # חומרים מסוכנים
    other = "other"                      # אחר


class SafetySeverity(str, Enum):
    """Severity 1-3 per Cemento convention"""
    sev_1 = "1"   # נמוכה — הערה/שיפור
    sev_2 = "2"   # בינונית — דורש תיקון
    sev_3 = "3"   # גבוהה — עצירה מיידית


class SafetyDocumentStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    verified = "verified"


class SafetyTaskStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class SafetyWorker(BaseModel):
    """Worker on site — minimal Phase 1 shape. Extended in Part 2."""
    id: str                              # uuid4
    project_id: str
    company_id: Optional[str] = None     # FK → project_companies.id
    full_name: str
    id_number: Optional[str] = None      # Israeli/Palestinian/foreign ID; stored raw, hashed in Part 2
    profession: Optional[str] = None     # e.g. "נגר", "חשמלאי"
    phone: Optional[str] = None
    notes: Optional[str] = None
    created_at: str                      # ISO UTC via _now()
    created_by: str                      # actor user id
    # soft-delete (project-wide convention — camelCase)
    deletedAt: Optional[str] = None
    deletedBy: Optional[str] = None
    deletion_reason: Optional[str] = None
    retention_until: Optional[str] = None  # 7yr from delete for regulatory


class SafetyTraining(BaseModel):
    """Training record per worker. Expiry drives Safety Score."""
    id: str
    project_id: str
    worker_id: str                       # FK → safety_workers.id
    training_type: str                   # e.g. "הדרכת אתר", "הדרכת סיכונים"
    instructor_name: Optional[str] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    trained_at: str                      # ISO date
    expires_at: Optional[str] = None     # ISO date; null = no expiry
    certificate_url: Optional[str] = None  # R2/S3 URL if uploaded
    created_at: str
    created_by: str
    deletedAt: Optional[str] = None
    deletedBy: Optional[str] = None


class SafetyDocument(BaseModel):
    """Safety observation/finding — the regulatory תיעוד records."""
    id: str
    project_id: str
    category: SafetyCategory
    severity: SafetySeverity
    status: SafetyDocumentStatus = SafetyDocumentStatus.open
    title: str
    description: Optional[str] = None
    location: Optional[str] = None       # e.g. "קומה 4, גוש מזרחי"
    company_id: Optional[str] = None     # FK → project_companies.id
    profession: Optional[str] = None
    assignee_id: Optional[str] = None    # user id
    reporter_id: str                     # user id
    photo_urls: List[str] = []
    attachment_urls: List[str] = []      # PDF/doc attachments
    found_at: str                        # ISO UTC (when observed)
    resolved_at: Optional[str] = None
    created_at: str
    created_by: str
    updated_at: Optional[str] = None
    deletedAt: Optional[str] = None
    deletedBy: Optional[str] = None


class SafetyTask(BaseModel):
    """Corrective action task."""
    id: str
    project_id: str
    document_id: Optional[str] = None    # FK → safety_documents.id
    title: str
    description: Optional[str] = None
    status: SafetyTaskStatus = SafetyTaskStatus.open
    severity: SafetySeverity
    assignee_id: Optional[str] = None
    company_id: Optional[str] = None
    due_at: Optional[str] = None
    completed_at: Optional[str] = None
    corrective_action: Optional[str] = None
    verification_photo_urls: List[str] = []
    created_at: str
    created_by: str
    updated_at: Optional[str] = None
    deletedAt: Optional[str] = None
    deletedBy: Optional[str] = None


class SafetyIncident(BaseModel):
    """Near-miss or injury event. 7-year retention is REGULATORY (not optional)."""
    id: str
    project_id: str
    incident_type: str                   # "near_miss" | "injury" | "property_damage"
    severity: SafetySeverity
    occurred_at: str                     # ISO UTC
    description: str
    location: Optional[str] = None
    injured_worker_id: Optional[str] = None  # FK → safety_workers.id; null if near-miss
    witnesses: List[str] = []            # worker_ids
    photo_urls: List[str] = []
    medical_record_urls: List[str] = []  # PHI — encrypted at rest (Part 2)
    reported_to_authority: bool = False
    authority_report_ref: Optional[str] = None
    created_at: str
    created_by: str
    updated_at: Optional[str] = None
    # soft-delete: retention_until MUST be set to occurred_at + 7yr on delete
    deletedAt: Optional[str] = None
    deletedBy: Optional[str] = None
    deletion_reason: Optional[str] = None
    retention_until: Optional[str] = None



# =====================================================================
# Safety Project Registration (Batch S2A 2026-05-04)
# Implements Israeli Ministry of Economy "פנקס הקבלנים" format.
# Manual entry only (per Zahi decision — no external API).
# =====================================================================

class SafetyProjectManager(BaseModel):
    """One manager entry in the registration document.
    Repeat group — a project can have N managers."""
    first_name: str = Field(..., min_length=1, max_length=60)
    last_name: str = Field(..., min_length=1, max_length=60)
    id_number: Optional[str] = None
    address: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = Field(None, max_length=500)


class SafetyProjectPersonnel(BaseModel):
    """One safety personnel entry embedded on the registration document.
    Repeat group — N per role. 5 canonical roles from VALID_SUB_ROLES."""
    role: Literal[
        'site_manager',
        'execution_engineer',
        'safety_assistant',
        'work_manager',
        'safety_officer',
    ]
    first_name: str = Field(..., min_length=1, max_length=60)
    last_name: str = Field(..., min_length=1, max_length=60)
    id_number: Optional[str] = None
    license_number: Optional[str] = Field(None, max_length=30)
    notes: Optional[str] = Field(None, max_length=500)


class SafetyProjectAddress(BaseModel):
    """Section 2 — מען המשרד הראשי / המשרד הרשום."""
    city: Optional[str] = Field(None, max_length=80)
    postal_code: Optional[str] = Field(None, max_length=10)
    street: Optional[str] = Field(None, max_length=120)
    house_number: Optional[str] = Field(None, max_length=10)
    email: Optional[str] = Field(None, max_length=120)
    phone: Optional[str] = Field(None, max_length=20)
    mobile: Optional[str] = Field(None, max_length=20)
    fax: Optional[str] = Field(None, max_length=20)


class SafetyProjectRegistration(BaseModel):
    """One registration record per project (1:1).
    Persisted in collection `safety_project_settings`."""
    developer_name: Optional[str] = Field(None, max_length=200)
    main_contractor_name: Optional[str] = Field(None, max_length=200)
    contractor_registry_number: Optional[str] = Field(None, max_length=20)
    office_address: Optional[SafetyProjectAddress] = None
    managers: List[SafetyProjectManager] = Field(default_factory=list)
    personnel: List[SafetyProjectPersonnel] = Field(default_factory=list)
    permit_number: Optional[str] = Field(None, max_length=30)
    form_4_target_date: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class SafetyProjectRegistrationUpsert(BaseModel):
    """PATCH-style upsert. All fields optional — partial updates allowed."""
    developer_name: Optional[str] = None
    main_contractor_name: Optional[str] = None
    contractor_registry_number: Optional[str] = None
    office_address: Optional[SafetyProjectAddress] = None
    managers: Optional[List[SafetyProjectManager]] = None
    personnel: Optional[List[SafetyProjectPersonnel]] = None
    permit_number: Optional[str] = None
    form_4_target_date: Optional[str] = None


# =====================================================================
# Execution Matrix (Batch Execution Matrix Phase 1, 2026-05-04)
# PMs / execution engineers track project state in a 2D grid
# (units × stages) with 6 status values + custom columns.
# =====================================================================

MATRIX_STATUS_VALUES = (
    'completed',       # ✓ בוצע
    'partial',         # ⚠ חלקי
    'ready_for_work',  # 🚚 מוכן לעבודה (#503-followup-3 — manual-only, planning state)
    'in_progress',     # ◷ בעבודה
    'pending_review',  # ⏳ ממתין לאישור (#503-followup-2 — sync-only from QC)
    'not_done',        # ✗ לא בוצע
    'not_relevant',    # − אין צורך
    'no_findings',     # ⊘ אין חוסרים
)

MATRIX_STAGE_TYPES = ('status', 'tag')


class MatrixStageCreate(BaseModel):
    """Custom stage added by approver/PM (NOT part of qc_template)."""
    title: str = Field(..., min_length=1, max_length=80)
    type: Literal['status', 'tag'] = 'status'
    order: Optional[int] = None
    id: Optional[str] = None


class MatrixStage(BaseModel):
    """Stage entry in the matrix — either base (from qc_template) or custom."""
    id: str
    title: str
    type: Literal['status', 'tag']
    order: int
    source: Literal['base', 'custom']
    scope: Optional[Literal['floor', 'unit']] = None


class MatrixStagesUpdate(BaseModel):
    """PATCH-style update for the project matrix's stage list."""
    custom_stages_added: Optional[List[MatrixStageCreate]] = None
    base_stages_removed: Optional[List[str]] = None


class MatrixCellAuditEntry(BaseModel):
    actor_id: str
    actor_name: str
    timestamp: str
    status_before: Optional[str] = None
    status_after: Optional[str] = None
    note_before: Optional[str] = None
    note_after: Optional[str] = None
    text_before: Optional[str] = None
    text_after: Optional[str] = None


class MatrixCellUpdate(BaseModel):
    """PATCH-style update for a single matrix cell."""
    status: Optional[Literal[
        'completed', 'partial', 'ready_for_work', 'in_progress',
        'not_done', 'not_relevant', 'no_findings',
        # NOTE (#503-followup-3): 'pending_review' INTENTIONALLY omitted
        # — sync-only from QC submit_stage. Manual PATCH must not set it.
        # 'ready_for_work' IS allowed (manual-only, planning state).
    ]] = None
    note: Optional[str] = Field(None, max_length=500)
    text_value: Optional[str] = Field(None, max_length=200)


class MatrixCell(BaseModel):
    """Cell in the matrix — one (unit_id × stage_id) entry."""
    project_id: str
    unit_id: str
    stage_id: str
    status: Optional[str] = None
    text_value: Optional[str] = None
    note: Optional[str] = None
    audit: List[MatrixCellAuditEntry] = Field(default_factory=list)
    last_updated_at: Optional[str] = None
    last_updated_by: Optional[str] = None
    # #503 — QC→Matrix sync metadata. `synced_from_qc=True` means the
    # current `status` was set by qc_to_matrix_sync; manual PM edits
    # set it back to False (or unset). Frontend uses these to render
    # the "מסונכרן מבקרת ביצוע" badge + warning in CellEditDialog.
    synced_from_qc: Optional[bool] = False
    last_qc_sync_at: Optional[str] = None


class MatrixSavedViewFilters(BaseModel):
    """Filter configuration for a saved view."""
    building_ids: Optional[List[str]] = None
    floor_ids: Optional[List[str]] = None
    unit_ids: Optional[List[str]] = None
    stage_status_filters: Optional[Dict[str, List[str]]] = None
    tag_value_filters: Optional[Dict[str, List[str]]] = None
    search_text: Optional[str] = None


class MatrixSavedViewCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)
    icon: Optional[str] = Field(None, max_length=10)
    filters: MatrixSavedViewFilters


class MatrixSavedView(BaseModel):
    id: str
    project_id: str
    user_id: str
    title: str
    icon: Optional[str] = None
    filters: MatrixSavedViewFilters
    created_at: str
    updated_at: Optional[str] = None
