from enum import Enum
from typing import Optional, List, Dict
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
    code: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.active
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


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None
    due_date: Optional[str] = None
    company_id: Optional[str] = None
    assignee_id: Optional[str] = None
    category: Optional[Category] = None


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


class ManagementRegistration(BaseModel):
    full_name: str
    email: str
    password: str
    phone_e164: str
    requested_role: str
    join_code: str


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
    insert_at_index: int
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
