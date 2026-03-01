import os
import hashlib
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class RegulationService:
    """Service for managing regulation and standard references"""
    
    def __init__(self, db):
        self.db = db
    
    async def create_regulation(self, regulation_data: Dict[str, Any], created_by: str) -> str:
        """Create new regulation reference
        
        Args:
            regulation_data: Regulation details
            created_by: User ID who created this
            
        Returns:
            Regulation ID
        """
        regulation_id = str(uuid.uuid4())
        
        regulation_doc = {
            'id': regulation_id,
            **regulation_data,
            'last_verified_at': datetime.now(timezone.utc).isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'created_by': created_by
        }
        
        await self.db.regulations.insert_one(regulation_doc)
        logger.info(f'Created regulation: {regulation_id}')
        
        return regulation_id
    
    async def list_regulations(self, filters: Optional[Dict] = None) -> List[Dict]:
        """List all regulations with optional filters"""
        query = filters or {}
        regulations = await self.db.regulations.find(query, {'_id': 0}).to_list(1000)
        return regulations
    
    async def get_regulation(self, regulation_id: str) -> Optional[Dict]:
        """Get regulation by ID"""
        return await self.db.regulations.find_one({'id': regulation_id}, {'_id': 0})
    
    async def seed_israeli_standards(self):
        """Seed common Israeli building standards"""
        standards = [
            {
                'source_name': 'מכון התקנים הישראלי',
                'source_url': 'https://www.sii.org.il',
                'standard_id': 'ת"י 1918',
                'title': 'בדיקת מבנים - דרישות כלליות',
                'description': 'תקן זה קובע את הדרישות הכלליות לבדיקת מבנים',
                'version_date': '2016-01-01'
            },
            {
                'source_name': 'מכון התקנים הישראלי',
                'source_url': 'https://www.sii.org.il',
                'standard_id': 'ת"י 466',
                'title': 'דלתות ותריסים - דרישות',
                'description': 'דרישות לדלתות, חלונות ותריסים במבני מגורים',
                'version_date': '2018-06-01'
            },
            {
                'source_name': 'משרד הבינוי והשיכון',
                'source_url': 'https://www.gov.il/he/departments/housing',
                'law_id': 'חוק המכר (דירות)',
                'section': 'תקנה 5',
                'title': 'תקופת בדק ואחריות',
                'description': '12 חודשי בדק, 7 שנות אחריות',
                'version_date': '1973-01-01'
            },
            {
                'source_name': 'תקנות התכנון והבניה',
                'source_url': 'https://www.nevo.co.il',
                'law_id': 'תקנות התכנון והבניה',
                'section': 'בידוד תרמי',
                'title': 'דרישות בידוד תרמי',
                'description': 'תקנות בידוד תרמי למבני מגורים',
                'version_date': '2020-01-01'
            }
        ]
        
        for std in standards:
            # Check if already exists
            existing = await self.db.regulations.find_one({
                '$or': [
                    {'standard_id': std.get('standard_id')},
                    {'law_id': std.get('law_id'), 'section': std.get('section')}
                ]
            })
            
            if not existing:
                await self.create_regulation(std, 'system')
                logger.info(f'Seeded standard: {std.get("standard_id") or std.get("law_id")}')

class CitationService:
    """Service for managing finding citations to regulations and clauses"""
    
    def __init__(self, db):
        self.db = db
        self.regulation_service = RegulationService(db)
    
    async def create_citation(
        self,
        finding_id: str,
        citation_data: Dict[str, Any],
        created_by: str
    ) -> str:
        """Create citation linking finding to regulation or clause
        
        Args:
            finding_id: Finding ID
            citation_data: Citation details (regulation_id, clause_id, type, confidence)
            created_by: User ID
            
        Returns:
            Citation ID
        """
        citation_id = str(uuid.uuid4())
        
        citation_doc = {
            'id': citation_id,
            'finding_id': finding_id,
            **citation_data,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'created_by': created_by
        }
        
        await self.db.finding_citations.insert_one(citation_doc)
        logger.info(f'Created citation: {citation_id} for finding: {finding_id}')
        
        return citation_id
    
    async def get_finding_citations(self, finding_id: str) -> List[Dict]:
        """Get all citations for a finding with enriched data"""
        citations = await self.db.finding_citations.find(
            {'finding_id': finding_id},
            {'_id': 0}
        ).to_list(1000)
        
        # Enrich with regulation and clause data
        for citation in citations:
            if citation.get('regulation_id'):
                regulation = await self.regulation_service.get_regulation(
                    citation['regulation_id']
                )
                citation['regulation'] = regulation
            
            if citation.get('clause_id'):
                clause = await self.db.document_clauses.find_one(
                    {'id': citation['clause_id']},
                    {'_id': 0}
                )
                citation['clause'] = clause
        
        return citations
    
    async def auto_suggest_citations(self, finding: Dict) -> List[Dict]:
        """Auto-suggest relevant regulations based on finding category
        
        Args:
            finding: Finding dict with category, description
            
        Returns:
            List of suggested citations with confidence
        """
        suggestions = []
        
        category_mapping = {
            'wall_damage': [{'standard_id': 'ת"י 1918', 'confidence': 'high'}],
            'door_issue': [{'standard_id': 'ת"י 466', 'confidence': 'high'}],
            'window_issue': [{'standard_id': 'ת"י 466', 'confidence': 'high'}],
            'floor_issue': [{'standard_id': 'ת"י 1918', 'confidence': 'medium'}],
            'cleanliness': [{'law_id': 'חוק המכר (דירות)', 'confidence': 'medium'}]
        }
        
        category = finding.get('category', '')
        mapped_regs = category_mapping.get(category, [])
        
        for reg_ref in mapped_regs:
            # Find regulation in database
            query = {}
            if reg_ref.get('standard_id'):
                query['standard_id'] = reg_ref['standard_id']
            elif reg_ref.get('law_id'):
                query['law_id'] = reg_ref['law_id']
            
            if query:
                regulation = await self.db.regulations.find_one(query, {'_id': 0})
                if regulation:
                    suggestions.append({
                        'regulation': regulation,
                        'confidence': reg_ref['confidence'],
                        'reason': f'Based on finding category: {category}'
                    })
        
        return suggestions