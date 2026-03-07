from typing import Any, Dict, List, Union

import torch

from autonomous.tools.images_tool.image_pipeline.clip_embedder import CLIPEmbedder
from autonomous.tools.images_tool.image_pipeline.faiss_db import FAISSDatabase


def semantic_search(
    query: Union[str, torch.Tensor],
    faiss_db: FAISSDatabase,
    clip_embedder: CLIPEmbedder,
    top_k: int = 1,
    query_type: str = "text",
    search_type: str = "image",
) -> List[Dict[str, Any]]:
    """
    Performs a semantic search in the FAISS database based on text or image query and returns full metadata.

    Args:
        query (str or torch.Tensor): The search query (text string for query_type="text").
        faiss_db (FAISSDatabase): The FAISS database instance.
        clip_embedder (CLIPEmbedder): The CLIP embedder instance.
        top_k (int): The number of top results to return.
        query_type (str): Type of query: "text" or "image".
        search_type (str): Which index to search: "image" or "text".

    Returns:
        List[Dict[str, Any]]: A list of metadata dictionaries with distance.
    """
    # Generate query embedding based on query type
    if query_type == "text":
        query_embedding = clip_embedder.embed_captions([query])  # [1, D]
    elif query_type == "image":
        # Expect a PIL Image here; if a tensor is provided, raise for clarity.
        if isinstance(query, torch.Tensor):
            raise ValueError("For image queries, pass a PIL.Image (or adapt embedder).")
        query_embedding = clip_embedder.embed_images([query])  # [1, D]
    else:
        raise ValueError("Invalid query_type. Use 'text' or 'image'.")

    # Search in the selected FAISS index
    if search_type == "image":
        results = faiss_db.search_images(query_embedding, k=top_k)
    elif search_type == "text":
        results = faiss_db.search_texts(query_embedding, k=top_k)
    else:
        raise ValueError("Invalid search_type. Use 'image' or 'text'.")

    # Attach metadata for each result
    detailed_results = []
    for item_id, distance in results:
        meta = faiss_db.metadata.get(item_id, {})
        detailed_results.append(
            {
                "id": item_id,
                "distance": distance,
                **meta,
            }
        )

    return detailed_results
