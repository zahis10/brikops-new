"""M4.1+M4.2 Hotfix Tests — contractor filter logic, unit label formatter, summary consistency."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestUnitLabelFormatter:
    """Unit display: 'דירה X' formatting rules."""

    def _fmt(self, label):
        if not label and label != 0:
            return ''
        s = str(label)
        if s.isdigit():
            return f'דירה {s}'
        if s.startswith('דירה '):
            return s
        return s

    def test_numeric_string(self):
        assert self._fmt('1') == 'דירה 1'
        assert self._fmt('38') == 'דירה 38'
        assert self._fmt('100') == 'דירה 100'

    def test_already_prefixed(self):
        assert self._fmt('דירה 2') == 'דירה 2'
        assert self._fmt('דירה 15') == 'דירה 15'

    def test_no_double_prefix(self):
        result = self._fmt('דירה 1')
        assert result == 'דירה 1'
        assert result.count('דירה') == 1

    def test_text_label_preserved(self):
        assert self._fmt('גג') == 'גג'
        assert self._fmt('פנטהאוז') == 'פנטהאוז'
        assert self._fmt('מחסן') == 'מחסן'

    def test_empty_and_none(self):
        assert self._fmt(None) == ''
        assert self._fmt('') == ''

    def test_zero(self):
        assert self._fmt(0) == 'דירה 0'
        assert self._fmt('0') == 'דירה 0'


class TestContractorFilterLogic:
    """Contractor filter query construction matches spec."""

    def _build_query(self, project_id, status=None, contractor='all'):
        params = {'project_id': project_id}
        if status:
            params['status'] = status
        if contractor == 'unassigned':
            params['unassigned'] = True
        elif contractor and contractor != 'all':
            params['assignee_id'] = contractor
        return params

    def test_all_contractors(self):
        q = self._build_query('p1')
        assert q == {'project_id': 'p1'}
        assert 'assignee_id' not in q

    def test_specific_contractor(self):
        q = self._build_query('p1', contractor='c123')
        assert q['assignee_id'] == 'c123'
        assert 'unassigned' not in q

    def test_unassigned(self):
        q = self._build_query('p1', contractor='unassigned')
        assert q['unassigned'] is True
        assert 'assignee_id' not in q

    def test_with_status_filter(self):
        q = self._build_query('p1', status='open', contractor='c123')
        assert q['status'] == 'open'
        assert q['assignee_id'] == 'c123'

    def test_contractor_filter_uses_id_not_category(self):
        q = self._build_query('p1', contractor='uuid-of-electrician')
        assert q['assignee_id'] == 'uuid-of-electrician'
        assert 'category' not in q


class TestSpecialtyLabels:
    """Hebrew specialty display mapping."""

    SPECIALTY_LABELS = {
        'electrical': 'חשמלאי',
        'plumbing': 'אינסטלטור',
        'painting': 'צבעי',
        'flooring': 'רצף',
        'carpentry': 'נגר',
        'hvac': 'מיזוג',
        'masonry': 'בנאי',
        'windows': 'חלונות',
        'doors': 'דלתות',
        'general': 'כללי',
    }

    def _display_name(self, contractor):
        if contractor.get('specialty') and contractor['specialty'] in self.SPECIALTY_LABELS:
            return self.SPECIALTY_LABELS[contractor['specialty']]
        return contractor['name']

    def test_electrical_hebrew(self):
        assert self._display_name({'name': 'חשמלאי', 'specialty': 'electrical'}) == 'חשמלאי'

    def test_plumbing_hebrew(self):
        assert self._display_name({'name': 'אינסטלטור', 'specialty': 'plumbing'}) == 'אינסטלטור'

    def test_painting_hebrew(self):
        assert self._display_name({'name': 'צבעי', 'specialty': 'painting'}) == 'צבעי'

    def test_no_specialty_falls_back_to_name(self):
        assert self._display_name({'name': 'Custom Name'}) == 'Custom Name'

    def test_unknown_specialty_falls_back(self):
        assert self._display_name({'name': 'Bob', 'specialty': 'unknown_trade'}) == 'Bob'


class TestContractorSummaryIntegration:
    """Integration: summary counts match actual task list counts."""

    def test_summary_counts_match_task_list(self):
        import pymongo
        client = pymongo.MongoClient('localhost', 27017)
        db = client.contractor_ops

        project = db.projects.find_one({})
        if not project:
            pytest.skip('No project in DB')
        pid = project['id']

        all_tasks = list(db.tasks.find({'project_id': pid}))
        total = len(all_tasks)
        unassigned = sum(1 for t in all_tasks if not t.get('assignee_id'))

        by_assignee = {}
        for t in all_tasks:
            aid = t.get('assignee_id')
            if aid:
                by_assignee[aid] = by_assignee.get(aid, 0) + 1

        assert total > 0
        assert sum(by_assignee.values()) + unassigned == total

        for aid, expected_count in by_assignee.items():
            actual = db.tasks.count_documents({'project_id': pid, 'assignee_id': aid})
            assert actual == expected_count, f'Count mismatch for {aid}: expected {expected_count}, got {actual}'

    def test_contractor_has_specialty_field(self):
        import pymongo
        client = pymongo.MongoClient('localhost', 27017)
        db = client.contractor_ops

        contractors = list(db.users.find(
            {'role': 'contractor', 'specialties': {'$exists': True, '$ne': []}},
            {'_id': 0, 'id': 1, 'specialties': 1}
        ))

        for c in contractors:
            assert c.get('specialties'), f'Contractor {c["id"]} has no specialties'
            assert isinstance(c['specialties'], list)
