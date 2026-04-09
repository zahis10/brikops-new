from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

CATEGORIES = [
    {"value": "entrance_door", "label": "דלת כניסה", "display_order": 1},
    {"value": "electrical", "label": "אביזרי חשמל", "display_order": 2},
    {"value": "aluminum", "label": "אלומיניום", "display_order": 3},
    {"value": "carpentry_kitchen", "label": "נגרות-מטבח", "display_order": 4},
    {"value": "plaster_paint", "label": "טיח וצבע", "display_order": 5},
    {"value": "plumbing", "label": "אינסטלציה", "display_order": 6},
    {"value": "tiling", "label": "ריצוף", "display_order": 7},
    {"value": "frames_shelter", "label": 'מסגרות-ממ"ד', "display_order": 8},
    {"value": "parking", "label": "חניון", "display_order": 9},
    {"value": "hvac", "label": "מיזוג אוויר", "display_order": 10},
    {"value": "carpentry", "label": "נגרות", "display_order": 11},
    {"value": "bathroom_cabinets", "label": "ארונות אמבטיה", "display_order": 12},
    {"value": "general", "label": "כללי", "display_order": 13},
    {"value": "doors", "label": "דלתות", "display_order": 14},
    {"value": "finishes", "label": "גמרים", "display_order": 15},
    {"value": "painting", "label": "צביעה", "display_order": 16},
    {"value": "structural", "label": "שלד", "display_order": 17},
    {"value": "windows", "label": "חלונות", "display_order": 18},
]

UNIT_LABELS = [
    {"value": "קומפ'", "label": "קומפ'"},
    {"value": 'מ"ר', "label": 'מ"ר'},
    {"value": "יח'", "label": "יח'"},
    {"value": 'מ"א', "label": 'מ"א'},
    {"value": "פאושלי", "label": "פאושלי"},
]

ROOMS = [
    {"value": "living_room", "label": "סלון"},
    {"value": "kitchen", "label": "מטבח"},
    {"value": "master_bedroom", "label": "חדר שינה הורים"},
    {"value": "bedroom_2", "label": "חדר שינה 2"},
    {"value": "bedroom_3", "label": "חדר שינה 3"},
    {"value": "bedroom_4", "label": "חדר שינה 4"},
    {"value": "bathroom_master", "label": "חדר רחצה הורים"},
    {"value": "bathroom_shared", "label": "חדר רחצה משותף"},
    {"value": "toilet", "label": "שירותים"},
    {"value": "toilet_guest", "label": "שירותי אורחים"},
    {"value": "balcony_main", "label": "מרפסת ראשית"},
    {"value": "balcony_service", "label": "מרפסת שירות"},
    {"value": "mamad", "label": 'ממ"ד'},
    {"value": "storage", "label": "מחסן"},
    {"value": "parking", "label": "חניה"},
    {"value": "hallway", "label": "מסדרון"},
    {"value": "entrance", "label": "כניסה"},
    {"value": "laundry", "label": "חדר כביסה"},
    {"value": "stairwell", "label": "חדר מדרגות"},
    {"value": "roof", "label": "גג"},
    {"value": "exterior", "label": "חזית חיצונית"},
    {"value": "common_area", "label": "שטח משותף"},
    {"value": "other", "label": "אחר"},
]

STANDARDS_LIBRARY = [
    {"id": "ti_1045", "code": 'ת"י 1045', "title": "תכנון מגורים", "category": "general"},
    {"id": "ti_23", "code": 'ת"י 23', "title": "בטון", "category": "structural"},
    {"id": "ti_12", "code": 'ת"י 12', "title": "פלדה", "category": "structural"},
    {"id": "ti_1555", "code": 'ת"י 1555', "title": "ריצוף וחיפוי", "category": "tiling"},
    {"id": "ti_1556", "code": 'ת"י 1556', "title": "אריחי קרמיקה", "category": "tiling"},
    {"id": "ti_938", "code": 'ת"י 938', "title": "דלתות פנים", "category": "doors"},
    {"id": "ti_23_1", "code": 'ת"י 23 חלק 1', "title": "בטון טרי", "category": "structural"},
    {"id": "ti_1474", "code": 'ת"י 1474', "title": "אלומיניום – חלונות ודלתות", "category": "aluminum"},
    {"id": "ti_1142", "code": 'ת"י 1142', "title": "איטום מבנים", "category": "waterproofing"},
    {"id": "ti_61", "code": 'ת"י 61', "title": "צנרת מים", "category": "plumbing"},
    {"id": "ti_158", "code": 'ת"י 158', "title": "התקנות חשמל", "category": "electrical"},
    {"id": "ti_5281", "code": 'ת"י 5281', "title": "בידוד תרמי", "category": "insulation"},
    {"id": "building_law", "code": "חוק התכנון והבנייה", "title": "תקנות התכנון והבנייה", "category": "legal"},
    {"id": "sale_law", "code": "חוק המכר (דירות)", "title": "חוק המכר דירות – תקופת בדק", "category": "legal"},
    {"id": "ti_1918", "code": 'ת"י 1918', "title": "טיח וציפויים", "category": "plaster"},
    {"id": "ti_4683", "code": 'ת"י 4683', "title": "גבס – לוחות", "category": "gypsum"},
]


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None
    role: str = 'tenant'

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    phone: Optional[str] = None
    role: str

class TokenResponse(BaseModel):
    token: str
    user: UserResponse


class ExpertProfileCreate(BaseModel):
    full_name: str
    title: Optional[str] = None
    education: Optional[str] = None
    certifications: Optional[List[str]] = []
    experience_years: Optional[int] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    signature_url: Optional[str] = None
    declaration_text: Optional[str] = None
    is_default: bool = False

class ExpertProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    title: Optional[str] = None
    education: Optional[str] = None
    certifications: Optional[List[str]] = None
    experience_years: Optional[int] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    signature_url: Optional[str] = None
    declaration_text: Optional[str] = None
    is_default: Optional[bool] = None

class ExpertProfileResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    title: Optional[str] = None
    education: Optional[str] = None
    certifications: List[str] = []
    experience_years: Optional[int] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    signature_url: Optional[str] = None
    declaration_text: Optional[str] = None
    is_default: bool = False
    created_at: str
    updated_at: Optional[str] = None


class PropertyCreate(BaseModel):
    address: str
    apt_number: Optional[str] = None
    property_type: Optional[str] = None
    floor: Optional[int] = None
    num_rooms: Optional[float] = None
    area_sqm: Optional[float] = None
    is_occupied: Optional[bool] = None
    has_electricity: Optional[bool] = None
    has_water: Optional[bool] = None
    client_name: Optional[str] = None

class PropertyResponse(BaseModel):
    id: str
    address: str
    apt_number: Optional[str] = None
    property_type: Optional[str] = None
    floor: Optional[int] = None
    num_rooms: Optional[float] = None
    area_sqm: Optional[float] = None
    is_occupied: Optional[bool] = None
    has_electricity: Optional[bool] = None
    has_water: Optional[bool] = None
    client_name: Optional[str] = None
    tenant_id: Optional[str] = None
    created_at: str


class InspectionCreate(BaseModel):
    property_id: Optional[str] = None
    handover_date: Optional[str] = None
    inspection_date: Optional[str] = None
    expert_profile_id: Optional[str] = None
    attendees: List[str] = []
    notes: Optional[str] = None
    property_address: Optional[str] = None
    property_type: Optional[str] = None
    property_floor: Optional[int] = None
    property_apt_number: Optional[str] = None
    property_num_rooms: Optional[float] = None
    property_area_sqm: Optional[float] = None
    property_is_occupied: Optional[bool] = None
    property_has_electricity: Optional[bool] = None
    property_has_water: Optional[bool] = None
    client_name: Optional[str] = None

class InspectionUpdate(BaseModel):
    status: Optional[str] = None
    handover_date: Optional[str] = None
    inspection_date: Optional[str] = None
    expert_profile_id: Optional[str] = None
    attendees: Optional[List[str]] = None
    notes: Optional[str] = None

class InspectionResponse(BaseModel):
    id: str
    property_id: Optional[str] = None
    tenant_id: Optional[str] = None
    status: str
    handover_date: Optional[str] = None
    inspection_date: Optional[str] = None
    expert_profile_id: Optional[str] = None
    attendees: List[str] = []
    notes: Optional[str] = None
    created_at: str
    updated_at: str
    property: Optional[PropertyResponse] = None
    rooms: Optional[List[Any]] = None
    client_name: Optional[str] = None


class RoomCreate(BaseModel):
    inspection_id: str
    room_type: str
    name: str
    min_media_count: Optional[int] = 0


class RoomStatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None

class MediaAssetResponse(BaseModel):
    id: str
    room_id: Optional[str] = None
    inspection_id: Optional[str] = None
    finding_id: Optional[str] = None
    file_url: str
    thumbnail_url: str
    type: str
    checksum: Optional[str] = None
    metadata: Dict[str, Any]
    uploaded_at: str
    created_at: Optional[str] = None

class FindingResponse(BaseModel):
    id: str
    room_id: str
    category: str
    description: str
    severity: str
    confidence: str
    ai_generated: bool
    status: str
    created_at: str
    updated_at: Optional[str] = None

class RoomResponse(BaseModel):
    id: str
    inspection_id: str
    room_type: str
    name: str
    min_media_count: int
    status: str = 'open'
    status_note: Optional[str] = None
    status_updated_at: Optional[str] = None
    created_at: str
    media: List[MediaAssetResponse] = []
    findings: List[FindingResponse] = []

class FindingCreate(BaseModel):
    room_id: str
    category: str
    description: str
    severity: str
    confidence: Optional[str] = 'high'
    ai_generated: Optional[bool] = False

class TenantEvidenceCreate(BaseModel):
    inspection_id: str
    room_id: Optional[str] = None
    room_guess: Optional[str] = None
    category_guess: Optional[str] = None
    tenant_note: Optional[str] = None
    tenant_impact: Optional[str] = 'medium'
    is_safety_concern: Optional[bool] = False
    evidence_ids: List[str] = []

class AISuggestion(BaseModel):
    suggested_room: Optional[str] = None
    suggested_category: Optional[str] = None
    suggested_severity: Optional[str] = None
    suggested_description: Optional[str] = None
    standard_refs: List[Dict[str, Any]] = []
    clause_refs: List[Dict[str, Any]] = []
    confidence: Optional[str] = 'medium'
    requires_reviewer: bool = True

class ReviewerFinal(BaseModel):
    final_category: Optional[str] = None
    final_severity: Optional[str] = None
    final_description: Optional[str] = None
    final_standard_refs: List[str] = []
    final_clause_refs: List[str] = []
    legal_notes: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None

class EvidenceFindingResponse(BaseModel):
    id: str
    inspection_id: str
    room_id: Optional[str] = None
    room_guess: Optional[str] = None
    category_guess: Optional[str] = None
    tenant_note: Optional[str] = None
    tenant_impact: Optional[str] = None
    is_safety_concern: bool = False
    evidence: List[MediaAssetResponse] = []
    ai_suggestions: Optional[AISuggestion] = None
    reviewer_final: Optional[ReviewerFinal] = None
    status: str
    created_at: str
    updated_at: Optional[str] = None

class FindingUpdate(BaseModel):
    category: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    confidence: Optional[str] = None
    status: Optional[str] = None

class ExpertReviewCreate(BaseModel):
    finding_id: str
    status: str
    comments: Optional[str] = None

class ExpertReviewResponse(BaseModel):
    id: str
    finding_id: str
    reviewer_id: str
    status: str
    comments: Optional[str] = None
    reviewed_at: str


class ProfessionalFindingCreate(BaseModel):
    inspection_id: str
    finding_number: Optional[str] = None
    category: str
    sub_category: Optional[str] = None
    room_id: Optional[str] = None
    location_text: Optional[str] = None
    location: Optional[str] = None
    description: str
    note: Optional[str] = None
    recommendation: Optional[str] = None
    standard_reference: Optional[str] = None
    unit_price: Optional[float] = None
    quantity: Optional[float] = None
    unit_label: Optional[str] = None
    total_price: Optional[float] = None
    severity: str = "medium"
    status: str = "open"
    contractor_type: Optional[str] = None
    urgency: Optional[str] = None
    responsible_party: Optional[str] = None
    evidence_ids: List[str] = []
    ai_suggested: bool = False
    ai_suggestions: Optional[Dict[str, Any]] = None

class ProfessionalFindingUpdate(BaseModel):
    finding_number: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    room_id: Optional[str] = None
    location_text: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    note: Optional[str] = None
    recommendation: Optional[str] = None
    standard_reference: Optional[str] = None
    unit_price: Optional[float] = None
    quantity: Optional[float] = None
    unit_label: Optional[str] = None
    total_price: Optional[float] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    contractor_type: Optional[str] = None
    urgency: Optional[str] = None
    responsible_party: Optional[str] = None
    evidence_ids: Optional[List[str]] = None
    ai_suggested: Optional[bool] = None
    ai_suggestions: Optional[Dict[str, Any]] = None

class ProfessionalFindingResponse(BaseModel):
    id: str
    inspection_id: str
    finding_number: Optional[str] = None
    category: str
    sub_category: Optional[str] = None
    room_id: Optional[str] = None
    location_text: Optional[str] = None
    location: Optional[str] = None
    description: str
    note: Optional[str] = None
    recommendation: Optional[str] = None
    standard_reference: Optional[str] = None
    unit_price: Optional[float] = None
    quantity: Optional[float] = None
    unit_label: Optional[str] = None
    total_price: Optional[float] = None
    severity: str = "medium"
    status: str = "open"
    contractor_type: Optional[str] = None
    urgency: Optional[str] = None
    responsible_party: Optional[str] = None
    evidence_ids: List[str] = []
    ai_suggested: bool = False
    ai_suggestions: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: Optional[str] = None


class FindingDuplicate(BaseModel):
    finding_id: str


class ReportResponse(BaseModel):
    id: str
    inspection_id: str
    pdf_url: str
    generated_by: str
    generated_at: str
    report_type: Optional[str] = None
    expert_profile_id: Optional[str] = None
    total_findings: Optional[int] = None
    total_cost: Optional[float] = None

class AuditLogResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    user_id: str
    timestamp: str
    changes: Dict[str, Any]
