import os
import io
import logging
import time
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_url_cache = {}
_url_cache_lock = threading.Lock()
_URL_CACHE_TTL = 600
_URL_CACHE_MAX = 5000

_BACKEND_MODE = os.environ.get("FILES_STORAGE_BACKEND", "local").lower()
_S3_BUCKET = os.environ.get("AWS_S3_BUCKET", "")
_S3_REGION = os.environ.get("AWS_REGION", "eu-central-1")
_PRESIGN_EXPIRES = int(os.environ.get("AWS_S3_PRESIGNED_URL_EXPIRES", "900"))

_LOCAL_UPLOADS_ROOT = Path(__file__).parent.parent / "uploads"
_LOCAL_UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)

_s3_client = None
_s3_client_created_at = 0
_S3_CLIENT_MAX_AGE = 3000


def _get_s3():
    global _s3_client, _s3_client_created_at
    now = time.monotonic()
    if _s3_client is None or (now - _s3_client_created_at) > _S3_CLIENT_MAX_AGE:
        import boto3
        from botocore.config import Config
        cfg = Config(signature_version='s3v4', s3={'addressing_style': 'virtual'})
        key_id = os.environ.get("AWS_ACCESS_KEY_ID")
        secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
        if key_id and secret:
            _s3_client = boto3.client(
                "s3",
                region_name=_S3_REGION,
                aws_access_key_id=key_id,
                aws_secret_access_key=secret,
                config=cfg,
            )
        else:
            _s3_client = boto3.client(
                "s3",
                region_name=_S3_REGION,
                config=cfg,
            )
        _s3_client_created_at = now
        logger.info(f"[STORAGE:S3] client created/refreshed (explicit_creds={'yes' if key_id else 'no'})")
    return _s3_client


def is_s3_mode() -> bool:
    return _BACKEND_MODE == "s3"


def save_bytes(data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    """Save bytes to storage.

    Args:
        data: file content
        key: relative path / object key, e.g. "qc/abc.jpg" or "documents/xyz.pdf"
        content_type: MIME type

    Returns:
        For local mode: the URL path e.g. "/api/uploads/qc/abc.jpg"
        For S3 mode: the S3 object key (same as *key* arg) prefixed with "s3://"
    """
    if is_s3_mode():
        try:
            s3 = _get_s3()
            s3.upload_fileobj(
                io.BytesIO(data),
                _S3_BUCKET,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            logger.info(f"[STORAGE:S3:SAVED] bucket={_S3_BUCKET} key={key} size={len(data)}")
            return f"s3://{key}"
        except Exception as e:
            logger.error(f"[STORAGE:S3:ERROR] key={key} error={e}")
            raise
    else:
        local_path = _LOCAL_UPLOADS_ROOT / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        logger.info(f"[STORAGE:LOCAL:SAVED] path={local_path} size={len(data)}")
        return f"/api/uploads/{key}"


def generate_url(stored_ref: str) -> str:
    """Return a usable URL for a stored reference.

    - Old local paths ("/api/uploads/..."): returned as-is.
    - S3 references ("s3://..."): generate a presigned GET URL.
    - Plain keys (legacy compat): treated as local.
    """
    if not stored_ref:
        return stored_ref

    if stored_ref.startswith("s3://"):
        key = stored_ref[5:]
        now = time.monotonic()
        with _url_cache_lock:
            cached = _url_cache.get(key)
            if cached and (now - cached[1]) < _URL_CACHE_TTL:
                return cached[0]
        try:
            s3 = _get_s3()
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": _S3_BUCKET, "Key": key},
                ExpiresIn=_PRESIGN_EXPIRES,
            )
            with _url_cache_lock:
                if len(_url_cache) >= _URL_CACHE_MAX:
                    oldest_key = min(_url_cache, key=lambda k: _url_cache[k][1])
                    del _url_cache[oldest_key]
                _url_cache[key] = (url, now)
            return url
        except Exception as e:
            logger.error(f"[STORAGE:S3:PRESIGN_ERROR] key={key} error={e}")
            return stored_ref

    return stored_ref


def delete(stored_ref: str) -> bool:
    """Delete a stored object. Returns True on success."""
    if not stored_ref:
        return False

    if stored_ref.startswith("s3://"):
        key = stored_ref[5:]
        try:
            s3 = _get_s3()
            s3.delete_object(Bucket=_S3_BUCKET, Key=key)
            logger.info(f"[STORAGE:S3:DELETED] key={key}")
            return True
        except Exception as e:
            logger.error(f"[STORAGE:S3:DELETE_ERROR] key={key} error={e}")
            return False

    if stored_ref.startswith("/api/uploads/"):
        rel = stored_ref[len("/api/uploads/"):]
        local_path = _LOCAL_UPLOADS_ROOT / rel
        if local_path.exists():
            local_path.unlink()
            logger.info(f"[STORAGE:LOCAL:DELETED] path={local_path}")
            return True
    return False


def resolve_url(url):
    """Convenience alias for generate_url — resolve any stored ref to a usable URL."""
    return generate_url(url) if url else url


def resolve_urls_in_doc(doc, fields=("file_url", "thumbnail_url", "attachment_url", "pdf_url")):
    """Resolve S3 refs to presigned URLs in a dict, in-place. Returns the same dict."""
    if not doc or not isinstance(doc, dict):
        return doc
    for f in fields:
        v = doc.get(f)
        if v and isinstance(v, str) and v.startswith("s3://"):
            doc[f] = generate_url(v)
    proof = doc.get("proof_urls")
    if proof and isinstance(proof, list):
        doc["proof_urls"] = [generate_url(u) if isinstance(u, str) and u.startswith("s3://") else u for u in proof]
    return doc


def log_backend():
    if _BACKEND_MODE == "s3":
        if not _S3_BUCKET:
            msg = "[STORAGE:FATAL] FILES_STORAGE_BACKEND=s3 but AWS_S3_BUCKET is empty or not set"
            logger.critical(msg)
            raise RuntimeError(msg)
        has_key = bool(os.environ.get("AWS_ACCESS_KEY_ID"))
        has_secret = bool(os.environ.get("AWS_SECRET_ACCESS_KEY"))
        cred_mode = "explicit" if (has_key and has_secret) else "IAM-role"
        logger.info(f"[STORAGE] backend=s3 bucket={_S3_BUCKET} region={_S3_REGION} presign_expires={_PRESIGN_EXPIRES}s credentials={cred_mode} client_refresh={_S3_CLIENT_MAX_AGE}s")
    else:
        logger.info(f"[STORAGE] backend=local dir={_LOCAL_UPLOADS_ROOT}")
