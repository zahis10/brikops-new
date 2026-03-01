import os
import io
import logging
import requests
from typing import Optional, Tuple
from PIL import Image as PILImage
from reportlab.lib.units import cm

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Process and prepare images for PDF inclusion"""
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports', 'image_cache')
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # Maximum dimensions to fit in PDF table cell
        self.max_width = 14 * cm  # Max width in PDF
        self.max_height = 10 * cm  # Max height in PDF
    
    def download_and_process_image(
        self,
        image_url: str,
        finding_id: str,
        index: int = 0
    ) -> Optional[str]:
        """Download image from URL and process for PDF inclusion
        
        Args:
            image_url: URL or path to image
            finding_id: Finding ID for caching
            index: Image index for this finding
            
        Returns:
            Path to processed image file, or None if failed
        """
        try:
            # Check if already cached
            cache_filename = f"{finding_id}_{index}.jpg"
            cache_path = os.path.join(self.cache_dir, cache_filename)
            
            if os.path.exists(cache_path):
                logger.debug(f'Using cached image: {cache_path}')
                return cache_path
            
            # Download image
            if image_url.startswith('http'):
                response = requests.get(image_url, timeout=10)
                if response.status_code != 200:
                    logger.warning(f'Failed to download image: {image_url}')
                    return None
                image_data = io.BytesIO(response.content)
            else:
                # Local file path
                if not os.path.exists(image_url):
                    logger.warning(f'Image file not found: {image_url}')
                    return None
                image_data = image_url
            
            # Open and process image
            with PILImage.open(image_data) as img:
                # Convert to RGB if needed
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # Calculate new dimensions preserving aspect ratio
                width, height = img.size
                aspect_ratio = width / height
                
                # Fit within max bounds
                if width > self.max_width or height > self.max_height:
                    if aspect_ratio > 1:  # Wider than tall
                        new_width = min(width, self.max_width)
                        new_height = new_width / aspect_ratio
                    else:  # Taller than wide
                        new_height = min(height, self.max_height)
                        new_width = new_height * aspect_ratio
                    
                    # Resize
                    img = img.resize(
                        (int(new_width), int(new_height)),
                        PILImage.Resampling.LANCZOS
                    )
                
                # Save to cache
                img.save(cache_path, 'JPEG', quality=85, optimize=True)
                logger.info(f'Processed and cached image: {cache_path}')
                return cache_path
        
        except Exception as e:
            logger.error(f'Error processing image {image_url}: {str(e)}')
            return None
    
    def get_image_dimensions(self, image_path: str) -> Tuple[float, float]:
        """Get image dimensions in cm for PDF placement
        
        Returns:
            (width_cm, height_cm)
        """
        try:
            with PILImage.open(image_path) as img:
                width_px, height_px = img.size
                # Convert pixels to cm (assuming 72 DPI)
                width_cm = (width_px / 72) * 2.54
                height_cm = (height_px / 72) * 2.54
                
                # Ensure within max bounds
                if width_cm > 14:
                    scale = 14 / width_cm
                    width_cm = 14
                    height_cm = height_cm * scale
                
                if height_cm > 10:
                    scale = 10 / height_cm
                    height_cm = 10
                    width_cm = width_cm * scale
                
                return (width_cm, height_cm)
        except Exception as e:
            logger.error(f'Error getting image dimensions: {str(e)}')
            return (10, 8)  # Default dimensions
    
    def create_fallback_image(self, message: str) -> str:
        """Create a fallback image with Hebrew text message
        
        Args:
            message: Hebrew message to display
            
        Returns:
            Path to fallback image
        """
        fallback_path = os.path.join(self.cache_dir, 'fallback.jpg')
        
        try:
            # Create a simple gray image with text
            img = PILImage.new('RGB', (400, 300), color=(240, 240, 240))
            
            # Save
            img.save(fallback_path, 'JPEG', quality=85)
            return fallback_path
        
        except Exception as e:
            logger.error(f'Error creating fallback image: {str(e)}')
            return None