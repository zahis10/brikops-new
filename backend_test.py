#!/usr/bin/env python3
"""
BedekPro Backend API Testing Suite
Tests all API endpoints with proper authentication and role-based access
"""

import requests
import sys
import json
import base64
from datetime import datetime
from typing import Dict, Any, Optional

class BedekProAPITester:
    def __init__(self, base_url="https://bedekpro-inspect.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tokens = {}  # Store tokens for different users
        self.test_data = {}  # Store created test data
        self.tests_run = 0
        self.tests_passed = 0
        
        # Demo credentials
        self.credentials = {
            'tenant': {'email': 'tenant@bedekpro.com', 'password': 'tenant123'},
            'reviewer': {'email': 'reviewer@bedekpro.com', 'password': 'reviewer123'},
            'admin': {'email': 'admin@bedekpro.com', 'password': 'admin123'}
        }

    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}: PASSED {details}")
        else:
            print(f"❌ {name}: FAILED {details}")

    def make_request(self, method: str, endpoint: str, data: Dict = None, 
                    files: Dict = None, role: str = None, expected_status: int = 200) -> tuple:
        """Make HTTP request with optional authentication"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {'Content-Type': 'application/json'}
        
        if role and role in self.tokens:
            headers['Authorization'] = f'Bearer {self.tokens[role]}'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    # Remove Content-Type for file uploads
                    headers.pop('Content-Type', None)
                    response = requests.post(url, data=data, files=files, headers=headers)
                else:
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            success = response.status_code == expected_status
            response_data = {}
            
            try:
                response_data = response.json()
            except:
                response_data = {'text': response.text}
            
            return success, response_data, response.status_code
            
        except Exception as e:
            return False, {'error': str(e)}, 0

    def test_authentication(self):
        """Test authentication for all user roles"""
        print("\n🔐 Testing Authentication...")
        
        for role, creds in self.credentials.items():
            success, response, status = self.make_request(
                'POST', '/auth/login', 
                data=creds, 
                expected_status=200
            )
            
            if success and 'token' in response:
                self.tokens[role] = response['token']
                self.log_test(f"Login as {role}", True, f"Token received")
            else:
                self.log_test(f"Login as {role}", False, f"Status: {status}, Response: {response}")

    def test_user_profile(self):
        """Test getting user profile"""
        print("\n👤 Testing User Profiles...")
        
        for role in self.tokens.keys():
            success, response, status = self.make_request(
                'GET', '/auth/me', 
                role=role, 
                expected_status=200
            )
            
            if success and 'email' in response:
                self.log_test(f"Get {role} profile", True, f"Email: {response['email']}")
            else:
                self.log_test(f"Get {role} profile", False, f"Status: {status}")

    def test_property_creation(self):
        """Test property creation (tenant only)"""
        print("\n🏠 Testing Property Creation...")
        
        property_data = {
            'address': 'רחוב הרצל 123, תל אביב',
            'apt_number': '5א'
        }
        
        success, response, status = self.make_request(
            'POST', '/properties',
            data=property_data,
            role='tenant',
            expected_status=200
        )
        
        if success and 'id' in response:
            self.test_data['property_id'] = response['id']
            self.log_test("Create property", True, f"Property ID: {response['id']}")
        else:
            self.log_test("Create property", False, f"Status: {status}, Response: {response}")

    def test_inspection_creation(self):
        """Test inspection creation"""
        print("\n📋 Testing Inspection Creation...")
        
        if 'property_id' not in self.test_data:
            self.log_test("Create inspection", False, "No property ID available")
            return
        
        inspection_data = {
            'property_id': self.test_data['property_id'],
            'handover_date': '2024-12-31'
        }
        
        success, response, status = self.make_request(
            'POST', '/inspections',
            data=inspection_data,
            role='tenant',
            expected_status=200
        )
        
        if success and 'id' in response:
            self.test_data['inspection_id'] = response['id']
            self.log_test("Create inspection", True, f"Inspection ID: {response['id']}")
        else:
            self.log_test("Create inspection", False, f"Status: {status}, Response: {response}")

    def test_room_creation(self):
        """Test room creation"""
        print("\n🚪 Testing Room Creation...")
        
        if 'inspection_id' not in self.test_data:
            self.log_test("Create room", False, "No inspection ID available")
            return
        
        rooms = [
            {'room_type': 'living_room', 'name': 'סלון', 'min_media_count': 3},
            {'room_type': 'kitchen', 'name': 'מטבח', 'min_media_count': 3},
            {'room_type': 'bedroom', 'name': 'חדר שינה', 'min_media_count': 3}
        ]
        
        self.test_data['room_ids'] = []
        
        for room_data in rooms:
            room_data['inspection_id'] = self.test_data['inspection_id']
            
            success, response, status = self.make_request(
                'POST', '/rooms',
                data=room_data,
                role='tenant',
                expected_status=200
            )
            
            if success and 'id' in response:
                self.test_data['room_ids'].append(response['id'])
                self.log_test(f"Create room {room_data['name']}", True, f"Room ID: {response['id']}")
            else:
                self.log_test(f"Create room {room_data['name']}", False, f"Status: {status}")

    def create_test_image(self) -> str:
        """Create a simple test image in base64 format"""
        # Create a simple 100x100 PNG image with some pattern
        from PIL import Image, ImageDraw
        import io
        
        # Create image with some visual features (not solid color)
        img = Image.new('RGB', (100, 100), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add some visual features
        draw.rectangle([10, 10, 90, 90], outline='black', width=2)
        draw.line([10, 10, 90, 90], fill='red', width=2)
        draw.line([90, 10, 10, 90], fill='blue', width=2)
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_data = buffer.getvalue()
        
        return base64.b64encode(img_data).decode('utf-8')

    def test_media_upload(self):
        """Test media upload to rooms"""
        print("\n📸 Testing Media Upload...")
        
        if not self.test_data.get('room_ids'):
            self.log_test("Upload media", False, "No room IDs available")
            return
        
        try:
            # Create test image
            test_image_b64 = self.create_test_image()
            
            # Convert base64 to file-like object for upload
            import io
            image_data = base64.b64decode(test_image_b64)
            
            for room_id in self.test_data['room_ids'][:1]:  # Test with first room only
                files = {
                    'file': ('test_image.png', io.BytesIO(image_data), 'image/png')
                }
                data = {
                    'room_id': room_id
                }
                
                success, response, status = self.make_request(
                    'POST', '/media/upload',
                    data=data,
                    files=files,
                    role='tenant',
                    expected_status=200
                )
                
                if success and 'id' in response:
                    self.log_test(f"Upload media to room", True, f"Media ID: {response['id']}")
                else:
                    self.log_test(f"Upload media to room", False, f"Status: {status}, Response: {response}")
                break
                
        except Exception as e:
            self.log_test("Upload media", False, f"Error: {str(e)}")

    def test_inspection_analysis(self):
        """Test AI analysis of inspection"""
        print("\n🤖 Testing AI Analysis...")
        
        if 'inspection_id' not in self.test_data:
            self.log_test("AI Analysis", False, "No inspection ID available")
            return
        
        success, response, status = self.make_request(
            'POST', f'/inspections/{self.test_data["inspection_id"]}/analyze',
            role='tenant',
            expected_status=200
        )
        
        if success:
            self.log_test("AI Analysis", True, f"Findings: {response.get('findings_count', 0)}")
        else:
            self.log_test("AI Analysis", False, f"Status: {status}, Response: {response}")

    def test_inspection_listing(self):
        """Test listing inspections for different roles"""
        print("\n📋 Testing Inspection Listing...")
        
        for role in ['tenant', 'reviewer', 'admin']:
            if role not in self.tokens:
                continue
                
            success, response, status = self.make_request(
                'GET', '/inspections',
                role=role,
                expected_status=200
            )
            
            if success and isinstance(response, list):
                self.log_test(f"List inspections ({role})", True, f"Count: {len(response)}")
            else:
                self.log_test(f"List inspections ({role})", False, f"Status: {status}")

    def test_inspection_detail(self):
        """Test getting inspection details"""
        print("\n🔍 Testing Inspection Details...")
        
        if 'inspection_id' not in self.test_data:
            self.log_test("Get inspection detail", False, "No inspection ID available")
            return
        
        success, response, status = self.make_request(
            'GET', f'/inspections/{self.test_data["inspection_id"]}',
            role='tenant',
            expected_status=200
        )
        
        if success and 'id' in response:
            self.log_test("Get inspection detail", True, f"Rooms: {len(response.get('rooms', []))}")
        else:
            self.log_test("Get inspection detail", False, f"Status: {status}")

    def test_admin_endpoints(self):
        """Test admin-only endpoints"""
        print("\n👑 Testing Admin Endpoints...")
        
        if 'admin' not in self.tokens:
            self.log_test("Admin endpoints", False, "No admin token available")
            return
        
        # Test user listing
        success, response, status = self.make_request(
            'GET', '/admin/users',
            role='admin',
            expected_status=200
        )
        
        if success and isinstance(response, list):
            self.log_test("List users (admin)", True, f"Users: {len(response)}")
        else:
            self.log_test("List users (admin)", False, f"Status: {status}")

    def test_unauthorized_access(self):
        """Test unauthorized access scenarios"""
        print("\n🚫 Testing Unauthorized Access...")
        
        # Test tenant trying to access admin endpoint
        success, response, status = self.make_request(
            'GET', '/admin/users',
            role='tenant',
            expected_status=403
        )
        
        if status == 403:
            self.log_test("Tenant blocked from admin endpoint", True, "403 Forbidden")
        else:
            self.log_test("Tenant blocked from admin endpoint", False, f"Status: {status}")

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting BedekPro Backend API Tests")
        print(f"Base URL: {self.base_url}")
        print("=" * 60)
        
        try:
            # Import PIL for image creation
            from PIL import Image, ImageDraw
        except ImportError:
            print("⚠️  PIL not available, skipping image upload tests")
        
        # Run tests in order
        self.test_authentication()
        self.test_user_profile()
        self.test_property_creation()
        self.test_inspection_creation()
        self.test_room_creation()
        
        # Only test media upload if PIL is available
        try:
            from PIL import Image
            self.test_media_upload()
        except ImportError:
            print("⚠️  Skipping media upload test (PIL not available)")
        
        self.test_inspection_analysis()
        self.test_inspection_listing()
        self.test_inspection_detail()
        self.test_admin_endpoints()
        self.test_unauthorized_access()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print(f"❌ {self.tests_run - self.tests_passed} tests failed")
            return 1

def main():
    tester = BedekProAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())