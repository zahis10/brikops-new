import os
import re
from fastapi import HTTPException

# Single source of truth for the safety-upload storage-ref shape (batch d4a,
# fold-in 2e). A stored ref is the safety-upload output: safety/{project}/{file},
# optionally with the local-backend "/api/uploads/" prefix or the "s3://" scheme.
# No other schemes, no "..". This ONE compiled object is imported (never
# re-compiled) by every site that validates a photo ref — the write gates in
# work_diary_router / safety.workers AND the SSRF read gate in work_diary_pdf —
# so they can never drift byte-for-byte again (the d3-fix2 lesson).
SAFETY_STORED_REF_RE = re.compile(
    r"^(?:/api/uploads/|s3://)?safety/([A-Za-z0-9_-]+)/[A-Za-z0-9][A-Za-z0-9.+_-]*$")

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'}

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
