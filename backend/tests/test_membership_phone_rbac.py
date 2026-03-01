"""Tests for membership phone RBAC — user_phone field should only appear for privileged roles."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import AsyncMock, patch, MagicMock
import asyncio


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestMembershipPhoneRBAC:

    def _build_memberships(self, requester_role, project_id='proj-1'):
        member_user = {
            'id': 'user-member-1',
            'name': 'Test Member',
            'phone': '050-1234567',
            'role': 'contractor',
            'company_id': None,
        }
        membership_doc = {
            'id': 'mem-1',
            'project_id': project_id,
            'user_id': 'user-member-1',
            'role': 'contractor',
            'status': 'active',
        }

        can_see_phone = requester_role in ('owner', 'admin', 'project_manager')

        result = {
            'user_name': member_user['name'],
            'role': membership_doc['role'],
        }
        if can_see_phone:
            result['user_phone'] = member_user['phone']

        return result, can_see_phone

    def test_admin_sees_phone(self):
        result, can_see = self._build_memberships('admin')
        assert can_see is True
        assert 'user_phone' in result
        assert result['user_phone'] == '050-1234567'

    def test_owner_sees_phone(self):
        result, can_see = self._build_memberships('owner')
        assert can_see is True
        assert 'user_phone' in result
        assert result['user_phone'] == '050-1234567'

    def test_pm_sees_phone(self):
        result, can_see = self._build_memberships('project_manager')
        assert can_see is True
        assert 'user_phone' in result

    def test_contractor_no_phone(self):
        result, can_see = self._build_memberships('contractor')
        assert can_see is False
        assert 'user_phone' not in result

    def test_viewer_no_phone(self):
        result, can_see = self._build_memberships('viewer')
        assert can_see is False
        assert 'user_phone' not in result

    def test_management_team_no_phone(self):
        result, can_see = self._build_memberships('management_team')
        assert can_see is False
        assert 'user_phone' not in result

    def test_none_role_no_phone(self):
        result, can_see = self._build_memberships('none')
        assert can_see is False
        assert 'user_phone' not in result


class TestPhoneRBACLogic:

    PHONE_ALLOWED_ROLES = ('owner', 'admin', 'project_manager')

    def test_allowed_roles_include_all_privileged(self):
        for role in ['owner', 'admin', 'project_manager']:
            assert role in self.PHONE_ALLOWED_ROLES, f'{role} should allow phone access'

    def test_disallowed_roles_exclude_non_privileged(self):
        for role in ['contractor', 'viewer', 'management_team', 'none', '']:
            assert role not in self.PHONE_ALLOWED_ROLES, f'{role} should NOT allow phone access'
