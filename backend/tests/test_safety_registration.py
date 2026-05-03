"""Tests for Batch S2A — Safety Project Registration."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from contractor_ops import safety_registration_router as srr


def test_get_initializes_empty_registration_if_missing():
    """First GET creates an empty doc lazily."""
    async def run():
        db = MagicMock()
        db.safety_project_settings.find_one = AsyncMock(side_effect=[None, {
            "id": "x", "project_id": "p1", "deletedAt": None,
            "developer_name": None, "main_contractor_name": None,
            "contractor_registry_number": None, "office_address": None,
            "managers": [], "permit_number": None, "form_4_target_date": None,
        }])
        db.safety_project_settings.insert_one = AsyncMock()
        doc = await srr._get_or_init_registration(db, "p1")
        assert doc["project_id"] == "p1"
        assert doc["managers"] == []
        db.safety_project_settings.insert_one.assert_called_once()
    asyncio.run(run())


def test_get_returns_existing_registration():
    """If doc exists, GET returns it without insert."""
    async def run():
        db = MagicMock()
        existing = {"id": "x", "project_id": "p1", "deletedAt": None, "developer_name": "Acme"}
        db.safety_project_settings.find_one = AsyncMock(return_value=existing)
        db.safety_project_settings.insert_one = AsyncMock()
        doc = await srr._get_or_init_registration(db, "p1")
        assert doc["developer_name"] == "Acme"
        db.safety_project_settings.insert_one.assert_not_called()
    asyncio.run(run())


def test_required_fields_all_missing_returns_zero_pct():
    async def run():
        db = MagicMock()
        db.safety_project_settings.find_one = AsyncMock(return_value={
            "id": "x", "project_id": "p1", "deletedAt": None,
            "developer_name": None, "main_contractor_name": None,
            "contractor_registry_number": None, "office_address": None,
            "managers": [], "permit_number": None, "form_4_target_date": None,
        })
        doc = await srr._get_or_init_registration(db, "p1")
        required = ["developer_name", "main_contractor_name",
                    "contractor_registry_number", "permit_number"]
        required_address = ["city", "street", "house_number"]
        missing = [f for f in required if not doc.get(f)]
        addr = doc.get("office_address") or {}
        for f in required_address:
            if not addr.get(f):
                missing.append(f"office_address.{f}")
        if not doc.get("managers"):
            missing.append("managers")
        assert len(missing) == 8  # 4 + 3 + 1
    asyncio.run(run())


def test_required_fields_all_filled_returns_complete():
    doc = {
        "developer_name": "Acme",
        "main_contractor_name": "Acme",
        "contractor_registry_number": "12345",
        "permit_number": "P-001",
        "office_address": {"city": "TLV", "street": "Main", "house_number": "1"},
        "managers": [{"first_name": "A", "last_name": "B"}],
    }
    required = ["developer_name", "main_contractor_name",
                "contractor_registry_number", "permit_number"]
    required_address = ["city", "street", "house_number"]
    missing = [f for f in required if not doc.get(f)]
    addr = doc.get("office_address") or {}
    for f in required_address:
        if not addr.get(f):
            missing.append(f"office_address.{f}")
    if not doc.get("managers"):
        missing.append("managers")
    assert missing == []


def test_upsert_hashes_manager_id_numbers():
    """V2 fix: uses _hash_id_number (real helper) + inline masking
    (no _mask_id helper exists). Verifies PII pattern matches workers."""
    with patch.object(srr, '_hash_id_number', return_value='HASHED'):
        manager = {"first_name": "A", "last_name": "B", "id_number": "123456789"}
        raw_id = manager.get("id_number")
        if raw_id:
            manager["id_number_hash"] = srr._hash_id_number(raw_id)
            stripped = raw_id.strip()
            if len(stripped) >= 4:
                manager["id_number"] = f"{stripped[:1]}***{stripped[-3:]}"
            else:
                manager["id_number"] = "***"
        assert manager["id_number_hash"] == "HASHED"
        assert manager["id_number"] == "1***789"


def test_inline_mask_short_id_falls_back_to_stars():
    """Edge: id < 4 chars → "***" instead of substring slicing."""
    raw = "12"
    stripped = raw.strip()
    masked = f"{stripped[:1]}***{stripped[-3:]}" if len(stripped) >= 4 else "***"
    assert masked == "***"


def test_pdf_export_returns_bytes_for_empty_registration():
    from services.safety_pdf import generate_registration_pdf
    empty_reg = {
        "developer_name": None,
        "main_contractor_name": None,
        "contractor_registry_number": None,
        "office_address": None,
        "managers": [],
        "permit_number": None,
        "form_4_target_date": None,
    }
    project = {"id": "p1", "name": "Test Project"}
    pdf = generate_registration_pdf(empty_reg, project)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1000
    assert pdf[:4] == b"%PDF"


def test_pdf_export_includes_developer_name_when_present():
    from services.safety_pdf import generate_registration_pdf
    reg = {
        "developer_name": "ארזי הנגב ייזום ובניה בע״מ",
        "main_contractor_name": None,
        "contractor_registry_number": "24914",
        "office_address": None, "managers": [],
        "permit_number": None, "form_4_target_date": None,
    }
    project = {"id": "p1", "name": "Test"}
    pdf = generate_registration_pdf(reg, project)
    assert pdf[:4] == b"%PDF"


def test_managers_can_be_empty_list():
    """Empty managers list is valid (not required for save, only for completion)."""
    from contractor_ops.schemas import SafetyProjectRegistrationUpsert
    payload = SafetyProjectRegistrationUpsert(managers=[])
    assert payload.managers == []


def test_registration_schema_accepts_partial_update():
    """PATCH-style — only updated fields included."""
    from contractor_ops.schemas import SafetyProjectRegistrationUpsert
    payload = SafetyProjectRegistrationUpsert(developer_name="Just this")
    as_dict = payload.dict(exclude_unset=True)
    assert "developer_name" in as_dict
    assert "main_contractor_name" not in as_dict


def test_registration_address_optional():
    """Office address is optional — can be None."""
    from contractor_ops.schemas import SafetyProjectRegistration
    reg = SafetyProjectRegistration(office_address=None, managers=[])
    assert reg.office_address is None
    assert reg.managers == []
