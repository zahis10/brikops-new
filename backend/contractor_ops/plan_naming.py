"""#629 — the name a plan carries after its file is replaced by an updated one.

A plan that was never given a name of its own is called after its file: depending on the upload window it was
created with, the stored name is the file name as it is ("801A-6-003.pdf") or without the extension
("801A-6-003"). Such a name follows the file when an updated plan is uploaded. A name somebody typed stays."""
import re
from typing import Optional

# same rule as planNameOf() in frontend/src/components/BulkPlanUploadModal.jsx
_EXTENSION = re.compile(r'\.[^/.]+$')


def _without_extension(filename: str) -> str:
    return _EXTENSION.sub('', filename)


def name_after_new_file(plan: dict, new_filename: Optional[str]) -> Optional[str]:
    """The name `plan` should carry once `new_filename` is its file, or None when the name must not change.

    `plan` is the document as it is BEFORE the update. The name counts as "the file's name" when it equals the
    name of the plan's current file or of any earlier version of it, with or without the extension."""
    name = (plan.get('name') or '').strip()
    new_filename = (new_filename or '').strip()
    if not name or not new_filename:
        return None
    seen = [plan.get('original_filename')]
    seen += [v.get('original_filename') for v in (plan.get('versions') or []) if isinstance(v, dict)]
    for filename in seen:
        filename = (filename or '').strip()
        if not filename:
            continue
        if name == filename:
            new_name = new_filename
        elif name == _without_extension(filename):
            new_name = _without_extension(new_filename) or new_filename
        else:
            continue
        return new_name if new_name != name else None
    return None
