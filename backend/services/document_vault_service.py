import os
import hashlib
import uuid
import logging
import mimetypes
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from pathlib import Path
import re
from services.object_storage import save_bytes as obj_save_bytes, generate_url as obj_generate_url, is_s3_mode

logger = logging.getLogger(__name__)

class DocumentVaultService:
    """Service for secure document storage with versioning and OCR"""
    
    def __init__(self, db, vault_dir: str = None):
        self.db = db
        if vault_dir is None:
            vault_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'document_vault')
        self.vault_dir = vault_dir
        os.makedirs(vault_dir, exist_ok=True)
    
    def calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b''):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    async def upload_document(
        self,
        inspection_id: str,
        document_type: str,
        file_data: bytes,
        filename: str,
        uploaded_by: str,
        description: Optional[str] = None
    ) -> str:
        """Upload document with versioning and checksum
        
        Args:
            inspection_id: Inspection ID
            document_type: Type of document (contract, specification, etc.)
            file_data: File bytes
            filename: Original filename
            uploaded_by: User ID
            description: Optional description
            
        Returns:
            Document ID
        """
        document_id = str(uuid.uuid4())
        
        # Determine version number
        existing_docs = await self.db.property_documents.count_documents({
            'inspection_id': inspection_id,
            'document_type': document_type
        })
        version = existing_docs + 1
        
        file_ext = Path(filename).suffix
        safe_filename = f"{document_id}_v{version}{file_ext}"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        stored_ref = obj_save_bytes(file_data, f"documents/{safe_filename}", content_type)

        checksum = hashlib.sha256(file_data).hexdigest()
        file_path = stored_ref
        
        # Store document metadata
        document_doc = {
            'id': document_id,
            'inspection_id': inspection_id,
            'document_type': document_type,
            'filename': filename,
            'file_path': file_path,
            'file_size': len(file_data),
            'checksum': checksum,
            'version': version,
            'uploaded_by': uploaded_by,
            'uploaded_at': datetime.now(timezone.utc).isoformat(),
            'description': description,
            'ocr_completed': False,
            'clause_count': 0
        }
        
        await self.db.property_documents.insert_one(document_doc)
        
        # Create audit trail
        await self._create_audit_trail(
            'property_document',
            document_id,
            'upload',
            uploaded_by,
            {
                'filename': filename,
                'document_type': document_type,
                'version': version,
                'file_size': len(file_data)
            },
            checksum
        )
        
        logger.info(f'Uploaded document: {document_id}, checksum: {checksum}')
        
        # Trigger OCR in background (simplified for MVP)
        # In production, this would be async task queue
        try:
            await self._extract_text_and_clauses(document_id, file_path, file_ext, file_data=file_data)
        except Exception as e:
            logger.error(f'OCR failed for {document_id}: {str(e)}')
        
        return document_id
    
    async def _extract_text_and_clauses(
        self,
        document_id: str,
        file_path: str,
        file_ext: str,
        file_data: bytes = None
    ):
        """Extract text and identify clauses from document
        
        Enhanced implementation for real PDF clause extraction
        """
        text_content = ""
        clauses = []
        
        try:
            if file_ext.lower() == '.pdf':
                try:
                    import io as _io
                    from PyPDF2 import PdfReader
                    if file_data:
                        reader = PdfReader(_io.BytesIO(file_data))
                    else:
                        reader = PdfReader(file_path)
                    
                    for page_num, page in enumerate(reader.pages, 1):
                        page_text = page.extract_text()
                        if not page_text:
                            continue
                            
                        text_content += page_text
                        
                        # Enhanced clause detection patterns
                        patterns = [
                            # Standard numbered clauses: 1.1, 1.2.3, etc.
                            r'(\d+\.\d+(?:\.\d+)?)\s+([^\n]{3,100})',
                            # Lettered clauses: א. ב. ג.
                            r'([א-ת])\.?\s+([^\n]{3,100})',
                            # Roman numerals: I. II. III.
                            r'([IVX]+)\.?\s+([^\n]{3,100})',
                            # Hebrew section markers: סעיף, פרק
                            r'(סעיף|פרק)\s+(\d+[א-ת]?)\s*[-:]\s*([^\n]{3,100})'
                        ]
                        
                        for pattern in patterns:
                            matches = re.finditer(pattern, page_text, re.MULTILINE)
                            
                            for match in matches:
                                if len(match.groups()) == 2:
                                    clause_number = match.group(1).strip()
                                    clause_title = match.group(2).strip()[:150]
                                else:
                                    # Pattern with 3 groups (Hebrew section markers)
                                    clause_number = f"{match.group(1)} {match.group(2)}"
                                    clause_title = match.group(3).strip()[:150]
                                
                                # Extract full clause text (next 300 chars)
                                start_pos = match.end()
                                clause_text = page_text[start_pos:start_pos+300].strip()
                                
                                # Remove newlines and extra spaces
                                clause_text = ' '.join(clause_text.split())
                                
                                # Calculate confidence based on clause quality
                                confidence = 'high'
                                if len(clause_text) < 50:
                                    confidence = 'medium'
                                if len(clause_title) < 10:
                                    confidence = 'low'
                                
                                clauses.append({
                                    'clause_number': clause_number,
                                    'section_title': clause_title,
                                    'clause_text': clause_text,
                                    'page_number': page_num,
                                    'confidence': confidence
                                })
                    
                    logger.info(f'Extracted {len(clauses)} clauses from {len(reader.pages)} pages')
                    
                except Exception as e:
                    logger.error(f'PDF extraction error: {str(e)}')
                    import traceback
                    traceback.print_exc()
            
            elif file_ext.lower() == '.docx':
                # DOCX text extraction (simplified)
                try:
                    import docx
                    doc = docx.Document(file_path)
                    for para in doc.paragraphs:
                        text_content += para.text + '\n'
                except Exception:
                    pass
            
            # Store extracted clauses
            if clauses:
                for clause_data in clauses:
                    await self._store_clause(document_id, clause_data)
                
                # Update document with clause count
                await self.db.property_documents.update_one(
                    {'id': document_id},
                    {'$set': {
                        'ocr_completed': True,
                        'clause_count': len(clauses),
                        'ocr_completed_at': datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                logger.info(f'Stored {len(clauses)} clauses for document {document_id}')
            else:
                # Mark OCR as completed even if no clauses found
                await self.db.property_documents.update_one(
                    {'id': document_id},
                    {'$set': {
                        'ocr_completed': True,
                        'clause_count': 0,
                        'ocr_completed_at': datetime.now(timezone.utc).isoformat()
                    }}
                )
        
        except Exception as e:
            logger.error(f'Text extraction failed for {document_id}: {str(e)}')
            import traceback
            traceback.print_exc()
    
    async def _store_clause(self, document_id: str, clause_data: Dict):
        """Store extracted clause"""
        clause_id = str(uuid.uuid4())
        
        clause_doc = {
            'id': clause_id,
            'document_id': document_id,
            **clause_data,
            'extracted_at': datetime.now(timezone.utc).isoformat()
        }
        
        await self.db.document_clauses.insert_one(clause_doc)
    
    async def get_document(self, document_id: str) -> Optional[Dict]:
        """Get document metadata"""
        return await self.db.property_documents.find_one(
            {'id': document_id},
            {'_id': 0}
        )
    
    async def list_documents(self, inspection_id: str) -> List[Dict]:
        """List all documents for an inspection"""
        return await self.db.property_documents.find(
            {'inspection_id': inspection_id},
            {'_id': 0}
        ).to_list(1000)
    
    async def get_document_clauses(self, document_id: str) -> List[Dict]:
        """Get all clauses from a document"""
        return await self.db.document_clauses.find(
            {'document_id': document_id},
            {'_id': 0}
        ).to_list(1000)
    
    async def search_clauses(
        self,
        inspection_id: str,
        search_term: str
    ) -> List[Dict]:
        """Search clauses across all documents for an inspection"""
        # Get all documents for this inspection
        documents = await self.list_documents(inspection_id)
        doc_ids = [doc['id'] for doc in documents]
        
        if not doc_ids:
            return []
        
        # Search clauses
        clauses = await self.db.document_clauses.find({
            'document_id': {'$in': doc_ids},
            '$or': [
                {'clause_text': {'$regex': search_term, '$options': 'i'}},
                {'section_title': {'$regex': search_term, '$options': 'i'}}
            ]
        }, {'_id': 0}).to_list(100)
        
        return clauses
    
    def generate_signed_url(
        self,
        document_id: str,
        expires_in: int = 3600
    ) -> str:
        """Generate time-limited signed URL for secure document access
        
        Args:
            document_id: Document ID
            expires_in: Expiration time in seconds (default 1 hour)
            
        Returns:
            Signed URL with expiration
        """
        import time
        import hmac
        
        # Calculate expiration timestamp
        expires_at = int(time.time()) + expires_in
        
        from config import JWT_SECRET
        message = f"{document_id}:{expires_at}".encode('utf-8')
        signature = hmac.new(
            JWT_SECRET.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()
        
        signed_url = f"/api/documents/{document_id}/download?expires={expires_at}&signature={signature}"
        
        return signed_url
    
    def verify_signed_url(
        self,
        document_id: str,
        expires_at: int,
        signature: str
    ) -> bool:
        """Verify signed URL is valid and not expired
        
        Args:
            document_id: Document ID
            expires_at: Expiration timestamp
            signature: URL signature
            
        Returns:
            True if valid, False otherwise
        """
        import time
        import hmac
        
        # Check expiration
        if int(time.time()) > expires_at:
            logger.warning(f'Signed URL expired for document {document_id}')
            return False
        
        from config import JWT_SECRET
        message = f"{document_id}:{expires_at}".encode('utf-8')
        expected_signature = hmac.new(
            JWT_SECRET.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()
        
        if signature != expected_signature:
            logger.warning(f'Invalid signature for document {document_id}')
            return False
        
        return True
    
    async def _create_audit_trail(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str,
        metadata: Dict,
        checksum: Optional[str] = None
    ):
        """Create immutable audit trail entry"""
        audit_id = str(uuid.uuid4())
        
        audit_doc = {
            'id': audit_id,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'action': action,
            'actor_id': actor_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metadata': metadata,
            'checksum': checksum
        }
        
        await self.db.audit_trail.insert_one(audit_doc)
    
    async def get_audit_trail(
        self,
        entity_type: str,
        entity_id: str
    ) -> List[Dict]:
        """Get audit trail for an entity"""
        return await self.db.audit_trail.find(
            {'entity_type': entity_type, 'entity_id': entity_id},
            {'_id': 0}
        ).sort('timestamp', -1).to_list(1000)