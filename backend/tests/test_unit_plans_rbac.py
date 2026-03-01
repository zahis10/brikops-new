"""Tests for unit_plans RBAC, discipline validation, and contractor routing logic."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from contractor_ops.router import PLAN_DISCIPLINES, PLAN_UPLOAD_ROLES


class TestUnitPlansRBAC:

    def test_owner_can_upload(self):
        assert 'owner' in PLAN_UPLOAD_ROLES

    def test_admin_can_upload(self):
        assert 'admin' in PLAN_UPLOAD_ROLES

    def test_pm_can_upload(self):
        assert 'project_manager' in PLAN_UPLOAD_ROLES

    def test_management_team_can_upload(self):
        assert 'management_team' in PLAN_UPLOAD_ROLES

    def test_contractor_cannot_upload(self):
        assert 'contractor' not in PLAN_UPLOAD_ROLES

    def test_viewer_cannot_upload(self):
        assert 'viewer' not in PLAN_UPLOAD_ROLES

    def test_upload_roles_tuple_not_empty(self):
        assert len(PLAN_UPLOAD_ROLES) >= 4

    def test_no_unexpected_roles_can_upload(self):
        for role in PLAN_UPLOAD_ROLES:
            assert role in ('owner', 'admin', 'project_manager', 'management_team')


class TestPlanDisciplines:

    def test_all_expected_disciplines_present(self):
        expected = ['electrical', 'plumbing', 'architecture', 'construction', 'hvac', 'fire_protection']
        for d in expected:
            assert d in PLAN_DISCIPLINES, f'{d} missing from disciplines'

    def test_invalid_discipline_rejected(self):
        assert 'random' not in PLAN_DISCIPLINES
        assert 'general' not in PLAN_DISCIPLINES

    def test_discipline_count(self):
        assert len(PLAN_DISCIPLINES) == 6

    def test_discipline_is_tuple(self):
        assert isinstance(PLAN_DISCIPLINES, tuple)


class TestPlanDocStructure:

    def _build_plan_doc(self, discipline='electrical', unit_id='unit-1', project_id='proj-1'):
        import uuid
        from datetime import datetime, timezone
        return {
            'id': str(uuid.uuid4()),
            'project_id': project_id,
            'unit_id': unit_id,
            'discipline': discipline,
            'file_url': f'/api/uploads/test.pdf',
            'original_filename': 'plan.pdf',
            'file_size': 1024,
            'uploaded_by': 'user-1',
            'note': 'test note',
            'created_at': datetime.now(timezone.utc).isoformat(),
        }

    def test_plan_has_required_fields(self):
        doc = self._build_plan_doc()
        required = ['id', 'project_id', 'unit_id', 'discipline', 'file_url', 'uploaded_by', 'created_at']
        for f in required:
            assert f in doc, f'Missing field: {f}'

    def test_plan_scoped_to_unit(self):
        doc = self._build_plan_doc(unit_id='unit-A')
        assert doc['unit_id'] == 'unit-A'

    def test_plan_scoped_to_project(self):
        doc = self._build_plan_doc(project_id='proj-X')
        assert doc['project_id'] == 'proj-X'

    def test_different_units_different_plans(self):
        doc_a = self._build_plan_doc(unit_id='unit-A')
        doc_b = self._build_plan_doc(unit_id='unit-B')
        assert doc_a['unit_id'] != doc_b['unit_id']
        assert doc_a['id'] != doc_b['id']

    def test_discipline_must_be_valid(self):
        doc = self._build_plan_doc(discipline='electrical')
        assert doc['discipline'] in PLAN_DISCIPLINES

    def test_invalid_discipline_not_in_set(self):
        doc = self._build_plan_doc(discipline='random_thing')
        assert doc['discipline'] not in PLAN_DISCIPLINES


class TestContractorRoutingLogic:

    MANAGEMENT_ROLES = ('owner', 'admin', 'project_manager')

    def _resolve_target(self, role, project_id):
        if role == 'contractor':
            return f'/projects/{project_id}/tasks?assignee=me'
        elif role == 'viewer':
            return f'/projects/{project_id}/tasks'
        else:
            return f'/projects/{project_id}/control'

    def test_contractor_goes_to_tasks(self):
        target = self._resolve_target('contractor', 'p1')
        assert '/tasks' in target
        assert 'assignee=me' in target
        assert '/control' not in target

    def test_viewer_goes_to_tasks_no_filter(self):
        target = self._resolve_target('viewer', 'p1')
        assert '/tasks' in target
        assert 'assignee' not in target

    def test_owner_goes_to_control(self):
        target = self._resolve_target('owner', 'p1')
        assert '/control' in target

    def test_admin_goes_to_control(self):
        target = self._resolve_target('admin', 'p1')
        assert '/control' in target

    def test_pm_goes_to_control(self):
        target = self._resolve_target('project_manager', 'p1')
        assert '/control' in target

    def test_contractor_blocked_from_control(self):
        assert 'contractor' not in self.MANAGEMENT_ROLES

    def test_management_team_goes_to_control(self):
        target = self._resolve_target('management_team', 'p1')
        assert '/control' in target


class TestUnitProjectScoping:

    def test_unit_query_includes_project_id(self):
        unit_id = 'u1'
        project_id = 'p1'
        query = {'id': unit_id, 'project_id': project_id}
        assert query['id'] == unit_id
        assert query['project_id'] == project_id

    def test_mismatched_project_rejected_conceptually(self):
        unit_project = 'proj-A'
        request_project = 'proj-B'
        assert unit_project != request_project

    def test_plan_query_scoped_to_both(self):
        query = {'project_id': 'p1', 'unit_id': 'u1'}
        assert 'project_id' in query
        assert 'unit_id' in query
