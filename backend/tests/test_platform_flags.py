import pytest

from contractor_ops.platform_flags import DEFECT_AI_MODE_KEY, coerce_flag


@pytest.mark.parametrize('doc,expected', [
    (None, False), ({}, False), ({'value': True}, True),
    ({'value': False}, False), ({'value': 'true'}, False),
    ({'value': 1}, False), ({'value': None}, False),
])
def test_coerce_flag(doc, expected):
    assert coerce_flag(doc) is expected


def test_default_and_key():
    assert coerce_flag(None, True) is True
    assert DEFECT_AI_MODE_KEY == 'defect_ai_mode_enabled'
