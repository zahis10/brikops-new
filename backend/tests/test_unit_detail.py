import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from contractor_ops import projects_router


def test_unit_without_resolvable_project_returns_404():
    db = MagicMock()
    db.units.find_one = AsyncMock(return_value={
        'id': 'unit-1',
        'floor_id': None,
        'building_id': None,
        'project_id': None,
    })

    async def run():
        with (
            patch.object(projects_router, 'get_db', return_value=db),
            patch.object(
                projects_router,
                '_check_project_read_access',
                new=AsyncMock(),
            ) as access_check,
        ):
            with pytest.raises(HTTPException) as error:
                await projects_router.get_unit_detail(
                    'unit-1',
                    {'id': 'user-1'},
                )
            assert access_check.await_count == 0
            return error.value

    error = asyncio.run(run())
    assert error.status_code == 404
    assert error.detail == 'Unit not found'