import os
from fastapi import HTTPException

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'}

# S7 — contractor proof uploads accept images AND PDFs (certificates, invoices,
# inspection reports). Used by tasks_router.py contractor-proof handler.
# Construction-domain decision (Zahi 2026-04-27): PDFs are first-class proofs.
ALLOWED_PROOF_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | {'.pdf'}
ALLOWED_PROOF_TYPES = ALLOWED_IMAGE_TYPES | {'application/pdf'}

ALLOWED_PLAN_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.xlsx', '.xls', '.dwg', '.dxf'}
ALLOWED_PLAN_TYPES = {
    'application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel', 'application/dwg', 'application/dxf',
    'image/vnd.dwg',
}

ALLOWED_IMPORT_EXTENSIONS = {'.xlsx', '.xls', '.csv'}
ALLOWED_IMPORT_TYPES = {
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel', 'text/csv',
}


def validate_upload(file, allowed_extensions, allowed_types):
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=422, detail='סוג קובץ לא נתמך')
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(status_code=422, detail='סוג קובץ לא נתמך')
