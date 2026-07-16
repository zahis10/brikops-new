"""Safety package — batch refactor-safety-split.

Submodule import order below IS the route registration order (the 3a
lesson: summary-BEFORE-{id} depends on it). Do not reorder.
"""
from contractor_ops.safety._shared import router  # noqa: F401
from contractor_ops.safety import healthz  # noqa: F401
from contractor_ops.safety import workers  # noqa: F401
from contractor_ops.safety import trainings  # noqa: F401
from contractor_ops.safety import documents  # noqa: F401
from contractor_ops.safety import tasks  # noqa: F401
from contractor_ops.safety import incidents  # noqa: F401
from contractor_ops.safety import tours  # noqa: F401
from contractor_ops.safety import equipment  # noqa: F401
from contractor_ops.safety import score_exports  # noqa: F401
from contractor_ops.safety import uploads  # noqa: F401
from contractor_ops.safety import induction  # noqa: F401
from contractor_ops.safety import gate  # noqa: F401
from contractor_ops.safety import indexes  # noqa: F401
from contractor_ops.safety.indexes import ensure_safety_indexes  # noqa: F401
