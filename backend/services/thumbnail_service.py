import io
import logging
import asyncio
from typing import Optional

from PIL import Image
from services.object_storage import save_bytes as obj_save_bytes

logger = logging.getLogger(__name__)

THUMB_WIDTH = 300
THUMB_QUALITY = 75
IMAGE_MIMES = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}

_poppler_available: Optional[bool] = None


def _check_poppler() -> bool:
    global _poppler_available
    if _poppler_available is not None:
        return _poppler_available
    import shutil
    _poppler_available = shutil.which('pdftoppm') is not None
    if not _poppler_available:
        logger.info("[THUMB] poppler not available (pdftoppm not found) — PDF thumbnails disabled")
    else:
        logger.info("[THUMB] poppler detected via pdftoppm")
    return _poppler_available


def _generate_image_thumb(file_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode in ('RGBA', 'P', 'LA'):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    ratio = THUMB_WIDTH / img.width
    new_h = int(img.height * ratio)
    img = img.resize((THUMB_WIDTH, new_h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=THUMB_QUALITY)
    return buf.getvalue()


def _generate_pdf_thumb(file_bytes: bytes) -> Optional[bytes]:
    if not _check_poppler():
        return None
    try:
        from pdf2image import convert_from_bytes
        pages = convert_from_bytes(file_bytes, first_page=1, last_page=1, size=(THUMB_WIDTH, None))
        if not pages:
            return None
        img = pages[0].convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=THUMB_QUALITY)
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"[THUMB] PDF conversion failed: {e}")
        return None


async def generate_thumbnail(file_bytes: bytes, file_type: str, storage_key: str) -> Optional[str]:
    try:
        thumb_bytes = None
        if file_type in IMAGE_MIMES:
            thumb_bytes = await asyncio.to_thread(_generate_image_thumb, file_bytes)
        elif file_type == 'application/pdf':
            thumb_bytes = await asyncio.to_thread(_generate_pdf_thumb, file_bytes)

        if not thumb_bytes:
            return None

        thumb_key = f"{storage_key}_thumb.jpg"
        stored_ref = await asyncio.to_thread(obj_save_bytes, thumb_bytes, thumb_key, 'image/jpeg')
        logger.info(f"[THUMB] Generated thumbnail: {thumb_key} ({len(thumb_bytes)} bytes)")
        return stored_ref
    except Exception as e:
        logger.warning(f"[THUMB] Failed for {storage_key}: {e}")
        return None
