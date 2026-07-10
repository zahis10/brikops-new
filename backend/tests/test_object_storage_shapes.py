"""
object_storage return-shape unit test (diary d4a fold-in 2d).

Pure/offline: it toggles the module-level backend flag and mocks the S3 client,
so it NEVER touches a real bucket or needs AWS credentials. It pins the two
stored-ref shapes the whole app depends on:

  - local mode: save_bytes(...) -> "/api/uploads/{key}"
  - s3 mode:    save_bytes(...) -> "s3://{key}"
  - generate_url passthrough for a local "/api/uploads/..." ref (returned as-is)
  - generate_url for an "s3://..." ref -> the presigned URL from the client

Run: cd backend && PYTHONPATH=/home/runner/workspace/backend python tests/test_object_storage_shapes.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("FILES_STORAGE_BACKEND", "local")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import object_storage as st  # noqa: E402

RESULTS = []


def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append({"test": name, "status": status, "detail": detail})
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


class _FakeS3:
    """Records uploads in-memory and returns a deterministic presigned URL.

    No network, no bucket — a stand-in for boto3's client.
    """

    def __init__(self):
        self.uploaded = []

    def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):  # noqa: N803
        self.uploaded.append((bucket, key, fileobj.read(), ExtraArgs))

    def generate_presigned_url(self, op, Params=None, ExpiresIn=None):  # noqa: N803
        return f"https://signed.example/{Params['Key']}?exp={ExpiresIn}"


# ---------------------------------------------------------------------------
section("LOCAL MODE — save_bytes returns /api/uploads/{key}")

# Isolate local writes to a temp dir so the test never pollutes uploads/.
_tmp = tempfile.mkdtemp(prefix="objstore_test_")
_orig_root = st._LOCAL_UPLOADS_ROOT
_orig_mode = st._BACKEND_MODE
st._LOCAL_UPLOADS_ROOT = Path(_tmp)
st._BACKEND_MODE = "local"

try:
    key = "diary/abc123.jpg"
    ref = st.save_bytes(b"hello-bytes", key, "image/jpeg")
    record("local save_bytes shape", ref == f"/api/uploads/{key}", f"got={ref}")
    record(
        "local file actually written",
        (Path(_tmp) / key).read_bytes() == b"hello-bytes",
    )

    # generate_url passthrough for a local ref.
    passthrough = st.generate_url(f"/api/uploads/{key}")
    record(
        "generate_url local passthrough",
        passthrough == f"/api/uploads/{key}",
        f"got={passthrough}",
    )
    record("generate_url empty passthrough", st.generate_url("") == "")
finally:
    st._LOCAL_UPLOADS_ROOT = _orig_root

# ---------------------------------------------------------------------------
section("S3 MODE (mocked client) — save_bytes returns s3://{key}")

_fake = _FakeS3()
_orig_get_s3 = st._get_s3
_orig_bucket = st._S3_BUCKET
st._BACKEND_MODE = "s3"
st._S3_BUCKET = "unit-test-bucket"
st._get_s3 = lambda: _fake
st._url_cache.clear()

try:
    s3key = "diary/def456.pdf"
    s3ref = st.save_bytes(b"pdf-bytes", s3key, "application/pdf")
    record("s3 save_bytes shape", s3ref == f"s3://{s3key}", f"got={s3ref}")
    record(
        "s3 upload routed to mock (no real bucket)",
        _fake.uploaded and _fake.uploaded[0][1] == s3key
        and _fake.uploaded[0][0] == "unit-test-bucket",
    )

    signed = st.generate_url(f"s3://{s3key}")
    record(
        "generate_url s3 -> presigned",
        signed == f"https://signed.example/{s3key}?exp={st._PRESIGN_EXPIRES}",
        f"got={signed}",
    )
finally:
    st._get_s3 = _orig_get_s3
    st._S3_BUCKET = _orig_bucket
    st._BACKEND_MODE = _orig_mode
    st._url_cache.clear()

# ---------------------------------------------------------------------------
section("SUMMARY")
passed = sum(1 for r in RESULTS if r["status"] == "PASS")
failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
print(f"\n  Total: {len(RESULTS)} | PASS: {passed} | FAIL: {failed}")
sys.exit(0 if failed == 0 else 1)
