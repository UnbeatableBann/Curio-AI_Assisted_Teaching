import asyncio
import base64
from typing import Any, Dict, List, TypedDict

import aiohttp
import requests
from langgraph.graph import END, StateGraph

from autonomous.config.logger import get_logger
from autonomous.tools.images_tool.image_pipeline.app import ingest_imageurl
from autonomous.tools.images_tool.image_sources import (
    evaluate_images_with_clip,
    multi_modal_faiss_search,
    search_duckduckgo,
    search_faiss_by_text,
    search_google,
    search_openverse,
    search_serpapi,
    search_unsplash,
)

logger = get_logger(__name__)


class ImageSearchState(TypedDict):
    query: str
    session: aiohttp.ClientSession
    faiss_result: List[Dict[str, Any]]
    multi_faiss_result: List[Dict[str, Any]]
    validated_faiss_images: List[Dict[str, Any]]
    google_results: List[Dict[str, Any]]
    unsplash_results: List[Dict[str, Any]]
    openverse_results: List[Dict[str, Any]]
    ddg_results: List[Dict[str, Any]]
    serpapi_results: List[Dict[str, Any]]
    validated_external_images: List[Dict[str, Any]]
    final_images: List[Dict[str, Any]]
    _stop: bool


# -------------------------------
# Nodes
# -------------------------------
async def faiss_node(state: ImageSearchState) -> ImageSearchState:
    results = await search_faiss_by_text(state["query"]) or []
    logger.info(f"Retrieved {len(results)} results from FAISS (text search)")
    return {"faiss_result": results}


async def multi_faiss_node(state: ImageSearchState) -> ImageSearchState:
    results = await multi_modal_faiss_search(state["query"]) or []
    logger.info(f"Retrieved {len(results)} results from Multi-modal FAISS search")
    return {"multi_faiss_result": results}


async def clip_eval_faiss_node(state: ImageSearchState) -> ImageSearchState:
    urls = [
        item["url"]
        for item in state["faiss_result"] + state["multi_faiss_result"]
        if "url" in item
    ]

    validated = await evaluate_images_with_clip(state["query"], urls, "faiss")
    state["validated_faiss_images"] = validated

    if len(validated) >= 2:
        state["final_images"] = validated[:3]
        state["_stop"] = True
    else:
        state["_stop"] = False
    return state


async def external_sources_node(state: ImageSearchState) -> ImageSearchState:
    """
    Fetch google, unsplash, openverse in parallel and return them together.
    This avoids partial updates / concurrent writes to the same keys.
    """
    google_task = search_google(state["session"], state["query"], num=2)
    unsplash_task = search_unsplash(state["session"], state["query"], num=1)
    openverse_task = search_openverse(state["session"], state["query"], num=1)
    ddg_task = search_duckduckgo(state["session"], state["query"], num=2)
    serpapi_task = search_serpapi(state["session"], state["query"], num_images=2)

    (
        google_results,
        unsplash_results,
        openverse_results,
        ddg_results,
        serpapi_results,
    ) = await asyncio.gather(
        google_task, unsplash_task, openverse_task, ddg_task, serpapi_task
    )

    # Basic type-checks to catch upstream issues early
    if not isinstance(google_results, list):
        google_results = []
    if not isinstance(unsplash_results, list):
        unsplash_results = []
    if not isinstance(openverse_results, list):
        openverse_results = []
    if not isinstance(ddg_results, list):
        ddg_results = []
    if not isinstance(serpapi_results, list):
        serpapi_results = []

    return {
        "google_results": google_results,
        "unsplash_results": unsplash_results,
        "openverse_results": openverse_results,
        "ddg_results": ddg_results,
        "serpapi_results": serpapi_results,
    }


async def clip_eval_external_node(state: ImageSearchState) -> ImageSearchState:
    urls = []
    for source in [
        "google_results",
        "unsplash_results",
        "openverse_results",
        "ddg_results",
        "serpapi_results",
    ]:
        urls += [item["url"] for item in state.get(source, []) if "url" in item]
    validated = await evaluate_images_with_clip(
        state["query"], urls, "external", threshold=0.18
    )  # Lowered threshold
    state["validated_external_images"] = validated
    return state


async def faiss_update_node(state: ImageSearchState) -> ImageSearchState:
    """
    Update FAISS DB with relevant external images using the async image pipeline.
    Only images not already in FAISS and with high similarity are ingested.
    """
    logger.info("faiss_update_node started")

    # Get URLs of images already in FAISS
    faiss_urls = {img["url"] for img in state.get("validated_faiss_images", [])}
    logger.debug(f"FAISS currently has {len(faiss_urls)} images")

    # Select external images in final_images not in FAISS
    new_images = [
        img for img in state.get("final_images", []) if img["url"] not in faiss_urls
    ]
    logger.debug(f"{len(new_images)} new images to ingest")

    if new_images:
        await ingest_imageurl(new_images)
        state["faiss_updated"] = True
        logger.info("FAISS updated")
    else:
        state["faiss_updated"] = False
        logger.debug("No new images, FAISS not updated")

    return state


async def aggregator_node(state: ImageSearchState) -> ImageSearchState:
    # Collect validated images
    faiss_images = state.get("validated_faiss_images", [])
    external_images = state.get("validated_external_images", [])

    # Sort by score descending if available
    faiss_images = sorted(faiss_images, key=lambda x: x.get("score", 0), reverse=True)
    external_images = sorted(
        external_images, key=lambda x: x.get("score", 0), reverse=True
    )

    # Combine images, prioritizing FAISS first
    combined_images = faiss_images + external_images

    # Remove duplicates by URL
    seen = set()
    unique_images = []
    for img in combined_images:
        url = img.get("url")
        if url and url not in seen:
            unique_images.append(img)
            seen.add(url)
        if len(unique_images) == 3:  # Limit to top 3
            break

    # Save final images
    state["final_images"] = unique_images
    logger.info(f"Final Top Images: {len(state['final_images'])} images selected")
    return state


# -------------------------------
# LangGraph Workflow
# -------------------------------
workflow = StateGraph(ImageSearchState)

workflow.add_node("faiss", faiss_node)
workflow.add_node("multi_faiss", multi_faiss_node)
workflow.add_node("clip_eval_faiss", clip_eval_faiss_node)
workflow.add_node("external_sources", external_sources_node)
workflow.add_node("clip_eval_external", clip_eval_external_node)
workflow.add_node("aggregator", aggregator_node)
workflow.add_node("faiss_update", faiss_update_node)

workflow.set_entry_point("faiss")
workflow.add_edge("faiss", "multi_faiss")
workflow.add_edge("multi_faiss", "clip_eval_faiss")

workflow.add_conditional_edges(
    "clip_eval_faiss",
    lambda s: "enough" if s.get("_stop") else "continue",
    {"enough": END, "continue": "external_sources"},
)

workflow.add_edge("external_sources", "clip_eval_external")
workflow.add_edge("clip_eval_external", "aggregator")
workflow.add_edge("aggregator", END)
# workflow.add_edge("aggregator", "faiss_update")
# workflow.add_edge("faiss_update", END)

graph = workflow.compile()


# -------------------------------
# Mermaid Export
# -------------------------------
def show_mermaid_graph(graph):
    try:
        mermaid_code = graph.get_graph().draw_mermaid()
        logger.info("Mermaid Diagram generated")
        logger.debug(mermaid_code)
        mermaid_to_png(mermaid_code)
    except Exception as e:
        logger.error(f"Failed to generate Mermaid diagram: {e}")


def mermaid_to_png(mermaid_code, output_path="mermaid_diagram.png"):
    graph_bytes = mermaid_code.encode("utf8")
    base64_bytes = base64.urlsafe_b64encode(graph_bytes)
    base64_string = base64_bytes.decode("ascii")
    url = f"https://mermaid.ink/img/{base64_string}"
    img_data = requests.get(url).content
    with open(output_path, "wb") as f:
        f.write(img_data)


# -------------------------------
# Runner
# -------------------------------
async def image_generator_tool(query: str):
    async with aiohttp.ClientSession() as session:
        initial_state: ImageSearchState = {
            "query": query,
            "session": session,
            "faiss_result": [],
            "multi_faiss_result": [],
            "validated_faiss_images": [],
            "google_results": [],
            "unsplash_results": [],
            "openverse_results": [],
            "ddg_results": [],
            "serpapi_results": [],
            "validated_external_images": [],
            "final_images": [],
            "_stop": False,
        }

        final_state = await graph.ainvoke(initial_state)
        return final_state["final_images"] or "None"
