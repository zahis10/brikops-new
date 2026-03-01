from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Existing models...

class RegulationCreate(BaseModel):
    source_name: str
    source_url: Optional[str] = None
    law_id: Optional[str] = None
    standard_id: Optional[str] = None
    section: Optional[str] = None
    title: str
    description: Optional[str] = None
    version_date: Optional[str] = None

class RegulationResponse(BaseModel):
    id: str
    source_name: str
    source_url: Optional[str] = None
    law_id: Optional[str] = None
    standard_id: Optional[str] = None
    section: Optional[str] = None
    title: str
    description: Optional[str] = None
    version_date: Optional[str] = None
    last_verified_at: Optional[str] = None
    created_at: str

class DocumentUpload(BaseModel):
    inspection_id: str
    document_type: str  # contract, specification, annex, delivery_protocol, correspondence
    filename: str
    description: Optional[str] = None

class DocumentResponse(BaseModel):
    id: str
    inspection_id: str
    document_type: str
    filename: str
    file_path: str
    file_size: int
    checksum: str  # SHA-256
    version: int
    uploaded_by: str
    uploaded_at: str
    ocr_completed: bool = False
    clause_count: int = 0

class DocumentClauseResponse(BaseModel):
    id: str
    document_id: str
    clause_number: str
    clause_text: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    extracted_at: str

class FindingCitationCreate(BaseModel):
    finding_id: str
    regulation_id: Optional[str] = None
    clause_id: Optional[str] = None
    citation_type: str  # regulation, contract_clause, specification
    confidence: str = 'high'  # low, medium, high
    notes: Optional[str] = None

class FindingCitationResponse(BaseModel):
    id: str
    finding_id: str
    regulation_id: Optional[str] = None
    clause_id: Optional[str] = None
    citation_type: str
    confidence: str
    notes: Optional[str] = None
    created_at: str
    regulation: Optional[RegulationResponse] = None
    clause: Optional[DocumentClauseResponse] = None

class AuditTrailResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    actor_id: str
    actor_name: Optional[str] = None
    timestamp: str
    metadata: Dict[str, Any]
    checksum: Optional[str] = None