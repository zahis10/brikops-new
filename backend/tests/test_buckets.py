import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from contractor_ops.bucket_utils import compute_task_bucket, BUCKET_LABELS, CATEGORY_TO_BUCKET


class TestComputeTaskBucket:
    def test_membership_trade_takes_highest_priority(self):
        task = {'company_id': 'c1', 'assignee_id': 'a1', 'category': 'general'}
        company_map = {'c1': 'electrical'}
        contractor_map = {'a1': 'plumbing'}
        membership_trade_map = {'a1': 'painting'}
        result = compute_task_bucket(task, contractor_map, company_map, membership_trade_map)
        assert result['bucket_key'] == 'painting'
        assert result['source'] == 'membership'

    def test_company_trade_second_priority(self):
        task = {'company_id': 'c1', 'assignee_id': 'a1', 'category': 'general'}
        company_map = {'c1': 'electrical'}
        contractor_map = {'a1': 'plumbing'}
        result = compute_task_bucket(task, contractor_map, company_map)
        assert result['bucket_key'] == 'electrical'
        assert result['source'] == 'company'

    def test_assignee_trade_third_priority(self):
        task = {'assignee_id': 'a1', 'category': 'general'}
        contractor_map = {'a1': 'plumbing'}
        result = compute_task_bucket(task, contractor_map, {})
        assert result['bucket_key'] == 'plumbing'
        assert result['source'] == 'assignee'

    def test_membership_beats_company_and_assignee(self):
        task = {'company_id': 'c1', 'assignee_id': 'a1', 'category': 'hvac'}
        result = compute_task_bucket(
            task,
            contractor_map={'a1': 'plumbing'},
            company_map={'c1': 'electrical'},
            membership_trade_map={'a1': 'hvac'}
        )
        assert result['bucket_key'] == 'hvac'
        assert result['source'] == 'membership'

    def test_no_membership_falls_to_company(self):
        task = {'company_id': 'c1', 'assignee_id': 'a1', 'category': 'general'}
        result = compute_task_bucket(
            task,
            contractor_map={'a1': 'plumbing'},
            company_map={'c1': 'electrical'},
            membership_trade_map={}
        )
        assert result['bucket_key'] == 'electrical'
        assert result['source'] == 'company'

    def test_category_fallback(self):
        task = {'category': 'flooring'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'flooring'
        assert result['source'] == 'category'

    def test_general_category(self):
        task = {'category': 'general'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'general'
        assert result['label_he'] == 'כללי'

    def test_carpentry_maps_to_carpentry_kitchen(self):
        task = {'category': 'carpentry'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'carpentry_kitchen'
        assert result['label_he'] == 'נגרות/מטבח'

    def test_masonry_maps_to_structural(self):
        task = {'category': 'masonry'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'structural'
        assert result['label_he'] == 'שלד'

    def test_windows_maps_to_glazing(self):
        task = {'category': 'windows'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'glazing'
        assert result['label_he'] == 'חלונות/זכוכית'

    def test_electrical_stays_electrical(self):
        task = {'category': 'electrical'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'electrical'
        assert result['label_he'] == 'חשמלאי'

    def test_plumbing_stays_plumbing(self):
        task = {'category': 'plumbing'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'plumbing'
        assert result['label_he'] == 'אינסטלטור'

    def test_painting_stays_painting(self):
        task = {'category': 'painting'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'painting'
        assert result['label_he'] == 'צבעי'

    def test_hvac_stays_hvac(self):
        task = {'category': 'hvac'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'hvac'
        assert result['label_he'] == 'מיזוג'

    def test_doors_stays_doors(self):
        task = {'category': 'doors'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'doors'
        assert result['label_he'] == 'דלתות'

    def test_bathroom_cabinets(self):
        task = {'category': 'bathroom_cabinets'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'bathroom_cabinets'
        assert result['label_he'] == 'ארונות אמבטיה'

    def test_finishes(self):
        task = {'category': 'finishes'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'finishes'
        assert result['label_he'] == 'גמרים'

    def test_structural(self):
        task = {'category': 'structural'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'structural'
        assert result['label_he'] == 'שלד'

    def test_aluminum(self):
        task = {'category': 'aluminum'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'aluminum'
        assert result['label_he'] == 'אלומיניום'

    def test_metalwork(self):
        task = {'category': 'metalwork'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'metalwork'
        assert result['label_he'] == 'מסגרות'

    def test_unknown_category_creates_dynamic_bucket(self):
        task = {'category': 'custom_trade_xyz'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'custom_trade_xyz'
        assert result['source'] == 'category'

    def test_no_category_defaults_to_general(self):
        task = {}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'general'

    def test_empty_assignee_ignored(self):
        task = {'assignee_id': '', 'category': 'electrical'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'electrical'
        assert result['source'] == 'category'

    def test_unknown_assignee_falls_to_category(self):
        task = {'assignee_id': 'unknown_id', 'category': 'plumbing'}
        result = compute_task_bucket(task, {}, {})
        assert result['bucket_key'] == 'plumbing'
        assert result['source'] == 'category'

    def test_all_bucket_labels_are_hebrew(self):
        for key, label in BUCKET_LABELS.items():
            assert any('\u0590' <= c <= '\u05FF' for c in label), f"Bucket {key} label '{label}' is not Hebrew"

    def test_category_to_bucket_completeness(self):
        required = ['electrical', 'plumbing', 'painting', 'carpentry', 'carpentry_kitchen',
                     'flooring', 'hvac', 'masonry', 'windows', 'doors', 'general',
                     'bathroom_cabinets', 'finishes', 'structural', 'aluminum', 'metalwork', 'glazing']
        for cat in required:
            assert cat in CATEGORY_TO_BUCKET, f"Category {cat} missing from CATEGORY_TO_BUCKET"
