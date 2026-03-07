import os
import pickle
from typing import Any, Dict, List, Tuple, Union

import faiss
import numpy as np
import torch

from autonomous.config.logger import get_logger

logger = get_logger(__name__)


class FAISSDatabase:
    """
    A class to manage FAISS indexes for image and text embeddings,
    allowing similarity search and persistence.
    """

    def __init__(self, dimension: int = 512):
        """
        Initialize FAISS indexes for image and text embeddings.

        Args:
            dimension (int): The dimensionality of the embeddings.
        """
        self.dimension = dimension
        self.image_index = faiss.IndexFlatL2(dimension)
        self.text_index = faiss.IndexFlatL2(dimension)
        self.image_ids: List[str] = []
        self.text_ids: List[str] = []
        self.metadata: Dict[str, Dict[str, str]] = {}

    def _tensor_to_numpy(
        self, tensor: Union[torch.Tensor, None]
    ) -> Union[None, np.ndarray]:
        """
        Convert a PyTorch tensor to a NumPy array.

        Args:
            tensor (torch.Tensor): The input tensor.

        Returns:
            numpy.ndarray: Converted NumPy array.
        """
        if isinstance(tensor, torch.Tensor):
            return tensor.detach().cpu().numpy().astype(np.float32)
        return tensor

    def add_embeddings(
        self,
        image_embeddings: torch.Tensor,
        text_embeddings: torch.Tensor,
        image_ids: List[str],
        text_ids: List[str],
        metadata: Dict[str, Dict[str, str]] = None,
    ) -> str:
        """
        Add image and text embeddings to their respective FAISS indexes with optional metadata.

        Args:
            image_embeddings (torch.Tensor): Image feature embeddings (shape: [N, D]).
            text_embeddings (torch.Tensor): Text feature embeddings (shape: [N, D]).
            image_ids (List[str]): Identifiers for images (e.g., URLs or file paths).
            text_ids (List[str]): Identifiers for text captions.
            metadata (Dict[str, Dict[str, str]], optional): Metadata for each ID.

        Returns:
            str: Success or error message.
        """
        try:
            img_np = self._tensor_to_numpy(image_embeddings)
            txt_np = self._tensor_to_numpy(text_embeddings)

            if img_np.shape[1] != self.dimension or txt_np.shape[1] != self.dimension:
                raise ValueError(
                    "Embedding dimensions do not match FAISS index dimension."
                )

            self.image_index.add(img_np)
            self.text_index.add(txt_np)

            self.image_ids.extend(image_ids)
            self.text_ids.extend(text_ids)

            if metadata:
                self.metadata.update(metadata)  # ✅ Store metadata for each ID

            return f"[SUCCESS] Added {len(image_ids)} image embeddings and {len(text_ids)} text embeddings."
        except Exception as e:
            return f"[ERROR] Failed to add embeddings: {e}"

    def search_images(
        self, query_embedding: torch.Tensor, k: int = 1
    ) -> List[Tuple[str, float]]:
        """
        Search the text FAISS index for the most similar embeddings.

        Args:
            query_embedding (torch.Tensor): Query embedding (shape: [1, D]).
            k (int, optional): Number of top results to return. Defaults to 5.

        Returns:
            List[Tuple[str, float]]: List of (text_id, distance) tuples.
        """
        try:
            query_np = self._tensor_to_numpy(query_embedding)
            if query_np.shape[1] != self.dimension:
                raise ValueError(
                    "Query embedding dimension does not match FAISS index dimension."
                )

            distances, indices = self.image_index.search(query_np, k)

            results = []
            for idx, dist in zip(indices[0], distances[0]):
                if 0 <= idx < len(self.image_ids):  #  validate index
                    results.append((self.image_ids[idx], float(dist)))

            return results
        except Exception as e:
            logger.error(f"Image search failed: {e}")
            return []

    def search_texts(
        self, query_embedding: torch.Tensor, k: int = 1
    ) -> List[Tuple[str, float]]:
        """
        Search the text FAISS index for the most similar embeddings.

        Args:
            query_embedding (torch.Tensor): Query embedding (shape: [1, D]).
            k (int, optional): Number of top results to return. Defaults to 5.

        Returns:
            List[Tuple[str, float]]: List of (text_id, distance) tuples.
        """
        try:
            query_np = self._tensor_to_numpy(query_embedding)
            if query_np.shape[1] != self.dimension:
                raise ValueError(
                    "Query embedding dimension does not match FAISS index dimension."
                )

            distances, indices = self.text_index.search(query_np, k)

            results: List[Tuple[str, float]] = []
            for idx, dist in zip(indices[0], distances[0]):
                if 0 <= idx < len(self.text_ids):
                    results.append((self.text_ids[idx], float(dist)))
            return results
        except Exception as e:
            logger.error(f"Text search failed: {e}")
            return []

    def save(self, folder_path: str) -> None:
        """
        Save FAISS indexes and metadata to a specified folder.

        Args:
            folder_path (str): Directory path to save the database.
        """
        try:
            os.makedirs(folder_path, exist_ok=True)  # Create folder if it doesn't exist

            image_index_path = os.path.join(folder_path, "cloud_image_index.faiss")
            text_index_path = os.path.join(folder_path, "cloud_caption_index.faiss")
            metadata_path = os.path.join(folder_path, "cloud_image_data.pkl")

            faiss.write_index(self.image_index, image_index_path)
            faiss.write_index(self.text_index, text_index_path)

            with open(metadata_path, "wb") as f:
                pickle.dump(
                    {
                        "image_ids": self.image_ids,
                        "text_ids": self.text_ids,
                        "metadata": self.metadata,
                    },
                    f,
                )

            logger.info(f"Database saved at: {folder_path}")
        except Exception as e:
            logger.error(f"Failed to save FAISS database: {e}")

    def load(self, folder_path: str) -> None:
        """
        Load FAISS indexes and metadata from a specified folder.

        Args:
            folder_path (str): Directory path to load the database from.
        """
        try:
            image_index_path = os.path.join(folder_path, "cloud_image_index.faiss")
            text_index_path = os.path.join(folder_path, "cloud_caption_index.faiss")
            metadata_path = os.path.join(folder_path, "cloud_image_data.pkl")

            self.image_index = faiss.read_index(image_index_path)
            self.text_index = faiss.read_index(text_index_path)

            with open(metadata_path, "rb") as f:
                meta: Dict[str, Any] = pickle.load(f)
                self.image_ids = meta.get("image_ids", [])
                self.text_ids = meta.get("text_ids", [])
                self.metadata = meta.get("metadata", {})

            logger.info(f"Database loaded from: {folder_path}")
        except Exception as e:
            logger.error(f"Failed to load FAISS database: {e}")
