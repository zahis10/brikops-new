"""
Regression test for M8 Viewer RBAC enforcement.

Critical bug fixed: MANAGEMENT_ROLES variable was redefined at line 611
to include 'viewer', shadowing the correct definition at line 308.
This would have allowed viewers to bypass RBAC on task updates,
assignments, and manager decisions.

Fix: Renamed the second definition to VALID_TARGET_ROLES.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_management_roles_excludes_viewer():
    """REGRESSION: Verify MANAGEMENT_ROLES never includes 'viewer'."""
    from contractor_ops.router import MANAGEMENT_ROLES
    assert 'viewer' not in MANAGEMENT_ROLES, \
        "CRITICAL: viewer must NOT be in MANAGEMENT_ROLES (variable shadowing bug)"
    assert 'project_manager' in MANAGEMENT_ROLES
    assert 'management_team' in MANAGEMENT_ROLES


def test_valid_target_roles_exists_separately():
    """Verify VALID_TARGET_ROLES is a separate variable for role-change validation."""
    from contractor_ops.router import VALID_TARGET_ROLES
    assert 'viewer' in VALID_TARGET_ROLES, \
        "viewer should be a valid target role for role assignment"
    assert 'contractor' in VALID_TARGET_ROLES
    assert 'project_manager' in VALID_TARGET_ROLES
    assert 'management_team' in VALID_TARGET_ROLES


def test_no_management_roles_shadowing():
    """REGRESSION: Ensure MANAGEMENT_ROLES is not redefined anywhere in router.py."""
    import re
    router_path = os.path.join(os.path.dirname(__file__), '..', 'contractor_ops', 'router.py')
    with open(router_path) as f:
        content = f.read()

    matches = list(re.finditer(r'^MANAGEMENT_ROLES\s*=', content, re.MULTILINE))
    assert len(matches) == 1, \
        f"MANAGEMENT_ROLES must be defined exactly once, found {len(matches)} definitions"


def test_plan_upload_roles_excludes_viewer():
    """Verify PLAN_UPLOAD_ROLES does not include viewer."""
    import re
    router_path = os.path.join(os.path.dirname(__file__), '..', 'contractor_ops', 'router.py')
    with open(router_path) as f:
        content = f.read()

    match = re.search(r'PLAN_UPLOAD_ROLES\s*=\s*\(([^)]+)\)', content)
    assert match, "PLAN_UPLOAD_ROLES must be defined"
    roles_str = match.group(1)
    assert 'viewer' not in roles_str, \
        "viewer must NOT be in PLAN_UPLOAD_ROLES"


def test_viewer_explicit_blocks_exist():
    """Verify explicit viewer 403 blocks exist for critical endpoints."""
    router_path = os.path.join(os.path.dirname(__file__), '..', 'contractor_ops', 'router.py')
    with open(router_path) as f:
        content = f.read()

    required_blocks = [
        'Viewers cannot change task status',
        'Viewers cannot add updates',
        'Viewers cannot upload attachments',
    ]
    for block in required_blocks:
        assert block in content, \
            f"Missing explicit viewer block: '{block}'"
