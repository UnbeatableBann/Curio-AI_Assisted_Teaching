import os
import requests
from typing import Optional


# --- CONFIGURATION ---
# Removed SentenceTransformer dependencies
# SentenceTransformer was used for local image FAISS search
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
GENERATED_IMAGE_DIR = "generated_images"


def get_visual_for_slide(visual_hint: str) -> Optional[str]:
    # 1. Try Unsplash search first (best quality if key exists)
    image = search_unsplash_image(visual_hint)
    if image:
        print("Found on Unsplash:", image)
        return image

    # 2. Fallback: Generate a placeholder
    # In a real app we might use DALL-E or similar API
    return None


def search_unsplash_image(visual_hint: str) -> Optional[str]:
    """Search Unsplash for an image matching the visual_hint."""
    if not UNSPLASH_ACCESS_KEY:
        print("Unsplash API key not set.")
        return None
    url = "https://api.unsplash.com/photos/random"
    params = {
        "query": visual_hint,
        "client_id": UNSPLASH_ACCESS_KEY,
        "orientation": "landscape",
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        image_url = data.get("urls", {}).get("regular")
        if image_url:
            # Download and save the image locally
            img_data = requests.get(image_url).content
            os.makedirs("unsplash_images", exist_ok=True)
            # Sanitize filename
            safe_name = (
                "".join(
                    [c for c in visual_hint if c.isalpha() or c.isdigit() or c == " "]
                )
                .strip()
                .replace(" ", "_")[:50]
            )
            img_path = os.path.join("unsplash_images", f"{safe_name}.jpg")
            with open(img_path, "wb") as f:
                f.write(img_data)
            return img_path
    except Exception as e:
        print(f"Unsplash search failed: {e}")
    return None


if __name__ == "__main__":
    # Example usage
    hint = "Nature landscape"
    print(get_visual_for_slide(hint))
