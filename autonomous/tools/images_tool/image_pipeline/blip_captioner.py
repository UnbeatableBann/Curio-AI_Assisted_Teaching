import os
from io import BytesIO
from typing import Dict, List, Optional

import requests
import torch
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor

from autonomous.config.logger import get_logger

logger = get_logger(__name__)


class BlipCaptioner:
    def __init__(
        self, model_name="Salesforce/blip-image-captioning-large", device=None
    ):
        # Set device (GPU if available, else CPU)
        self.device = (
            device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        )

        # Load model and processor
        self.processor = BlipProcessor.from_pretrained(model_name)
        self.model = BlipForConditionalGeneration.from_pretrained(model_name).to(
            self.device
        )

    def load_image_from_url(self, url: str) -> Optional[Image.Image]:
        """Load an image from a URL, return None if request fails."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGB")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to load image from {url}: {e}")
            return None

    def generate_captions_from_url_batch(
        self, urls: List[str], batch_size: int = 4, max_new_tokens: int = 50
    ) -> Dict[str, str]:
        """Generate captions in batches for better performance."""
        captions: Dict[str, str] = {}
        for i in range(0, len(urls), batch_size):
            batch_urls = urls[i : i + batch_size]
            images = [self.load_image_from_url(url) for url in batch_urls]
            # Filter out None images
            valid_pairs = [
                (url, img) for url, img in zip(batch_urls, images) if img is not None
            ]

            if not valid_pairs:
                continue  # Skip if no valid images in this batch

            urls_filtered, images_filtered = zip(*valid_pairs)

            inputs = self.processor(
                images=list(images_filtered), return_tensors="pt", padding=True
            ).to(self.device)
            out = self.model.generate(**inputs, max_new_tokens=max_new_tokens)

            for j, url in enumerate(urls_filtered):
                captions[url] = self.processor.decode(out[j], skip_special_tokens=True)
        return captions

    def generate_caption_for_image(
        self, image_path: str, max_new_tokens: int = 50
    ) -> str:
        """Generate caption for a single image file."""
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        out = self.model.generate(**inputs, max_new_tokens=max_new_tokens)
        caption = self.processor.decode(out[0], skip_special_tokens=True)
        return caption

    def generate_captions_for_folder(
        self, image_folder: str, max_new_tokens: int = 50
    ) -> dict:
        """Generate captions for all images in a local folder."""
        captions = {}
        for filename in os.listdir(image_folder):
            if filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                image_path = os.path.join(image_folder, filename)
                caption = self.generate_caption(
                    image_path, max_new_tokens=max_new_tokens
                )
                captions[filename] = caption
        return captions


captioner = BlipCaptioner()
