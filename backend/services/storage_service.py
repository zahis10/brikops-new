import os
import io
import uuid
import hashlib
import asyncio
import time
from typing import Tuple, Dict, Any
from dataclasses import dataclass
from fastapi import UploadFile
from PIL import Image
import logging
from services.object_storage import save_bytes as obj_save_bytes, generate_url as obj_generate_url, is_s3_mode

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result of a file upload operation"""
    file_url: str
    thumbnail_url: str
    checksum: str
    file_size: int
    stored_filename: str


class StorageService:
    def __init__(self):
        self.local_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
        os.makedirs(self.local_dir, exist_ok=True)
    
    def _compute_checksum(self, content: bytes) -> str:
        """Compute MD5 checksum of file content"""
        return hashlib.md5(content).hexdigest()
    
    async def upload_file(self, file: UploadFile, context_id: str) -> Tuple[str, str]:
        """
        Legacy method - Upload file and return (file_url, thumbnail_url)
        Kept for backward compatibility
        """
        result = await self.upload_file_with_details(file, context_id)
        return result.file_url, result.thumbnail_url
    
    async def upload_file_with_details(self, file: UploadFile, context_id: str) -> UploadResult:
        """
        Upload file and return full details including checksum
        
        Args:
            file: The uploaded file
            context_id: Context identifier (room_id, inspection_id, etc.)
            
        Returns:
            UploadResult with file_url, thumbnail_url, checksum, file_size
        """
        try:
            # Stage 1: Read file content
            logger.info(f"[UPLOAD:STAGE1:RECEIVED] context={context_id}, filename={file.filename}, content_type={file.content_type}")
            content = await file.read()
            file_size = len(content)
            
            if file_size == 0:
                logger.error(f"[UPLOAD:STAGE1:ERROR] Empty file received: {file.filename}")
                raise ValueError("Empty file received")
            
            # Stage 2: Compute checksum
            checksum = self._compute_checksum(content)
            logger.info(f"[UPLOAD:STAGE2:CHECKSUM] checksum={checksum}, size={file_size}")
            
            file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
            unique_name = f"{uuid.uuid4()}.{file_ext}"
            key = f"attachments/{unique_name}"
            
            content_type = file.content_type or "application/octet-stream"
            t0 = time.time()
            stored_ref = await asyncio.to_thread(obj_save_bytes, content, key, content_type)
            logger.info(f"[UPLOAD:STAGE3:STORED] ref={stored_ref} elapsed={time.time()-t0:.2f}s")

            thumbnail_ref = stored_ref
            if file.content_type and file.content_type.startswith('image/'):
                try:
                    thumbnail_name = f"attachments/thumb_{unique_name}"
                    img = Image.open(io.BytesIO(content))
                    img.thumbnail((300, 300))
                    thumb_buf = io.BytesIO()
                    img_format = 'JPEG' if unique_name.lower().endswith(('.jpg', '.jpeg')) else 'PNG'
                    if img_format == 'JPEG' and img.mode in ('RGBA', 'P', 'LA'):
                        img = img.convert('RGB')
                    img.save(thumb_buf, format=img_format)
                    thumb_bytes = thumb_buf.getvalue()
                    t0_thumb = time.time()
                    thumbnail_ref = await asyncio.to_thread(obj_save_bytes, thumb_bytes, thumbnail_name, content_type)
                    logger.info(f"[UPLOAD:STAGE4:THUMBNAIL] ref={thumbnail_ref} elapsed={time.time()-t0_thumb:.2f}s")
                except Exception as thumb_err:
                    logger.warning(f"[UPLOAD:STAGE4:THUMBNAIL_FAILED] error={thumb_err}, using original")

            file_url = stored_ref
            thumbnail_url = thumbnail_ref

            logger.info(f"[UPLOAD:COMPLETE] file_url={file_url}, thumbnail_url={thumbnail_url}, checksum={checksum}")

            return UploadResult(
                file_url=file_url,
                thumbnail_url=thumbnail_url,
                checksum=checksum,
                file_size=file_size,
                stored_filename=unique_name
            )
        
        except Exception as e:
            logger.error(f'[UPLOAD:ERROR] stage=unknown, error={str(e)}')
            raise