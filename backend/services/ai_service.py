import os
import base64
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType, ImageContent
except ImportError:
    LlmChat = None
    UserMessage = None
    FileContentWithMimeType = None
    ImageContent = None

load_dotenv()
logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not self.api_key:
            logger.warning('EMERGENT_LLM_KEY not found in environment')
    
    async def analyze_room(self, room: Dict[str, Any], media: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze room media and generate findings"""
        try:
            if not self.api_key:
                return self._mock_findings(room)
            
            # Initialize Claude Sonnet 4.6 chat
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"room_analysis_{room['id']}",
                system_message="""
You are an expert property inspector analyzing room conditions for a handover inspection.
Analyze the provided images and identify any issues, damage, or concerns.

For each finding, provide:
1. category (e.g., 'wall_damage', 'floor_issue', 'ceiling_stain', 'fixture_damage', 'cleanliness')
2. description (detailed description in Hebrew)
3. severity (low, medium, high)
4. confidence (low, medium, high) based on image quality and visibility

If image quality is poor or evidence is insufficient, mark confidence as 'low' and mention this in the description.

Respond in JSON format:
{
  "findings": [
    {
      "category": "wall_damage",
      "description": "סדק בקיר...",
      "severity": "medium",
      "confidence": "high"
    }
  ]
}

If no issues found, return empty findings array.
"""
            ).with_model('anthropic', 'claude-sonnet-4-5-20250929')
            
            # Prepare message with images
            message_text = f"Analyze this {room['room_type']} room: {room['name']}. Identify any issues or damage."
            
            # For MVP, we'll use base64 encoded images
            # In production, we'd load actual image files
            file_contents = []
            
            # For now, create mock analysis since we don't have actual images yet
            # In production: load images from file_url and encode
            
            # Send to AI
            # response = await chat.send_message(UserMessage(
            #     text=message_text,
            #     file_contents=file_contents
            # ))
            
            # For MVP, return mock findings
            return self._mock_findings(room)
        
        except Exception as e:
            logger.error(f'AI analysis error: {str(e)}')
            return self._mock_findings(room)
    
    def _mock_findings(self, room: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate mock findings for testing"""
        findings = []
        
        if room['room_type'] == 'living_room':
            findings.append({
                'category': 'wall_damage',
                'description': 'סדק קל בקיר ליד החלון',
                'severity': 'low',
                'confidence': 'high',
                'raw_response': 'Mock AI response'
            })
        elif room['room_type'] == 'kitchen':
            findings.append({
                'category': 'fixture_damage',
                'description': 'שריטות על משטח העבודה',
                'severity': 'medium',
                'confidence': 'high',
                'raw_response': 'Mock AI response'
            })
        elif room['room_type'] == 'bathroom':
            findings.append({
                'category': 'cleanliness',
                'description': 'כתמי אבנית על הברזים',
                'severity': 'low',
                'confidence': 'medium',
                'raw_response': 'Mock AI response'
            })
        
        return findings