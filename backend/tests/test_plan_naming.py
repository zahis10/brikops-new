import pytest

from contractor_ops.plan_naming import name_after_new_file


def _plan(name, filename, *older):
    """a plan whose current file is `filename`; `older` are the files of its earlier versions, oldest first"""
    versions = [{'version': i + 1, 'original_filename': fn} for i, fn in enumerate(list(older) + [filename])]
    return {'name': name, 'original_filename': filename, 'versions': versions}


@pytest.mark.parametrize('plan,new_file,expected', [
    # the name is the file's name -> it follows the new file
    (_plan('801A-6-003.pdf', '801A-6-003.pdf'), '801A-6-003 rev B.pdf', '801A-6-003 rev B.pdf'),
    # ... the file's name without the extension -> same style
    (_plan('801A-6-003', '801A-6-003.pdf'), '801A-6-003 rev B.pdf', '801A-6-003 rev B'),
    (_plan('תוכנית קומה 2', 'תוכנית קומה 2.pdf'), 'תוכנית קומה 2 - מעודכנת.pdf', 'תוכנית קומה 2 - מעודכנת'),
    # the name of an EARLIER file of the plan (a plan that was updated before this rule existed)
    (_plan('801A-6-003.pdf', 'menu.pdf', '801A-6-003.pdf'), 'new.pdf', 'new.pdf'),
    (_plan('801A-6-003', 'menu.pdf', '801A-6-003.pdf'), 'new.dwg', 'new'),
    # a name somebody typed stays
    (_plan('קומה 2 — אדריכלות', '801A-6-003.pdf'), 'x.pdf', None),
    (_plan('801A-6-003 (ישן)', '801A-6-003.pdf'), 'x.pdf', None),
    # only spaces around it differ: still the file's name
    (_plan('801A-6-003 ', '801A-6-003.pdf'), 'x.pdf', 'x'),
    # the same file name again -> nothing to change
    (_plan('a.pdf', 'a.pdf'), 'a.pdf', None),
    (_plan('a', 'a.pdf'), 'a.pdf', None),
    # no name at all (old documents): the screens show the file name by themselves
    ({'original_filename': 'a.pdf'}, 'b.pdf', None),
    ({'name': '', 'original_filename': 'a.pdf', 'versions': []}, 'b.pdf', None),
    ({'name': None, 'original_filename': 'a.pdf'}, 'b.pdf', None),
    # nothing to follow
    (_plan('a.pdf', 'a.pdf'), '', None),
    (_plan('a.pdf', 'a.pdf'), None, None),
    # odd shapes do not break it
    ({'name': 'a.pdf', 'original_filename': None, 'versions': [None, {}, {'original_filename': 'a.pdf'}]}, 'b.pdf', 'b.pdf'),
    ({'name': 'a.pdf', 'original_filename': 'a.pdf', 'versions': None}, 'b.pdf', 'b.pdf'),
    # dots inside the name; a file name that is only an extension
    (_plan('plan.v2', 'plan.v2.pdf'), 'plan.v3.pdf', 'plan.v3'),
    (_plan('a', 'a.pdf'), '.pdf', '.pdf'),
])
def test_name_after_new_file(plan, new_file, expected):
    assert name_after_new_file(plan, new_file) == expected


def test_the_plan_is_not_modified():
    plan = _plan('a.pdf', 'a.pdf')
    before = repr(plan)
    name_after_new_file(plan, 'b.pdf')
    assert repr(plan) == before
