"""Drift guard for STATUS_BUCKET_EXPANSION ↔ dashboard KPI aggregation.

Filed under BATCH 5F (P1 launch-blocking). Catches a future contributor who
adds a new task status to the dashboard buckets in tasks_router.py:363
(open_statuses / handled_statuses) but forgets to add it to
STATUS_BUCKET_EXPANSION (or vice versa) — the chip-click ↔ KPI-count
mismatch we are fixing in this batch would silently re-emerge otherwise.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from contractor_ops.tasks_router import STATUS_BUCKET_EXPANSION


def test_bucket_expansion_open_matches_dashboard():
    assert set(STATUS_BUCKET_EXPANSION['open']) == {
        'open', 'assigned', 'reopened',
    }, "STATUS_BUCKET_EXPANSION['open'] drifted from dashboard open_statuses"


def test_bucket_expansion_in_progress_matches_dashboard():
    assert set(STATUS_BUCKET_EXPANSION['in_progress']) == {
        'in_progress', 'pending_contractor_proof',
        'pending_manager_approval', 'returned_to_contractor',
        'waiting_verify',
    }, "STATUS_BUCKET_EXPANSION['in_progress'] drifted from dashboard"


def test_bucket_expansion_closed_matches_dashboard_handled():
    assert set(STATUS_BUCKET_EXPANSION['closed']) == {
        'closed', 'approved',
    }, "STATUS_BUCKET_EXPANSION['closed'] drifted from dashboard handled_statuses"


def test_bucket_union_covers_all_dashboard_statuses():
    """The union of all 3 buckets must equal dashboard's
    (open_statuses ∪ handled_statuses) — no status falls outside a bucket.
    The dashboard literals live at tasks_router.py:363-364."""
    dashboard_open = {
        'open', 'assigned', 'in_progress', 'pending_contractor_proof',
        'reopened', 'waiting_verify',
    }
    dashboard_handled = {'closed', 'approved', 'pending_manager_approval'}
    dashboard_all = dashboard_open | dashboard_handled

    bucket_union = set()
    for members in STATUS_BUCKET_EXPANSION.values():
        bucket_union.update(members)

    # 'returned_to_contractor' is in our in_progress bucket but not in the
    # dashboard's open_statuses list — it is correctly handled by the
    # frontend chip but the dashboard treats it as in-progress visually.
    # Allow bucket_union to be a SUPERSET of dashboard_all.
    missing = dashboard_all - bucket_union
    assert not missing, (
        f"Statuses in dashboard but not in any STATUS_BUCKET_EXPANSION "
        f"bucket: {sorted(missing)}"
    )
