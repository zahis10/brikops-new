import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
import bcrypt
from datetime import datetime, timezone
import uuid

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def seed_database():
    app_mode = os.environ.get('APP_MODE', 'dev')
    run_seed = os.environ.get('RUN_SEED', '').lower()
    if app_mode == 'prod':
        print("FATAL: seed_data.py CANNOT run in production (APP_MODE=prod). Aborting.")
        sys.exit(1)
    if run_seed != 'true':
        print("FATAL: seed_data.py requires RUN_SEED=true. Usage: RUN_SEED=true python seed_data.py")
        sys.exit(1)
    print(f"Starting database seeding... (APP_MODE={app_mode}, RUN_SEED={run_seed})")
    
    await db.users.delete_many({})
    await db.properties.delete_many({})
    await db.inspections.delete_many({})
    await db.rooms.delete_many({})
    await db.media_assets.delete_many({})
    await db.findings.delete_many({})
    await db.ai_assessments.delete_many({})
    await db.expert_reviews.delete_many({})
    await db.reports.delete_many({})
    await db.audit_logs.delete_many({})
    
    print("Cleared existing data")
    
    # Create users
    tenant_id = str(uuid.uuid4())
    reviewer_id = str(uuid.uuid4())
    admin_id = str(uuid.uuid4())
    
    users = [
        {
            'id': tenant_id,
            'email': 'tenant@bedekpro.com',
            'password_hash': hash_password('tenant123'),
            'name': 'יוסי כהן',
            'phone': '050-1234567',
            'role': 'tenant',
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'id': reviewer_id,
            'email': 'reviewer@bedekpro.com',
            'password_hash': hash_password('reviewer123'),
            'name': 'דני לוי',
            'phone': '052-9876543',
            'role': 'reviewer',
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'id': admin_id,
            'email': 'admin@bedekpro.com',
            'password_hash': hash_password('admin123'),
            'name': 'מיכל אברהם',
            'phone': '054-5555555',
            'role': 'admin',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
    ]
    
    await db.users.insert_many(users)
    print(f"Created {len(users)} users")
    
    # Create properties
    property_id_1 = str(uuid.uuid4())
    property_id_2 = str(uuid.uuid4())
    
    properties = [
        {
            'id': property_id_1,
            'address': 'רחוב הרצל 15, תל אביב',
            'apt_number': '12',
            'tenant_id': tenant_id,
            'created_at': datetime.now(timezone.utc).isoformat()
        },
        {
            'id': property_id_2,
            'address': 'שדרות בן גוריון 42, חיפה',
            'apt_number': '5',
            'tenant_id': tenant_id,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
    ]
    
    await db.properties.insert_many(properties)
    print(f"Created {len(properties)} properties")
    
    # Create demo inspection (complete workflow)
    inspection_id = str(uuid.uuid4())
    
    inspection = {
        'id': inspection_id,
        'property_id': property_id_1,
        'tenant_id': tenant_id,
        'status': 'approved',
        'handover_date': '2024-02-15',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.inspections.insert_one(inspection)
    print(f"Created demo inspection: {inspection_id}")
    
    # Create rooms for demo inspection
    room_ids = []
    rooms_data = [
        {'room_type': 'living_room', 'name': 'סלון'},
        {'room_type': 'kitchen', 'name': 'מטבח'},
        {'room_type': 'bathroom', 'name': 'חדר אמבטיה'},
        {'room_type': 'bedroom', 'name': 'חדר שינה ראשי'}
    ]
    
    for room_data in rooms_data:
        room_id = str(uuid.uuid4())
        room_ids.append(room_id)
        
        room = {
            'id': room_id,
            'inspection_id': inspection_id,
            'room_type': room_data['room_type'],
            'name': room_data['name'],
            'min_media_count': 3,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        await db.rooms.insert_one(room)
        
        # Create mock media for each room
        for i in range(3):
            media_id = str(uuid.uuid4())
            media = {
                'id': media_id,
                'room_id': room_id,
                'file_url': f'/uploads/demo_{room_id}_{i}.jpg',
                'thumbnail_url': f'/uploads/thumb_demo_{room_id}_{i}.jpg',
                'type': 'image',
                'metadata': {
                    'filename': f'room_{room_data["name"]}_{i}.jpg',
                    'content_type': 'image/jpeg',
                    'uploaded_by': tenant_id
                },
                'uploaded_at': datetime.now(timezone.utc).isoformat()
            }
            await db.media_assets.insert_one(media)
    
    print(f"Created {len(rooms_data)} rooms with media")
    
    # Create findings for demo inspection
    findings_data = [
        {
            'room_id': room_ids[0],  # Living room
            'category': 'wall_damage',
            'description': 'סדק קל בקיר ליד החלון, באורך כ-15 ס"מ',
            'severity': 'low',
            'confidence': 'high',
            'status': 'approved'
        },
        {
            'room_id': room_ids[1],  # Kitchen
            'category': 'fixture_damage',
            'description': 'שריטות על משטח העבודה, נראות בירור בתאורה טבעית',
            'severity': 'medium',
            'confidence': 'high',
            'status': 'approved'
        },
        {
            'room_id': room_ids[2],  # Bathroom
            'category': 'cleanliness',
            'description': 'כתמי אבנית על ברזי האמבטיה, דורשים ניקוי מעמיק',
            'severity': 'low',
            'confidence': 'medium',
            'status': 'approved'
        },
        {
            'room_id': room_ids[3],  # Bedroom
            'category': 'floor_issue',
            'description': 'שריטה בפרקט ליד הכניסה, באורך כ-20 ס"מ',
            'severity': 'medium',
            'confidence': 'high',
            'status': 'approved'
        }
    ]
    
    for finding_data in findings_data:
        finding_id = str(uuid.uuid4())
        finding = {
            'id': finding_id,
            **finding_data,
            'ai_generated': True,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        await db.findings.insert_one(finding)
        
        # Create AI assessment
        assessment_id = str(uuid.uuid4())
        assessment = {
            'id': assessment_id,
            'finding_id': finding_id,
            'raw_response': 'AI analysis detected this issue with high confidence',
            'confidence_score': finding_data['confidence'],
            'model_used': 'claude-sonnet-4-5-20250929',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        await db.ai_assessments.insert_one(assessment)
        
        # Create expert review
        review_id = str(uuid.uuid4())
        review = {
            'id': review_id,
            'finding_id': finding_id,
            'reviewer_id': reviewer_id,
            'status': 'approved',
            'comments': 'אושר על ידי מומחה. הממצא מדויק ומתועד היטב.',
            'reviewed_at': datetime.now(timezone.utc).isoformat()
        }
        await db.expert_reviews.insert_one(review)
    
    print(f"Created {len(findings_data)} findings with assessments and reviews")
    
    # Create report
    report_id = str(uuid.uuid4())
    report = {
        'id': report_id,
        'inspection_id': inspection_id,
        'pdf_url': f'/reports/inspection_{inspection_id}.pdf',
        'generated_by': reviewer_id,
        'generated_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.reports.insert_one(report)
    print(f"Created report: {report_id}")
    
    # Create draft inspection for testing
    draft_inspection_id = str(uuid.uuid4())
    draft_property_id = str(uuid.uuid4())
    
    draft_property = {
        'id': draft_property_id,
        'address': 'רחוב דיזנגוף 100, תל אביב',
        'apt_number': '25',
        'tenant_id': tenant_id,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    await db.properties.insert_one(draft_property)
    
    draft_inspection = {
        'id': draft_inspection_id,
        'property_id': draft_property_id,
        'tenant_id': tenant_id,
        'status': 'draft',
        'handover_date': '2024-03-01',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    await db.inspections.insert_one(draft_inspection)
    print(f"Created draft inspection for testing: {draft_inspection_id}")
    
    print("\\nSeeding complete!")
    print("\\n=== Demo Credentials ===")
    print("Tenant:   tenant@bedekpro.com / tenant123")
    print("Reviewer: reviewer@bedekpro.com / reviewer123")
    print("Admin:    admin@bedekpro.com / admin123")
    print("========================")
    
    client.close()

if __name__ == '__main__':
    asyncio.run(seed_database())
