import uuid
import csv
import io
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from contractor_ops.router import get_db, get_current_user, _is_super_admin, _audit, _now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/import/g4", tags=["import-g4"])

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
TEMPLATE_PATH = STATIC_DIR / "g4_template.xlsx"

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_ROWS = 1000

COLUMN_MAP = {
    0: "building_name",
    1: "floor",
    2: "apartment_number",
    3: "tenant_name",
    4: "tenant_id_number",
    5: "tenant_phone",
    6: "tenant_email",
    7: "tenant_2_name",
    8: "tenant_2_id_number",
}

REQUIRED_COLUMNS = {"apartment_number", "tenant_name"}


async def _check_import_access(user: dict, project_id: str):
    if _is_super_admin(user):
        return
    db = get_db()
    membership = await db.project_memberships.find_one(
        {"user_id": user["id"], "project_id": project_id}
    )
    if not membership:
        raise HTTPException(status_code=403, detail="אין לך גישה לפרויקט זה")
    allowed = {"owner", "project_manager", "management_team"}
    if membership.get("role") not in allowed:
        raise HTTPException(status_code=403, detail="אין הרשאה לפעולה זו")


def _validate_row(row: dict) -> dict:
    errors = []
    warnings = []

    if not row.get("apartment_number", "").strip():
        errors.append("דירה חסרה")
    if not row.get("tenant_name", "").strip():
        errors.append("שם רוכש חסר")

    id_number = row.get("tenant_id_number", "").strip()
    if id_number and not re.match(r'^\d{9}$', id_number):
        warnings.append("ת\"ז לא תקין (9 ספרות)")

    phone = row.get("tenant_phone", "").strip()
    if phone:
        try:
            from contractor_ops.phone_utils import normalize_israeli_phone
            result = normalize_israeli_phone(phone)
            row["tenant_phone"] = result["phone_e164"]
        except (ValueError, Exception):
            warnings.append("טלפון לא תקין")

    email = row.get("tenant_email", "").strip()
    if email and "@" not in email:
        warnings.append("מייל לא תקין")

    t2_id = row.get("tenant_2_id_number", "").strip()
    if t2_id and not re.match(r'^\d{9}$', t2_id):
        warnings.append("ת\"ז רוכש 2 לא תקין")

    return {
        "row": row,
        "errors": errors,
        "warnings": warnings,
        "valid": len(errors) == 0,
    }


def _parse_xlsx(content: bytes) -> list:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if row_idx > MAX_ROWS + 1:
            break
        if not row or all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        parsed = {}
        for col_idx, col_key in COLUMN_MAP.items():
            val = row[col_idx] if col_idx < len(row) else None
            parsed[col_key] = str(val).strip() if val is not None else ""
        parsed["source_row"] = row_idx
        rows.append(parsed)
    wb.close()
    return rows


def _parse_csv(content: bytes) -> list:
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = []
    header_skipped = False
    for row_idx, row in enumerate(reader, start=1):
        if not header_skipped:
            header_skipped = True
            continue
        if row_idx > MAX_ROWS + 1:
            break
        if not row or all(cell.strip() == "" for cell in row):
            continue
        parsed = {}
        for col_idx, col_key in COLUMN_MAP.items():
            val = row[col_idx] if col_idx < len(row) else ""
            parsed[col_key] = val.strip()
        parsed["source_row"] = row_idx
        rows.append(parsed)
    return rows


@router.get("/template")
async def download_template(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    await _check_import_access(user, project_id)

    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=500, detail="קובץ תבנית לא נמצא")

    return FileResponse(
        path=str(TEMPLATE_PATH),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="g4_template.xlsx"',
        },
    )


@router.post("/preview")
async def preview_import(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    await _check_import_access(user, project_id)

    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="קובץ גדול מדי (מקסימום 5MB)")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="קובץ גדול מדי (מקסימום 5MB)")

    filename = (file.filename or "").lower()
    if filename.endswith(".xlsx"):
        try:
            raw_rows = _parse_xlsx(content)
        except Exception as e:
            logger.error(f"Failed to parse xlsx: {e}")
            raise HTTPException(status_code=400, detail="שגיאה בקריאת קובץ Excel")
    elif filename.endswith(".csv"):
        try:
            raw_rows = _parse_csv(content)
        except Exception as e:
            logger.error(f"Failed to parse csv: {e}")
            raise HTTPException(status_code=400, detail="שגיאה בקריאת קובץ CSV")
    else:
        raise HTTPException(status_code=400, detail="פורמט לא נתמך. יש להעלות xlsx או csv")

    if not raw_rows:
        raise HTTPException(status_code=400, detail="הקובץ ריק או לא מכיל שורות נתונים")

    if len(raw_rows) > MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"הקובץ מכיל יותר מ-{MAX_ROWS} שורות")

    validated = [_validate_row(r) for r in raw_rows]

    valid_count = sum(1 for v in validated if v["valid"])
    error_count = sum(1 for v in validated if not v["valid"])

    db = get_db()
    overwrite_count = 0
    for v in validated:
        if not v["valid"]:
            continue
        r = v["row"]
        existing = await db.unit_tenant_data.find_one({
            "project_id": project_id,
            "building_name": r.get("building_name", ""),
            "floor": r.get("floor", ""),
            "apartment_number": r.get("apartment_number", ""),
        })
        if existing:
            overwrite_count += 1
            v["overwrite"] = True
        else:
            v["overwrite"] = False

    seen_keys = {}
    for v in validated:
        if not v["valid"]:
            continue
        r = v["row"]
        key = (r.get("building_name", ""), r.get("floor", ""), r.get("apartment_number", ""))
        if key in seen_keys:
            v["warnings"].append("כפילות בקובץ (בניין+קומה+דירה)")
            seen_keys[key]["warnings"].append("כפילות בקובץ (בניין+קומה+דירה)")
        else:
            seen_keys[key] = v

    return {
        "rows": validated,
        "valid_count": valid_count,
        "error_count": error_count,
        "overwrite_count": overwrite_count,
        "total": len(validated),
    }


class ImportRow(BaseModel):
    building_name: str = ""
    floor: str = ""
    apartment_number: str
    tenant_name: str
    tenant_id_number: str = ""
    tenant_phone: str = ""
    tenant_email: str = ""
    tenant_2_name: str = ""
    tenant_2_id_number: str = ""
    source_row: Optional[int] = None


class ExecuteImportRequest(BaseModel):
    rows: List[ImportRow]


@router.post("/execute")
async def execute_import(
    project_id: str,
    body: ExecuteImportRequest,
    user: dict = Depends(get_current_user),
):
    await _check_import_access(user, project_id)

    if not body.rows:
        raise HTTPException(status_code=400, detail="אין שורות לייבוא")

    if len(body.rows) > MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"יותר מ-{MAX_ROWS} שורות")

    db = get_db()
    batch_id = str(uuid.uuid4())
    ts = _now()

    imported = 0
    skipped = 0
    errors = []

    from contractor_ops.phone_utils import normalize_israeli_phone

    for row in body.rows:
        row_data = row.dict()
        row_errors = []

        if not row_data.get("apartment_number", "").strip():
            row_errors.append("דירה חסרה")
        if not row_data.get("tenant_name", "").strip():
            row_errors.append("שם רוכש חסר")

        if row_errors:
            skipped += 1
            errors.append({
                "source_row": row_data.get("source_row"),
                "apartment": row_data.get("apartment_number", ""),
                "errors": row_errors,
            })
            continue

        phone_e164 = ""
        raw_phone = row_data.get("tenant_phone", "").strip()
        if raw_phone:
            try:
                result = normalize_israeli_phone(raw_phone)
                phone_e164 = result["phone_e164"]
            except (ValueError, Exception):
                phone_e164 = raw_phone

        tenant = {
            "name": row_data["tenant_name"].strip(),
            "id_number": row_data.get("tenant_id_number", "").strip(),
            "phone": phone_e164,
            "email": row_data.get("tenant_email", "").strip(),
        }

        tenant_2 = None
        t2_name = row_data.get("tenant_2_name", "").strip()
        if t2_name:
            tenant_2 = {
                "name": t2_name,
                "id_number": row_data.get("tenant_2_id_number", "").strip(),
            }

        doc = {
            "project_id": project_id,
            "building_name": row_data.get("building_name", "").strip(),
            "floor": row_data.get("floor", "").strip(),
            "apartment_number": row_data["apartment_number"].strip(),
            "tenant": tenant,
            "source": "g4_import",
            "imported_at": ts,
            "imported_by": user["id"],
            "import_batch_id": batch_id,
        }
        if tenant_2:
            doc["tenant_2"] = tenant_2
        else:
            doc["tenant_2"] = None

        try:
            await db.unit_tenant_data.update_one(
                {
                    "project_id": project_id,
                    "building_name": doc["building_name"],
                    "floor": doc["floor"],
                    "apartment_number": doc["apartment_number"],
                },
                {"$set": doc},
                upsert=True,
            )
            imported += 1
        except Exception as e:
            logger.error(f"Failed to upsert tenant data: {e}")
            skipped += 1
            errors.append({
                "source_row": row_data.get("source_row"),
                "apartment": row_data.get("apartment_number", ""),
                "errors": [str(e)],
            })

    await _audit("g4_import", batch_id, "executed", user["id"], {
        "project_id": project_id,
        "imported": imported,
        "skipped": skipped,
        "total_rows": len(body.rows),
    })

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "batch_id": batch_id,
    }
