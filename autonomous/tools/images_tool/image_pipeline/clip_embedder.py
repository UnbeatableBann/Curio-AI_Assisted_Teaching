from io import BytesIO
from typing import Dict, List, Optional, Tuple

import requests
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from autonomous.config.logger import get_logger

logger = get_logger(__name__)


class CLIPEmbedder:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            model_id = "openai/clip-vit-base-patch32"
            logger.info(f"Loading CLIP model: {model_id}...")
            self.model = CLIPModel.from_pretrained(model_id).to(self.device)
            self.processor = CLIPProcessor.from_pretrained(model_id)
            self.model.eval()
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            raise

    def _load_image_from_url(self, url: str) -> Optional[Image.Image]:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGB")
        except Exception as e:
            logger.error(f"Failed to load image from {url}: {e}")
            return None

    def _load_images_from_urls(self, urls: List[str]) -> List[Optional[Image.Image]]:
        return [self._load_image_from_url(url) for url in urls]

    @staticmethod
    def _normalize(x: torch.Tensor) -> torch.Tensor:
        return x / (x.norm(dim=-1, keepdim=True) + 1e-8)

    def embed_images(self, images: List[Image.Image]) -> torch.Tensor:
        if not images:
            return torch.tensor([]).to(self.device)

        # Processor handles resizing and normalization
        inputs = self.processor(images=images, return_tensors="pt", padding=True).to(
            self.device
        )
        with torch.no_grad():
            feats = self.model.get_image_features(**inputs)
        return self._normalize(feats)

    def embed_captions(self, captions: List[str]) -> torch.Tensor:
        if not captions:
            return torch.tensor([]).to(self.device)

        inputs = self.processor(
            text=captions, return_tensors="pt", padding=True, truncation=True
        ).to(self.device)
        with torch.no_grad():
            feats = self.model.get_text_features(**inputs)
        return self._normalize(feats)

    def embed(
        self, captions_with_urls: Dict[str, str]
    ) -> Tuple[Optional[torch.Tensor], Optional[torch.Tensor], List[str], List[str]]:
        image_urls = list(captions_with_urls.keys())
        captions = list(captions_with_urls.values())
        images = self._load_images_from_urls(image_urls)

        valid_pairs = [
            (img, cap, url)
            for img, cap, url in zip(images, captions, image_urls)
            if img is not None
        ]
        if not valid_pairs:
            logger.warning("No valid images for embedding")
            return None, None, [], []

        images_filtered, captions_filtered, urls_filtered = zip(*valid_pairs)

        image_embeddings = self.embed_images(list(images_filtered))
        caption_embeddings = self.embed_captions(list(captions_filtered))

        return (
            image_embeddings,
            caption_embeddings,
            list(urls_filtered),
            list(captions_filtered),
        )


embedder = CLIPEmbedder()
