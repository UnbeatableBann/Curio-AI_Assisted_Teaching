import asyncio
import pickle
import random
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Union

import aiohttp
import faiss
import requests
import torch
from ddgs import DDGS
from PIL import Image
from sentence_transformers import SentenceTransformer
from serpapi import GoogleSearch

from autonomous.config.logger import get_logger
from autonomous.config.settings import settings
from autonomous.tools.images_tool.image_pipeline.clip_embedder import CLIPEmbedder
from autonomous.tools.images_tool.image_pipeline.faiss_db import FAISSDatabase

logger = get_logger(__name__)

# Load Models
sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
device = "cuda" if torch.cuda.is_available() else "cpu"

faiss_db: FAISSDatabase = FAISSDatabase()
clip_embedder: CLIPEmbedder = CLIPEmbedder()

try:
    db_path = Path(__file__).resolve().parent.parent / "faiss_database"
    if db_path.exists():
        logger.info(f"Loading FAISS database from {db_path}")
        faiss_db.load(str(db_path))
    else:
        logger.warning(f"FAISS database not found at {db_path}")
except Exception as e:
    logger.error(f"Failed to load FAISS database: {e}")


async def fetch_json(
    session: aiohttp.ClientSession, url: str, headers=None, params=None
):
    async with session.get(url, headers=headers, params=params) as resp:
        if resp.status != 200:
            raise Exception(f"HTTP Error {resp.status} for {url}")
        return await resp.json()


async def search_google(
    session: aiohttp.ClientSession, query: str, num: int = 5
) -> List[Dict]:
    logger.info(f"Searching Google for: {query}")
    if not query.strip():
        logger.warning("Empty query for Google search")
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    results = []

    try:
        start = random.randint(1, 90)
        params = {
            "q": query,
            "cx": settings.GOOGLE_CX,
            "searchType": "image",
            "key": settings.GOOGLE_SEARCH_API_KEY,
            "num": num,
            "start": start,
            "safe": "off",
        }

        data = await fetch_json(session, url, params=params)
        items = data.get("items", [])
        if not items:
            logger.info("No Google results found")
            return []

        for item in items:
            results.append(
                {
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "thumbnail": item.get("image", {}).get("thumbnailLink"),
                    "source": "google",
                    "license": "unknown",
                }
            )
        logger.debug(f"Google returned {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Google search failed: {e}")
        return []


async def search_duckduckgo(
    session: aiohttp.ClientSession, query: str, num: int = 5
) -> List[Dict]:
    """
    Search DuckDuckGo for images (no API key required).
    """
    logger.info(f"Searching DuckDuckGo for: {query}")
    if not query.strip():
        return []

    try:

        def _ddg_search():
            with DDGS() as ddgs:
                # keywords parameter might be positional 'query' in this version
                results = list(
                    ddgs.images(
                        query,
                        region="wt-wt",
                        safesearch="off",
                        size=None,
                        type_image=None,
                        layout=None,
                        license_image=None,
                        max_results=num,
                    )
                )
                return results

        ddg_results = await asyncio.to_thread(_ddg_search)

        results = []
        for item in ddg_results:
            results.append(
                {
                    "title": item.get("title"),
                    "url": item.get("image"),
                    "thumbnail": item.get("thumbnail"),
                    "source": "duckduckgo",
                    "license": "unknown",
                }
            )
        logger.info(f"DuckDuckGo returned {len(results)} images")
        return results

    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return []


async def search_unsplash(
    session: aiohttp.ClientSession, query: str, num: int = 5
) -> List[Dict]:
    if not query.strip():
        logger.warning("Empty query for Unsplash search")
        return []

    url = "https://api.unsplash.com/search/photos"
    headers = {"Authorization": f"Client-ID {settings.UNSPLASH_ACCESS_KEY}"}
    params = {"query": query, "per_page": num}

    try:
        data = await fetch_json(session, url, headers=headers, params=params)
        results = [
            {
                "title": item.get("description") or item.get("alt_description"),
                "url": item["urls"]["full"],
                "thumbnail": item["urls"]["thumb"],
                "source": "unsplash",
                "license": "unsplash",
            }
            for item in data.get("results", [])
        ]
        return results
    except Exception as e:
        logger.error(f"Unsplash search failed: {e}")
        return []


async def search_openverse(
    session: aiohttp.ClientSession, query: str, num: int = 5
) -> List[Dict]:
    if not query.strip():
        logger.warning("Empty query for Openverse search")
        return []

    url = "https://api.openverse.engineering/v1/images"
    params = {"q": query, "page_size": num}

    try:
        data = await fetch_json(session, url, params=params)
        results = [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "thumbnail": item.get("thumbnail"),
                "source": "openverse",
                "license": item.get("license"),
            }
            for item in data.get("results", [])
        ]
        return results

    except Exception as e:
        logger.error(f"Openverse search failed: {e}")
        return []


async def search_serpapi(
    session: aiohttp.ClientSession, query: str, num_images: int = 5
) -> list:
    """
    Asynchronously fetch image search results from SerpAPI (Google Images).

    Args:
        session (aiohttp.ClientSession): Unused, kept for consistency.
        query (str): Search query
        num_images (int): Number of images to fetch

    Returns:
        list: List of image result dictionaries
    """

    params = {
        "engine": "google_images",
        "q": query,
        "api_key": settings.SERPAPI_KEY,
        "num": num_images,
    }

    # SerpAPI client is blocking, so we offload it
    loop = asyncio.get_running_loop()

    try:
        results = await loop.run_in_executor(
            None, lambda: GoogleSearch(params).get_dict()
        )

        image_results = results.get("images_results", [])

        # Normalize to our format
        normalized_results = []
        for item in image_results:
            normalized_results.append(
                {
                    "title": item.get("title"),
                    "url": item.get("original"),
                    "thumbnail": item.get("thumbnail"),
                    "source": "serpapi",
                    "license": "unknown",
                }
            )

        logger.info(f"SerpAPI returned {len(normalized_results)} images")
        return normalized_results

    except Exception as e:
        logger.error(f"SerpAPI search failed: {e}")
        return []


async def search_faiss_by_text(query: str) -> Union[Dict[str, Any], None]:
    if not query.strip():
        return None

    try:

        def _search():
            # Construct absolute paths relative to this file
            base_dir = Path(__file__).parent / "image_pipeline" / "faiss_database"
            index_path = str(base_dir / "url_faiss_index.bin")
            data_path = str(base_dir / "url_faiss_data.pkl")

            index = faiss.read_index(index_path)
            with open(data_path, "rb") as f:
                df = pickle.load(f)

            query_vector = sentence_model.encode([query]).astype("float32")
            distances, best_match_index = index.search(query_vector, 5)
            results = []
            for idx, dist in zip(best_match_index[0], distances[0]):
                results.append(
                    {"url": df.iloc[idx]["photo_image_url"], "score": float(dist)}
                )
            return results

        return await asyncio.to_thread(_search)
    except Exception as e:
        logger.error(f"Error in FAISS text search: {e}")
        return None


async def multi_modal_faiss_search(
    query: Union[str, Any], top_k: int = 5
) -> List[Dict[str, Any]]:
    if not query:
        return []

    try:
        query_embedding = await asyncio.to_thread(clip_embedder.embed_captions, [query])
        results = await asyncio.to_thread(
            faiss_db.search_images, query_embedding, top_k
        )

        detailed_results = []
        for item_id, distance in results:
            meta = faiss_db.metadata.get(item_id, {})
            detailed_results.append(
                {
                    "id": item_id,
                    "distance": float(distance),
                    **meta,
                }
            )
        return detailed_results
    except Exception as e:
        logger.error(f"Error in multi-modal FAISS search: {e}")
        return []


async def evaluate_images_with_clip(
    query: str, image_urls: list, check: str, threshold: float = 0.20
):
    """
    Evaluate a list of images against a text query using CLIP similarity.
    Filters images below a similarity threshold (default 0.20).
    """
    logger.info(f"Running CLIP evaluation for query: '{query}', {check}")
    logger.debug(f"Number of candidate images: {len(image_urls)}")

    text_features = await asyncio.to_thread(clip_embedder.embed_captions, [query])

    scores = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    for url in image_urls:
        logger.debug(f"Processing image: {url}")
        try:
            # Download image (blocking, could be improved with aiohttp but keeping structure)
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code != 200:
                logger.warning(f"Download failed status {response.status_code}")
                continue

            img = Image.open(BytesIO(response.content)).convert("RGB")

            # Embed image
            image_features = await asyncio.to_thread(clip_embedder.embed_images, [img])

            # Calculate cosine similarity
            similarity = torch.mm(text_features, image_features.T).item()

            logger.debug(f"Similarity score: {similarity:.4f}")
            scores.append((url, similarity))
        except Exception as e:
            logger.warning(f"Error processing image: {e}")
            continue

    # Sort and filter by threshold
    scores.sort(key=lambda x: x[1], reverse=True)
    passed = [
        {"url": url, "score": score} for url, score in scores if score >= threshold
    ]

    logger.info(
        f"CLIP evaluation finished. {len(passed)}/{len(scores)} images passed threshold {threshold}"
    )
    for p in passed[:3]:
        logger.debug(f"{p['url']} | score={p['score']:.4f}")

    return passed
