import uuid
from datetime import datetime, timezone
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class AuditService:
    def __init__(self, db):
        self.db = db
    
    async def log(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        user_id: str,
        changes: Dict[str, Any]
    ) -> str:
        """Log an audit event"""
        try:
            audit_id = str(uuid.uuid4())
            audit_doc = {
                'id': audit_id,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'action': action,
                'user_id': user_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'changes': changes
            }
            
            await self.db.audit_logs.insert_one(audit_doc)
            return audit_id
        
        except Exception as e:
            logger.error(f'Audit logging error: {str(e)}')
            return ''