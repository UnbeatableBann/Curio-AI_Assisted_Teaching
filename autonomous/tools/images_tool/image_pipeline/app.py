import asyncio
from itertools import islice
from typing import Any, Dict, List

from autonomous.tools.images_tool.image_pipeline.blip_captioner import captioner
from autonomous.tools.images_tool.image_pipeline.clip_embedder import embedder
from autonomous.tools.images_tool.image_pipeline.faiss_db import FAISSDatabase
from autonomous.tools.images_tool.image_pipeline.search import semantic_search


async def ingest_imageurl(image_urls: List[Dict[str, Any]]) -> None:
    """
    Ingests a list of image URLs into the FAISS database.

    Steps:
        1. Extract image URLs from provided list.
        2. Generate captions using BLIP captioner.
        3. Create embeddings using CLIP.
        4. Store embeddings and metadata (URL + caption) in FAISS.
        5. Perform a sample semantic search to verify indexing.

    Args:
        image_urls (List[Dict[str, Any]]): A list of dictionaries containing image metadata,
                                           each with a "url" key (and optionally other fields).
    """
    # Extract URLs from the fetched images
    image_urls = [img["url"] for img in image_urls]

    captions_with_urls = captioner.generate_captions_from_url_batch(image_urls)
    print(
        f"Generated {len(captions_with_urls)} captions. "
        f"\nSample: {dict(islice(captions_with_urls.items(), 2))}"
    )

    image_embeddings, caption_embeddings, valid_urls, valid_captions = embedder.embed(
        captions_with_urls
    )

    if image_embeddings is None:
        print("[ERROR] No embeddings generated. Exiting.")
        return

    # Store embeddings in the FAISS database
    db = FAISSDatabase(dimension=image_embeddings.shape[1])
    metadata = {url: {"caption": cap} for url, cap in zip(valid_urls, valid_captions)}

    db.add_embeddings(
        image_embeddings, caption_embeddings, valid_urls, valid_captions, metadata
    )

    db.save("faiss_database")

    # Perform a semantic search as an example
    query = "a poster with a bright light shining over a black background"
    results = semantic_search(
        query=query,
        faiss_db=db,
        clip_embedder=embedder,
        top_k=1,
        query_type="text",
        search_type="text",
    )

    print("Search Results:", results)


def fetch_images_from_appwrite():
    pass


def ingest_appwrite_images() -> None:
    """
    Ingests images fetched from Appwrite into the FAISS database.

    Steps:
        1. Fetch images from Appwrite.
        2. Generate captions using BLIP captioner.
        3. Create embeddings using CLIP.
        4. Store embeddings and metadata (URL + caption) in FAISS.
        5. Perform a sample semantic search to verify indexing.
    """
    # Fetch images from Appwrite
    images = fetch_images_from_appwrite()
    print(f"Fetched {len(images)} images")

    # Extract URLs from the fetched images
    image_urls = [img["url"] for img in images]

    captions_with_urls = captioner.generate_captions_from_url_batch(image_urls)
    print(
        f"Generated {len(captions_with_urls)} captions. "
        f"\nSample: {dict(islice(captions_with_urls.items(), 2))}"
    )

    image_embeddings, caption_embeddings, valid_urls, valid_captions = embedder.embed(
        captions_with_urls
    )

    if image_embeddings is None:
        print("[ERROR] No embeddings generated. Exiting.")
        return

    # Store embeddings in the FAISS database
    db = FAISSDatabase(dimension=image_embeddings.shape[1])
    metadata = {url: {"caption": cap} for url, cap in zip(valid_urls, valid_captions)}

    result = db.add_embeddings(
        image_embeddings, caption_embeddings, valid_urls, valid_captions, metadata
    )
    print(result)

    db.save("faiss_database")

    # Perform a semantic search as an example
    query = "a diagram showing the different types of fish and algae"
    results = semantic_search(
        query=query,
        faiss_db=db,
        clip_embedder=embedder,
        top_k=1,
        query_type="text",
        search_type="image",
    )

    print("Search Results:", results)


if __name__ == "__main__":
    image_urls = [
        {
            "url": "https://images.examples.com/wp-content/uploads/2024/05/Average-Velocity-Formula.png",
            "score": 0.33472034335136414,
        },
        {
            "url": "https://live.staticflickr.com/3189/2603198009_3d6335db26.jpg",
            "score": 0.3331291675567627,
        },
        {
            "url": "https://live.staticflickr.com/8293/7844360618_b4e9e270fb_b.jpg",
            "score": 0.3135599195957184,
        },
    ]
    asyncio.run(ingest_imageurl(image_urls))
