import asyncio
import io
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from contractor_ops import projects_router, spare_photos_router as router
from contractor_ops.router import _get_project_role as real_get_project_role


class _Request:
    headers = {}


class _File:
    def __init__(self, body=b"\xff\xd8\xff", mime="image/jpeg", name="photo.jpg"):
        self.filename, self.content_type, self.body = name, mime, body

    async def read(self):
        return self.body


class _Units:
    def __init__(self, unit):
        self.unit, self.update_calls = unit, []

    async def find_one(self, *_args, **_kwargs):
        return self.unit

    async def update_one(self, query, update):
        self.update_calls.append((query, update))


class _Db:
    def __init__(self, unit, project=None):
        self.units = _Units(unit)
        self.projects = MagicMock()
        self.projects.find_one = AsyncMock(return_value=project or {
            "id": unit.get("project_id"), "spare_settings": {
                "categories": [{"name": "ריצוף יבש", "measure": "tiles"}],
                "profiles": [], "margin_pct": 10,
            },
        })


def _unit(**extra):
    return {"id": "unit-1", "project_id": "project-1", "spare_tiles": [], **extra}


def _patch_upload(monkeypatch, db, role="management_team", stored="/api/uploads/x.jpg"):
    monkeypatch.setattr(router, "get_db", lambda: db)
    monkeypatch.setattr(router, "_get_project_role", AsyncMock(return_value=role))
    monkeypatch.setattr(router, "check_upload_rate_limit", MagicMock())
    monkeypatch.setattr(router, "check_upload_bytes", MagicMock())
    monkeypatch.setattr(router, "check_content_length", MagicMock())
    monkeypatch.setattr(router, "check_storage_quota", AsyncMock())
    monkeypatch.setattr(router, "record_upload", AsyncMock())
    monkeypatch.setattr(router, "_audit", AsyncMock())
    monkeypatch.setattr(router.object_storage, "save_bytes", MagicMock(return_value=stored))
    monkeypatch.setattr(router.object_storage, "resolve_url", lambda value: value)


def _upload(monkeypatch, db, file=None, category="ריצוף יבש", user=None):
    _patch_upload(monkeypatch, db)
    return asyncio.run(router.upload_spare_photo(
        "unit-1", _Request(), file or _File(), category,
        user or {"id": "team-1", "name": "צוות"},
    ))


def test_sniff_minimal_image_headers():
    assert router._sniff_image(b"\xff\xd8\xff") == "jpg"
    assert router._sniff_image(b"\x89PNG\r\n\x1a\n") == "png"
    assert router._sniff_image(b"RIFFxxxxWEBP") == "webp"
    assert router._sniff_image(b"\x00\x00\x00\x00ftypheic") == "heic"


@pytest.mark.parametrize(
    ("body", "name", "mime", "extension", "stored_mime"),
    [
        (b"\xff\xd8\xff", "photo.jpg", "image/jpeg", "jpg", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "photo.png", "image/png", "png", "image/png"),
        (b"RIFFxxxxWEBP", "photo.webp", "image/webp", "webp", "image/webp"),
        (b"\x00\x00\x00\x00ftypheic", "photo.heic", "image/heic", "heic", "image/heic"),
        (b"\x00\x00\x00\x00ftypheix", "photo.heif", "image/heif", "heic", "image/heic"),
    ],
)
def test_minimal_valid_headers_upload_and_persist(
    monkeypatch, body, name, mime, extension, stored_mime,
):
    db = _Db(_unit())
    result = _upload(
        monkeypatch, db, _File(body=body, name=name, mime=mime),
    )
    saved = router.object_storage.save_bytes.call_args.args
    persisted = db.units.update_calls[0][1]["$push"]["spare_photos"]
    assert result["id"] == persisted["id"]
    assert result["uploaded_at"] == persisted["uploaded_at"]
    assert saved[1].startswith("spare/project-1/unit-1/")
    assert saved[1].endswith(f".{extension}")
    assert saved[2] == stored_mime


def test_configured_category_upload_pushes_stored_ref(monkeypatch):
    db = _Db(_unit())
    result = _upload(monkeypatch, db)
    assert result["url"] == "/api/uploads/x.jpg"
    pushed = db.units.update_calls[0][1]["$push"]["spare_photos"]
    assert pushed["category"] == "ריצוף יבש"
    assert pushed["url"] == "/api/uploads/x.jpg"
    assert pushed["uploaded_by"] == "team-1"
    assert pushed["uploaded_by_name"] == "צוות"
    assert pushed["uploaded_at"]
    assert pushed["id"] == result["id"]
    router._audit.assert_awaited_once_with(
        "unit", "unit-1", "spare_photo_upload", "team-1",
        {
            "category": "ריצוף יבש",
            "photo_id": pushed["id"],
            "project_id": "project-1",
        },
    )
    router.check_content_length.assert_called_once_with(
        None, router.MAX_PHOTO_SIZE,
    )
    save = router.object_storage.save_bytes
    assert save.call_args.args[1].startswith("spare/project-1/unit-1/")


def test_custom_spare_tile_category_is_accepted(monkeypatch):
    db = _Db(_unit(spare_tiles=[{"type": "אבן מיוחדת", "count": 1}]))
    _upload(monkeypatch, db, category="אבן מיוחדת")
    assert db.units.update_calls


def test_unknown_category_is_rejected_before_storage(monkeypatch):
    db = _Db(_unit())
    _patch_upload(monkeypatch, db)
    with pytest.raises(HTTPException) as error:
        asyncio.run(router.upload_spare_photo(
            "unit-1", _Request(), _File(), "לא קיים", {"id": "team-1"},
        ))
    assert error.value.status_code == 422
    router.object_storage.save_bytes.assert_not_called()


def test_category_and_unit_limits(monkeypatch):
    category_full = _unit(spare_photos=[
        {"id": str(i), "category": "ריצוף יבש"} for i in range(3)
    ])
    db = _Db(category_full)
    _patch_upload(monkeypatch, db)
    with pytest.raises(HTTPException) as error:
        asyncio.run(router.upload_spare_photo(
            "unit-1", _Request(), _File(), "ריצוף יבש", {"id": "team-1"},
        ))
    assert error.value.detail == "עד 3 תמונות לקטגוריה"
    total_full = _unit(spare_photos=[
        {"id": str(i), "category": "אחר"} for i in range(20)
    ])
    db = _Db(total_full)
    _patch_upload(monkeypatch, db)
    with pytest.raises(HTTPException) as error:
        asyncio.run(router.upload_spare_photo(
            "unit-1", _Request(), _File(), "ריצוף יבש", {"id": "team-1"},
        ))
    assert error.value.detail == "עד 20 תמונות לדירה"


def test_contractor_forbidden_and_management_team_allowed(monkeypatch):
    db = _Db(_unit())
    _patch_upload(monkeypatch, db, role="contractor")
    with pytest.raises(HTTPException) as error:
        asyncio.run(router.upload_spare_photo(
            "unit-1", _Request(), _File(), "ריצוף יבש", {"id": "c"},
        ))
    assert error.value.status_code == 403
    _upload(monkeypatch, _Db(_unit()), user={"id": "team"})


def test_super_admin_resolved_by_project_role(monkeypatch):
    db = _Db(_unit())
    _patch_upload(monkeypatch, db, role="project_manager")
    monkeypatch.setattr(router, "_get_project_role", real_get_project_role)
    result = asyncio.run(router.upload_spare_photo(
        "unit-1", _Request(), _File(), "ריצוף יבש",
        {"id": "admin", "platform_role": "super_admin"},
    ))
    assert result["id"]


@pytest.mark.parametrize(
    "file",
    [
        _File(body=b""),
        _File(body=b"%PDF-1.7", name="photo.jpg"),
        _File(body=b"x" * (10 * 1024 * 1024 + 1)),
    ],
)
def test_empty_pdf_spoof_and_oversize_never_reach_storage(monkeypatch, file):
    db = _Db(_unit())
    _patch_upload(monkeypatch, db)
    with pytest.raises(HTTPException) as error:
        asyncio.run(router.upload_spare_photo(
            "unit-1", _Request(), file, "ריצוף יבש", {"id": "team"},
        ))
    assert error.value.status_code == 400
    router.object_storage.save_bytes.assert_not_called()


def test_declared_pdf_is_rejected_before_storage(monkeypatch):
    db = _Db(_unit())
    _patch_upload(monkeypatch, db)
    with pytest.raises(HTTPException) as error:
        asyncio.run(router.upload_spare_photo(
            "unit-1", _Request(),
            _File(body=b"%PDF-1.7", mime="application/pdf", name="photo.jpg"),
            "ריצוף יבש", {"id": "team"},
        ))
    assert error.value.status_code in (400, 422)
    router.object_storage.save_bytes.assert_not_called()


def test_declared_png_with_jpeg_bytes_uses_sniffed_jpg(monkeypatch):
    db = _Db(_unit())
    result = _upload(
        monkeypatch, db, _File(body=b"\xff\xd8\xffjpeg", mime="image/png",
                                name="photo.png"),
    )
    assert result["id"]
    args = router.object_storage.save_bytes.call_args.args
    assert args[1].endswith(".jpg")
    assert args[2] == "image/jpeg"


def test_delete_uploader_removes_db_entry_and_storage(monkeypatch):
    photo = {"id": "photo-1", "category": "ריצוף יבש",
             "url": "s3://spare/p.jpg", "uploaded_by": "team"}
    db = _Db(_unit(spare_photos=[photo]))
    monkeypatch.setattr(router, "get_db", lambda: db)
    monkeypatch.setattr(router, "_get_project_role", AsyncMock(return_value="management_team"))
    monkeypatch.setattr(router, "_audit", AsyncMock())
    monkeypatch.setattr(router.object_storage, "delete", MagicMock(return_value=True))
    result = asyncio.run(router.delete_spare_photo("unit-1", "photo-1", {"id": "team"}))
    assert result is None
    assert db.units.update_calls[0][1] == {"$pull": {"spare_photos": {"id": "photo-1"}}}
    router.object_storage.delete.assert_called_once_with("s3://spare/p.jpg")


def test_other_management_user_cannot_delete(monkeypatch):
    photo = {"id": "photo-1", "uploaded_by": "other"}
    db = _Db(_unit(spare_photos=[photo]))
    monkeypatch.setattr(router, "get_db", lambda: db)
    monkeypatch.setattr(router, "_get_project_role", AsyncMock(return_value="management_team"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(router.delete_spare_photo("unit-1", "photo-1", {"id": "team"}))
    assert error.value.status_code == 403


def test_project_manager_can_delete_someone_elses_photo(monkeypatch):
    db = _Db(_unit(spare_photos=[{"id": "p", "uploaded_by": "team", "url": "ref"}]))
    monkeypatch.setattr(router, "get_db", lambda: db)
    monkeypatch.setattr(router, "_get_project_role", AsyncMock(return_value="project_manager"))
    monkeypatch.setattr(router, "_audit", AsyncMock())
    monkeypatch.setattr(router.object_storage, "delete", MagicMock(return_value=True))
    asyncio.run(router.delete_spare_photo("unit-1", "p", {"id": "pm"}))
    assert db.units.update_calls


def test_unknown_photo_returns_404(monkeypatch):
    db = _Db(_unit(spare_photos=[]))
    monkeypatch.setattr(router, "get_db", lambda: db)
    monkeypatch.setattr(router, "_get_project_role", AsyncMock(return_value="project_manager"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(router.delete_spare_photo("unit-1", "missing", {"id": "pm"}))
    assert error.value.status_code == 404


def test_storage_delete_exception_keeps_success_after_db_pull(monkeypatch, caplog):
    db = _Db(_unit(spare_photos=[{"id": "p", "uploaded_by": "team", "url": "ref"}]))
    monkeypatch.setattr(router, "get_db", lambda: db)
    monkeypatch.setattr(router, "_get_project_role", AsyncMock(return_value="management_team"))
    monkeypatch.setattr(router, "_audit", AsyncMock())
    monkeypatch.setattr(router.object_storage, "delete", MagicMock(side_effect=RuntimeError("down")))
    with caplog.at_level("WARNING"):
        asyncio.run(router.delete_spare_photo("unit-1", "p", {"id": "team"}))
    assert db.units.update_calls
    assert any("failed" in record.message.lower() for record in caplog.records)


def test_storage_delete_false_warns_after_db_pull(monkeypatch, caplog):
    db = _Db(_unit(spare_photos=[{"id": "p", "uploaded_by": "team", "url": "ref"}]))
    monkeypatch.setattr(router, "get_db", lambda: db)
    monkeypatch.setattr(router, "_get_project_role", AsyncMock(return_value="management_team"))
    monkeypatch.setattr(router, "_audit", AsyncMock())
    monkeypatch.setattr(router.object_storage, "delete", MagicMock(return_value=False))
    with caplog.at_level("WARNING"):
        asyncio.run(router.delete_spare_photo("unit-1", "p", {"id": "team"}))
    assert db.units.update_calls
    assert any("false" in record.message.lower() for record in caplog.records)


def test_serialize_photo_resolves_s3_without_leaking_ref(monkeypatch):
    monkeypatch.setattr(router.object_storage, "generate_url",
                        lambda ref: "https://signed.example/photo")
    photo = {"id": "p", "category": "ריצוף", "url": "s3://secret/key",
             "uploaded_at": "2026-01-01", "uploaded_by": "u",
             "uploaded_by_name": "User"}
    assert router.serialize_photo(photo)["url"] == "https://signed.example/photo"


def test_unit_detail_sorts_display_photos_and_keeps_unit_raw(monkeypatch):
    unit = _unit(spare_photos=[
        {"id": "late", "category": "ריצוף יבש", "url": "s3://late",
         "uploaded_at": "2026-02-01"},
        {"id": "early", "category": "ריצוף יבש", "url": "s3://early",
         "uploaded_at": "2026-01-01"},
        {"category": "bad", "url": "ignored"},
        "bad",
    ])
    db = _Db(unit)
    db.floors = MagicMock()
    db.floors.find_one = AsyncMock(return_value=None)
    db.buildings = MagicMock()
    db.buildings.find_one = AsyncMock(return_value=None)
    db.tasks = MagicMock()
    db.tasks.find.return_value.to_list = AsyncMock(return_value=[])
    db.field_escalations = MagicMock()
    monkeypatch.setattr(projects_router, "get_db", lambda: db)
    monkeypatch.setattr(projects_router, "_check_project_read_access", AsyncMock())
    monkeypatch.setattr(projects_router, "_get_project_role", AsyncMock(return_value="viewer"))
    monkeypatch.setattr(router.object_storage, "generate_url",
                        lambda ref: "https://signed.example/" + ref.rsplit("/", 1)[-1])
    result = asyncio.run(projects_router.get_unit_detail("unit-1", {"id": "viewer"}))
    assert [p["id"] for p in result["spare_photos"]] == ["early", "late"]
    assert result["spare_photos"][0]["url"] == "https://signed.example/early"
    assert result["unit"]["spare_photos"][0]["url"] == "s3://late"


def test_unit_detail_without_photos_returns_empty_list(monkeypatch):
    db = _Db(_unit())
    db.floors = MagicMock()
    db.floors.find_one = AsyncMock(return_value=None)
    db.buildings = MagicMock()
    db.buildings.find_one = AsyncMock(return_value=None)
    db.tasks = MagicMock()
    db.tasks.find.return_value.to_list = AsyncMock(return_value=[])
    db.field_escalations = MagicMock()
    monkeypatch.setattr(projects_router, "get_db", lambda: db)
    monkeypatch.setattr(projects_router, "_check_project_read_access", AsyncMock())
    monkeypatch.setattr(projects_router, "_get_project_role", AsyncMock(return_value="viewer"))
    result = asyncio.run(projects_router.get_unit_detail("unit-1", {"id": "viewer"}))
    assert result["spare_photos"] == []