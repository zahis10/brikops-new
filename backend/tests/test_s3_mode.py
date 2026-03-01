"""
S3-mode storage validation test.
Runs against real AWS credentials from env secrets.
"""
import os
import sys
import time

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

section("S3 MODE ENV CHECK")

backend = os.environ.get("FILES_STORAGE_BACKEND", "")
bucket = os.environ.get("AWS_S3_BUCKET", "")
region = os.environ.get("AWS_REGION", "")
key_id = os.environ.get("AWS_ACCESS_KEY_ID", "")
secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
presign_ttl = os.environ.get("AWS_S3_PRESIGNED_URL_EXPIRES", "")

print(f"  FILES_STORAGE_BACKEND = {backend}")
print(f"  AWS_S3_BUCKET = {bucket}")
print(f"  AWS_REGION = {region}")
print(f"  AWS_ACCESS_KEY_ID = {'****' + key_id[-4:] if key_id else '(not set)'}")
print(f"  AWS_SECRET_ACCESS_KEY = {'****' + secret[-4:] if secret else '(not set)'}")
print(f"  AWS_S3_PRESIGNED_URL_EXPIRES = {presign_ttl or '(not set, defaults to 900)'}")

record("FILES_STORAGE_BACKEND is 's3'",
       backend.lower() == "s3",
       f"actual='{backend}'")
record("AWS_S3_BUCKET is set",
       bool(bucket),
       f"bucket={bucket}")
record("AWS_REGION is set",
       bool(region),
       f"region={region}")
record("AWS_ACCESS_KEY_ID is set",
       bool(key_id))
record("AWS_SECRET_ACCESS_KEY is set",
       bool(secret))

if not all([backend.lower() == "s3", bucket, region, key_id, secret]):
    print("\n  ABORT: Missing S3 credentials. Cannot run S3 tests.")
    section("SUMMARY")
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    print(f"\n  Total: {len(RESULTS)} | PASS: {passed} | FAIL: {failed}")
    sys.exit(1)

import importlib
import services.object_storage as obj_mod
importlib.reload(obj_mod)

record("is_s3_mode() returns True",
       obj_mod.is_s3_mode() == True)

record("_S3_BUCKET matches env",
       obj_mod._S3_BUCKET == bucket)

record("_PRESIGN_EXPIRES uses env value (not hardcoded)",
       str(obj_mod._PRESIGN_EXPIRES) == presign_ttl if presign_ttl else obj_mod._PRESIGN_EXPIRES == 900,
       f"actual={obj_mod._PRESIGN_EXPIRES}, env={presign_ttl or 'default 900'}")

section("S3 UPLOAD TEST")

test_key = f"_migration_test/validation_{int(time.time())}.txt"
test_data = b"BrikOps S3 storage migration validation test"
test_content_type = "text/plain"

try:
    ref = obj_mod.save_bytes(test_data, test_key, test_content_type)
    record("save_bytes to S3 succeeded",
           True,
           f"ref={ref}")
    record("Returned ref starts with s3://",
           ref.startswith("s3://"),
           f"ref={ref}")
    record("Returned ref contains the key",
           test_key in ref,
           f"expected key={test_key}")
except Exception as e:
    record("save_bytes to S3 succeeded", False, f"error={e}")
    ref = None

section("S3 PRESIGNED URL TEST")

if ref:
    try:
        url = obj_mod.generate_url(ref)
        record("generate_url returns a presigned URL",
               url.startswith("https://"),
               f"url={url[:120]}...")
        record("Presigned URL contains bucket name",
               bucket in url,
               f"bucket={bucket}")
        record("Presigned URL contains the key",
               test_key.replace("/", "%2F") in url or test_key in url)
        
        import urllib.request
        resp = urllib.request.urlopen(url)
        body = resp.read()
        record("Presigned URL is accessible (HTTP 200)",
               resp.status == 200,
               f"status={resp.status}")
        record("Downloaded content matches uploaded content",
               body == test_data,
               f"downloaded {len(body)} bytes")
    except Exception as e:
        record("generate_url returns a presigned URL", False, f"error={e}")

section("BACKWARD COMPATIBILITY IN S3 MODE")

legacy_local = "/api/uploads/old_photo_abc.jpg"
resolved_legacy = obj_mod.generate_url(legacy_local)
record("Legacy /api/uploads/ path passes through unchanged in S3 mode",
       resolved_legacy == legacy_local,
       f"input={legacy_local}, output={resolved_legacy}")

resolved_none = obj_mod.generate_url(None)
record("generate_url(None) safe in S3 mode",
       resolved_none is None)

resolved_empty = obj_mod.generate_url("")
record("generate_url('') safe in S3 mode",
       resolved_empty == "")

doc = {
    "file_url": "s3://some/file.pdf",
    "thumbnail_url": "/api/uploads/old_thumb.jpg",
    "proof_urls": ["s3://proof/1.jpg", "/api/uploads/old_proof.jpg"]
}
obj_mod.resolve_urls_in_doc(doc)
record("resolve_urls_in_doc: s3:// file_url resolved to https://",
       doc["file_url"].startswith("https://"),
       f"resolved={doc['file_url'][:80]}...")
record("resolve_urls_in_doc: local thumbnail_url unchanged",
       doc["thumbnail_url"] == "/api/uploads/old_thumb.jpg")
record("resolve_urls_in_doc: s3:// proof resolved",
       doc["proof_urls"][0].startswith("https://"))
record("resolve_urls_in_doc: local proof unchanged",
       doc["proof_urls"][1] == "/api/uploads/old_proof.jpg")

section("S3 DELETE TEST")

if ref:
    try:
        deleted = obj_mod.delete(ref)
        record("delete() from S3 succeeded",
               deleted == True)
        
        import urllib.request, urllib.error
        check_url = obj_mod.generate_url(ref)
        try:
            urllib.request.urlopen(check_url)
            record("File actually deleted from S3", False, "still accessible")
        except urllib.error.HTTPError as he:
            record("File actually deleted from S3 (403/404 after delete)",
                   he.code in (403, 404),
                   f"status={he.code}")
    except Exception as e:
        record("delete() from S3 succeeded", False, f"error={e}")

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
    print("\n  ALL TESTS PASSED")
print(f"\n{'='*60}")
sys.exit(1 if failed else 0)
