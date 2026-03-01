\"\"\"
API endpoints for Regulation + Contract Intelligence Gate

Add these routes to server.py
\"\"\"

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Optional, List
import uuid
from datetime import datetime, timezone

from models_extended import (
    RegulationCreate, RegulationResponse,
    DocumentUpload, DocumentResponse, DocumentClauseResponse,
    FindingCitationCreate, FindingCitationResponse,
    AuditTrailResponse
)
from services.regulation_service import RegulationService, CitationService
from services.document_vault_service import DocumentVaultService

# Initialize services (add to server.py after db initialization)
regulation_service = RegulationService(db)
citation_service = CitationService(db)
document_vault_service = DocumentVaultService(db)

# Regulation endpoints
@api_router.post(\"/regulations\", response_model=RegulationResponse)
async def create_regulation(\n    regulation: RegulationCreate,\n    user: dict = Depends(require_role(['admin', 'reviewer']))\n):
    \"\"\"Create new regulation or standard reference\"\"\"
    regulation_id = await regulation_service.create_regulation(\n        regulation.dict(exclude_unset=True),\n        user['id']\n    )
    
    created = await regulation_service.get_regulation(regulation_id)
    return RegulationResponse(**created)

@api_router.get(\"/regulations\", response_model=List[RegulationResponse])
async def list_regulations(\n    standard_id: Optional[str] = None,\n    law_id: Optional[str] = None,\n    user: dict = Depends(get_current_user)\n):
    \"\"\"List all regulations with optional filters\"\"\"
    filters = {}
    if standard_id:
        filters['standard_id'] = standard_id
    if law_id:
        filters['law_id'] = law_id
    
    regulations = await regulation_service.list_regulations(filters)
    return [RegulationResponse(**reg) for reg in regulations]

@api_router.get(\"/regulations/{regulation_id}\", response_model=RegulationResponse)
async def get_regulation(\n    regulation_id: str,\n    user: dict = Depends(get_current_user)\n):
    \"\"\"Get specific regulation by ID\"\"\"
    regulation = await regulation_service.get_regulation(regulation_id)
    if not regulation:
        raise HTTPException(status_code=404, detail='Regulation not found')
    return RegulationResponse(**regulation)

# Document vault endpoints
@api_router.post(\"/documents/upload\", response_model=DocumentResponse)
async def upload_document(\n    inspection_id: str = Form(...),\n    document_type: str = Form(...),\n    description: Optional[str] = Form(None),\n    file: UploadFile = File(...),\n    user: dict = Depends(get_current_user)\n):
    \"\"\"Upload property document with versioning and checksum\"\"\"
    # Validate inspection exists
    inspection = await db.inspections.find_one({'id': inspection_id}, {'_id': 0})
    if not inspection:
        raise HTTPException(status_code=404, detail='Inspection not found')
    
    # Read file data
    file_data = await file.read()
    
    # Upload document
    document_id = await document_vault_service.upload_document(\n        inspection_id,\n        document_type,\n        file_data,\n        file.filename,\n        user['id'],\n        description\n    )
    
    # Get created document
    document = await document_vault_service.get_document(document_id)
    return DocumentResponse(**document)

@api_router.get(\"/documents/inspection/{inspection_id}\", response_model=List[DocumentResponse])
async def list_inspection_documents(\n    inspection_id: str,\n    user: dict = Depends(get_current_user)\n):
    \"\"\"List all documents for an inspection\"\"\"
    documents = await document_vault_service.list_documents(inspection_id)
    return [DocumentResponse(**doc) for doc in documents]

@api_router.get(\"/documents/{document_id}\", response_model=DocumentResponse)
async def get_document(\n    document_id: str,\n    user: dict = Depends(get_current_user)\n):
    \"\"\"Get document metadata\"\"\"
    document = await document_vault_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail='Document not found')
    return DocumentResponse(**document)

@api_router.get(\"/documents/{document_id}/clauses\", response_model=List[DocumentClauseResponse])
async def get_document_clauses(\n    document_id: str,\n    user: dict = Depends(get_current_user)\n):
    \"\"\"Get all extracted clauses from document\"\"\"
    clauses = await document_vault_service.get_document_clauses(document_id)
    return [DocumentClauseResponse(**clause) for clause in clauses]

@api_router.get(\"/documents/{document_id}/download\")
async def download_document(\n    document_id: str,\n    token: str,\n    user: dict = Depends(get_current_user)\n):
    \"\"\"Download document file (secured with token)\"\"\"
    document = await document_vault_service.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail='Document not found')
    
    file_path = document.get('file_path', '')
    if file_path.startswith('s3://'):
        from services.object_storage import generate_url as obj_generate_url
        from starlette.responses import RedirectResponse
        presigned_url = obj_generate_url(file_path)
        return RedirectResponse(url=presigned_url)
    else:
        from fastapi.responses import FileResponse
        return FileResponse(\n        file_path,\n        filename=document['filename'],\n        media_type='application/octet-stream'\n    )

# Citation endpoints
@api_router.post(\"/findings/{finding_id}/citations\", response_model=FindingCitationResponse)
async def create_finding_citation(\n    finding_id: str,\n    citation: FindingCitationCreate,\n    user: dict = Depends(get_current_user)\n):
    \"\"\"Link finding to regulation or contract clause\"\"\"
    # Validate finding exists
    finding = await db.findings.find_one({'id': finding_id}, {'_id': 0})
    if not finding:
        raise HTTPException(status_code=404, detail='Finding not found')
    
    # Create citation
    citation_id = await citation_service.create_citation(\n        finding_id,\n        citation.dict(exclude_unset=True),\n        user['id']\n    )
    
    # Get created citation with enriched data
    citations = await citation_service.get_finding_citations(finding_id)
    created = next((c for c in citations if c['id'] == citation_id), None)
    
    if not created:
        raise HTTPException(status_code=500, detail='Failed to retrieve citation')
    
    return FindingCitationResponse(**created)

@api_router.get(\"/findings/{finding_id}/citations\", response_model=List[FindingCitationResponse])
async def get_finding_citations(\n    finding_id: str,\n    user: dict = Depends(get_current_user)\n):
    \"\"\"Get all citations for a finding\"\"\"
    citations = await citation_service.get_finding_citations(finding_id)
    return [FindingCitationResponse(**citation) for citation in citations]

@api_router.get(\"/findings/{finding_id}/citations/suggestions\")
async def get_citation_suggestions(\n    finding_id: str,\n    user: dict = Depends(get_current_user)\n):
    \"\"\"Get auto-suggested citations for a finding\"\"\"
    finding = await db.findings.find_one({'id': finding_id}, {'_id': 0})
    if not finding:
        raise HTTPException(status_code=404, detail='Finding not found')
    
    suggestions = await citation_service.auto_suggest_citations(finding)
    return {'finding_id': finding_id, 'suggestions': suggestions}

# Audit trail endpoints
@api_router.get(\"/audit-trail/{entity_type}/{entity_id}\", response_model=List[AuditTrailResponse])
async def get_entity_audit_trail(\n    entity_type: str,\n    entity_id: str,\n    user: dict = Depends(require_role(['admin', 'reviewer']))\n):
    \"\"\"Get immutable audit trail for an entity\"\"\"
    audit_trail = await document_vault_service.get_audit_trail(entity_type, entity_id)
    
    # Enrich with actor names
    for entry in audit_trail:
        actor = await db.users.find_one({'id': entry['actor_id']}, {'_id': 0})
        if actor:
            entry['actor_name'] = actor.get('name', 'Unknown')
    
    return [AuditTrailResponse(**entry) for entry in audit_trail]

# Initialize regulations on startup
@app.on_event('startup')
async def seed_regulations():
    \"\"\"Seed Israeli building standards on startup\"\"\"
    try:
        await regulation_service.seed_israeli_standards()
        logger.info('Seeded Israeli building standards')
    except Exception as e:
        logger.error(f'Failed to seed standards: {str(e)}')
