import requests, os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
from io import BytesIO
from PIL import Image
import base64, pickle, numpy as np, faiss, clip, torch
import concurrent.futures
from sentence_transformers import SentenceTransformer


class VisualGenerator:
    def __init__(self):
        load_dotenv()
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.CX = os.getenv("GOOGLE_CX")
        self.GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")

        # Load AI Model (Fast & Lightweight)
        self.sentence_model = SentenceTransformer("all-MiniLM-L6-v2")

        # Load CLIP model
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, self.preprocess = clip.load("ViT-B/32", device=self.device)

    def upload_to_imgbb(self, image_base64):
        """Uploads base64 image to Imgbb and returns a public URL."""
        try:
            response = requests.post(
                "https://api.imgbb.com/1/upload",
                data={"key": "65af10f30a525eb2b66ef0c49062f1aa", "image": image_base64},
            )
            response_json = response.json()

            if "data" in response_json and "url" in response_json["data"]:
                return response_json["data"]["url"]
            else:
                print("❌ Failed to upload image to Imgbb:", response_json)
                return None
        except Exception as e:
            print(f"❌ Error uploading image: {e}")
            return None

    def internet_sourced_image(self, query: str):
        try:
            url = f"https://www.googleapis.com/customsearch/v1?q={query}&cx={self.CX}&searchType=image&key={self.GOOGLE_SEARCH_API_KEY}"
            response = requests.get(url)
            response.raise_for_status()
            response_json = response.json()
            image_url = response_json["items"][0]["link"]
            return image_url
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch image: {e}")
            return None
        except KeyError:
            print("No images found for the query.")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def generate_image_with_gemini(self, prompt: str):
        try:
            client = genai.Client(api_key=self.GEMINI_API_KEY)
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp-image-generation",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['Text', 'Image']
                )
            )

            for part in response.candidates[0].content.parts:
                if part.text is not None:
                    print(part.text)
                elif part.inline_data is not None:
                    image_data = part.inline_data.data
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
                    gemini_url = self.upload_to_imgbb(image_base64)
                    return gemini_url
        except Exception as e:
            print(f"Error generating image: {e}")
            return None

    def generate_image_with_duckduckgo(self, query: str):
        try:
            with DDGS() as ddgs:
                search_results = list(ddgs.images(query, max_results=1))

            if search_results:
                image_url = search_results[0]['image']
                return image_url
            else:
                print("No image found.")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Error downloading image: {e}")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def pre_generated_images_match(self, query):
        try:
            index = faiss.read_index("faiss_index.bin")

            # 🔹 Load dataset
            with open("image_data.pkl", "rb") as f:
                df = pickle.load(f)

            query_vector = self.sentence_model.encode([query])  # Convert query to vector
            _, best_match_index = index.search(query_vector, 1)  # Search FAISS index

            best_match_index = best_match_index[0][0]  # Get first result index
            best_match_url = df.iloc[best_match_index]["photo_image_url"]
            return best_match_url
        except Exception as e:
            print(f"Error in pre_generated_images_match: {e}")
            return None

    def download_image(self, image_url):
        """Downloads an image from a URL and returns a PIL image."""
        try:
            response = requests.get(image_url, timeout=5)
            response.raise_for_status()  # Raise an error for bad responses (404, etc.)
            return Image.open(BytesIO(response.content)).convert("RGB")
        except Exception as e:
            print(f"❌ Error downloading image {image_url}: {e}")
            return None

    def compute_image_relevance(self, query, image_url):
        """Computes relevance score using CLIP by comparing text and image embeddings."""
        try:
            # Download and preprocess the image
            image = self.download_image(image_url)
            if image is None:
                return -1, None  # Skip this image if download fails

            image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)

            # Convert query text to CLIP embedding
            text_tokenized = clip.tokenize([query]).to(self.device)
            text_embedding = self.model.encode_text(text_tokenized).detach().cpu().numpy()

            # Get CLIP embedding for the image
            image_embedding = self.model.encode_image(image_tensor).detach().cpu().numpy()

            # Compute cosine similarity
            similarity_score = np.dot(text_embedding, image_embedding.T).flatten()[0]
            return similarity_score, image

        except Exception as e:
            print(f"Error processing image: {e}")
            return -1, None  # Return low score if error

    def choose_best_image(self, query, image_sources_url):
        """Chooses the most relevant image from multiple sources."""
        ranked_images = []

        for source, img_url in image_sources_url.items():
            if img_url:
                score, image = self.compute_image_relevance(query, img_url)
                if image:
                    ranked_images.append((score, source, image))

        # Sort images by relevance (highest first)
        ranked_images.sort(reverse=True, key=lambda x: x[0])

        if ranked_images:
            print(f"✅ Best Image Source: {ranked_images[0][1]}")
            best_image = ranked_images[0][2]
            remaining_images = [img[2] for img in ranked_images[1:]]  # Exclude the best image
            return best_image, remaining_images
        else:
            print("❌ No suitable image found.")
            return None, []

    def run_all_image_generators(self, query):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            pregenereate_image = executor.submit(self.pre_generated_images_match, query)
            duckduckgo_image = executor.submit(self.generate_image_with_duckduckgo, query)
            gemini_image = executor.submit(self.generate_image_with_gemini, query)
            interned_image = executor.submit(self.internet_sourced_image, query)

            results = {
                "Pre-generated": pregenereate_image.result(),
                "Duckduckgo": duckduckgo_image.result(),
                "Gemini": gemini_image.result(),
                "Google-Search": interned_image.result(),
            }

        # Remove failed results
        results = {k: v for k, v in results.items() if v}

        # Select the most relevant image
        best_image, remaining_images = self.choose_best_image(query, results)
        return best_image, remaining_images
