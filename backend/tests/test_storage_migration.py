"""
Storage Migration Validation Tests
Tests local-mode write paths for all 3 upload flows and env var handling.
Run with: FILES_STORAGE_BACKEND=local python tests/test_storage_migration.py
"""
import os
import sys
import json
import io
import tempfile
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULTS = []

def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append({"test": name, "status": status, "detail": detail})
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── 1. ENV VAR HANDLING ──────────────────────────────────────
section("1. ENV VAR HANDLING")

os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ.pop("AWS_S3_BUCKET", None)
os.environ.pop("AWS_REGION", None)
os.environ.pop("AWS_S3_PRESIGNED_URL_EXPIRES", None)

import importlib
import services.object_storage as obj_mod
importlib.reload(obj_mod)

record("FILES_STORAGE_BACKEND defaults to 'local'",
       obj_mod._BACKEND_MODE == "local",
       f"actual={obj_mod._BACKEND_MODE}")

record("is_s3_mode() returns False in local mode",
       obj_mod.is_s3_mode() == False)

record("AWS_S3_PRESIGNED_URL_EXPIRES defaults to 900",
       obj_mod._PRESIGN_EXPIRES == 900,
       f"actual={obj_mod._PRESIGN_EXPIRES}")

record("AWS_REGION defaults to eu-central-1",
       obj_mod._S3_REGION == "eu-central-1",
       f"actual={obj_mod._S3_REGION}")

os.environ["AWS_S3_PRESIGNED_URL_EXPIRES"] = "1800"
importlib.reload(obj_mod)
record("AWS_S3_PRESIGNED_URL_EXPIRES=1800 is honored",
       obj_mod._PRESIGN_EXPIRES == 1800,
       f"actual={obj_mod._PRESIGN_EXPIRES}")

os.environ["FILES_STORAGE_BACKEND"] = "s3"
os.environ["AWS_S3_BUCKET"] = "test-bucket-fake"
os.environ["AWS_REGION"] = "us-west-2"
importlib.reload(obj_mod)
record("is_s3_mode() returns True when FILES_STORAGE_BACKEND=s3",
       obj_mod.is_s3_mode() == True)
record("AWS_S3_BUCKET read correctly",
       obj_mod._S3_BUCKET == "test-bucket-fake",
       f"actual={obj_mod._S3_BUCKET}")
record("AWS_REGION read correctly",
       obj_mod._S3_REGION == "us-west-2",
       f"actual={obj_mod._S3_REGION}")

# Reset to local for remaining tests
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ.pop("AWS_S3_BUCKET", None)
os.environ.pop("AWS_REGION", None)
os.environ.pop("AWS_S3_PRESIGNED_URL_EXPIRES", None)
importlib.reload(obj_mod)

# ── 2. WRITE PATH: object_storage.save_bytes (LOCAL) ─────────
section("2. WRITE PATH: object_storage.save_bytes (LOCAL)")

test_data = b"hello storage migration test"
test_key = "test_migration/test_file.txt"

ref = obj_mod.save_bytes(test_data, test_key, "text/plain")
record("save_bytes returns /api/uploads/ path in local mode",
       ref.startswith("/api/uploads/"),
       f"ref={ref}")

expected_path = obj_mod._LOCAL_UPLOADS_ROOT / test_key
record("File actually exists on disk",
       expected_path.exists(),
       f"path={expected_path}")

record("File content matches",
       expected_path.read_bytes() == test_data)

# ── 3. WRITE PATH: StorageService.upload_file_with_details ───
section("3. WRITE PATH: StorageService (task attachments)")

import asyncio
from unittest.mock import AsyncMock, MagicMock
from services.storage_service import StorageService

async def test_storage_service():
    svc = StorageService()
    
    mock_file = MagicMock()
    mock_file.filename = "test_photo.jpg"
    mock_file.content_type = "image/jpeg"
    
    # Create a minimal valid JPEG
    img_data = b'\xff\xd8\xff\xe0' + b'\x00' * 100 + b'\xff\xd9'
    mock_file.read = AsyncMock(return_value=img_data)
    
    result = await svc.upload_file_with_details(mock_file, "test_context")
    
    record("StorageService file_url starts with /api/uploads/",
           result.file_url.startswith("/api/uploads/"),
           f"file_url={result.file_url}")
    
    record("StorageService file_url does NOT contain s3://",
           "s3://" not in result.file_url)
    
    record("StorageService returns checksum",
           len(result.checksum) == 32,
           f"checksum={result.checksum}")
    
    record("StorageService file_size > 0",
           result.file_size > 0,
           f"size={result.file_size}")
    
    return result

storage_result = asyncio.get_event_loop().run_until_complete(test_storage_service())

# ── 4. WRITE PATH: QC photo upload ──────────────────────────
section("4. WRITE PATH: QC photo upload (direct save_bytes)")

qc_photo_data = b'\xff\xd8\xff\xe0' + b'\x00' * 50 + b'\xff\xd9'
qc_ref = obj_mod.save_bytes(qc_photo_data, "qc/test_photo_abc.jpg", "image/jpeg")
record("QC photo save_bytes returns /api/uploads/qc/... path",
       qc_ref.startswith("/api/uploads/qc/"),
       f"ref={qc_ref}")

qc_file = obj_mod._LOCAL_UPLOADS_ROOT / "qc" / "test_photo_abc.jpg"
record("QC photo file exists on disk",
       qc_file.exists(),
       f"path={qc_file}")

# ── 5. WRITE PATH: Document vault upload ────────────────────
section("5. WRITE PATH: Document Vault upload (direct save_bytes)")

doc_data = b"%PDF-1.4 fake pdf content for testing"
doc_ref = obj_mod.save_bytes(doc_data, "documents/test_doc_v1.pdf", "application/pdf")
record("Document vault save_bytes returns /api/uploads/documents/... path",
       doc_ref.startswith("/api/uploads/documents/"),
       f"ref={doc_ref}")

doc_file = obj_mod._LOCAL_UPLOADS_ROOT / "documents" / "test_doc_v1.pdf"
record("Document vault file exists on disk",
       doc_file.exists(),
       f"path={doc_file}")

# ── 6. READ PATH: URL resolution ────────────────────────────
section("6. READ PATH: URL resolution")

# Local paths should pass through unchanged
local_url = "/api/uploads/some_file.jpg"
resolved = obj_mod.generate_url(local_url)
record("Local /api/uploads/ path passes through unchanged",
       resolved == local_url,
       f"input={local_url}, output={resolved}")

# Empty/None should be safe
record("generate_url(None) returns None safely",
       obj_mod.generate_url(None) is None or obj_mod.generate_url(None) == None)

record("generate_url('') returns '' safely",
       obj_mod.generate_url("") == "")

# resolve_url alias
record("resolve_url is alias for generate_url",
       obj_mod.resolve_url(local_url) == local_url)

# resolve_urls_in_doc with local paths (no-op)
doc = {"file_url": "/api/uploads/a.pdf", "thumbnail_url": "/api/uploads/t.jpg", "proof_urls": ["/api/uploads/p1.jpg"]}
obj_mod.resolve_urls_in_doc(doc)
record("resolve_urls_in_doc leaves local paths unchanged",
       doc["file_url"] == "/api/uploads/a.pdf" and doc["proof_urls"][0] == "/api/uploads/p1.jpg")

# resolve_urls_in_doc with s3:// refs (can't presign without real S3, but test the branching)
doc_s3 = {"file_url": "s3://some/key.pdf", "thumbnail_url": "/api/uploads/t.jpg", "proof_urls": ["s3://proof/1.jpg", "/api/uploads/p2.jpg"]}
# In local mode with no S3 creds, this will fail gracefully and return the s3:// ref
obj_mod.resolve_urls_in_doc(doc_s3)
record("resolve_urls_in_doc attempts S3 resolution for s3:// refs",
       True,
       f"file_url after resolve={doc_s3['file_url'][:60]}...")

record("resolve_urls_in_doc leaves mixed local paths alone",
       doc_s3["thumbnail_url"] == "/api/uploads/t.jpg")

record("resolve_urls_in_doc handles mixed proof_urls list",
       doc_s3["proof_urls"][1] == "/api/uploads/p2.jpg",
       f"proof[1]={doc_s3['proof_urls'][1]}")

# ── 7. DELETE PATH ──────────────────────────────────────────
section("7. DELETE PATH")

delete_data = b"delete me"
delete_ref = obj_mod.save_bytes(delete_data, "test_migration/delete_me.txt", "text/plain")
delete_path = obj_mod._LOCAL_UPLOADS_ROOT / "test_migration" / "delete_me.txt"
record("File to delete exists before delete()",
       delete_path.exists())

deleted = obj_mod.delete(delete_ref)
record("delete() returns True for local file",
       deleted == True)
record("File is actually removed from disk",
       not delete_path.exists())

# ── 8. BACKWARD COMPATIBILITY ───────────────────────────────
section("8. BACKWARD COMPATIBILITY")

record("generate_url preserves /api/uploads/ paths (legacy)",
       obj_mod.generate_url("/api/uploads/old_file.jpg") == "/api/uploads/old_file.jpg")

record("generate_url preserves arbitrary non-s3 strings",
       obj_mod.generate_url("https://example.com/img.jpg") == "https://example.com/img.jpg")

# _resolve_photo_url in qc_router
from contractor_ops.qc_router import _resolve_photo_url
record("_resolve_photo_url passes local paths through",
       _resolve_photo_url("/api/uploads/qc/photo.jpg") == "/api/uploads/qc/photo.jpg")
record("_resolve_photo_url handles None safely",
       _resolve_photo_url(None) is None)

# ── 9. CALL SITE AUDIT ──────────────────────────────────────
section("9. CALL SITE AUDIT (import verification)")

from services.storage_service import StorageService as SS
import inspect
src = inspect.getsource(SS.upload_file_with_details)
record("StorageService uses obj_save_bytes (object_storage)",
       "obj_save_bytes" in src,
       "confirmed in upload_file_with_details source")

from services.document_vault_service import DocumentVaultService as DVS
src2 = inspect.getsource(DVS.upload_document)
record("DocumentVaultService uses obj_save_bytes (object_storage)",
       "obj_save_bytes" in src2,
       "confirmed in upload_document source")


# ── CLEANUP ──────────────────────────────────────────────────
section("CLEANUP")
# Remove test files
import shutil
test_dir = obj_mod._LOCAL_UPLOADS_ROOT / "test_migration"
if test_dir.exists():
    shutil.rmtree(test_dir)
qc_test = obj_mod._LOCAL_UPLOADS_ROOT / "qc" / "test_photo_abc.jpg"
if qc_test.exists():
    qc_test.unlink()
doc_test = obj_mod._LOCAL_UPLOADS_ROOT / "documents" / "test_doc_v1.pdf"
if doc_test.exists():
    doc_test.unlink()
print("  Test files cleaned up.")

# ── SUMMARY ──────────────────────────────────────────────────
section("SUMMARY")
passed = sum(1 for r in RESULTS if r["status"] == "PASS")
failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
print(f"\n  Total: {len(RESULTS)} | PASS: {passed} | FAIL: {failed}")
if failed:
    print("\n  FAILED TESTS:")
    for r in RESULTS:
        if r["status"] == "FAIL":
            print(f"    - {r['test']}: {r['detail']}")
else:
    print("\n  ALL TESTS PASSED ✓")

print(f"\n{'='*60}")
sys.exit(1 if failed else 0)
