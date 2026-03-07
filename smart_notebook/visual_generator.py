import asyncio
import io
import base64
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image

from autonomous.config.settings import settings
from autonomous.config.logger import get_logger

logger = get_logger("curio.smart_notebook.visual")


class VisualGenerator:
    def __init__(self):
        # Initialize Gemini client
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

        # Current stable multimodal model
        self.model = "gemini-3-pro-image-preview"

    def _build_educational_prompt(self, content: str) -> str:
        """
        Builds a structured prompt for generating clean educational visual notes.
        """
        return f"""
Create a clean, well-structured **educational visual note** as a student would make during class.

TOPIC:
{content}

STYLE RULES:
- Short phrases only (no long paragraphs)
- Use bullet points
- Use arrows (→, ⇒) to show relationships
- Organize ideas like a mind map
- Use boxed sections for important points
- Include formulas where relevant
- Add simple examples
- Add quick definitions when needed
- Keep layout clean, readable, and uncluttered

LAYOUT EXPECTATIONS:
- Clear hierarchy
- Visual grouping of related ideas
- Concept → explanation → example flow
- Designed for fast revision before exams

VISUAL GOAL:
A neat, notebook-style educational diagram that looks like high-quality student notes.
"""

    def _generate_sync(self, content: str) -> Optional[Image.Image]:
        try:
            logger.info(f"Generating educational visual notes for: {content}")

            prompt_text = self._build_educational_prompt(content)

            response = self.client.models.generate_content(
                model=self.model,
                contents=[prompt_text],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )

            for part in response.parts:
                if part.inline_data is not None:
                    return part.as_image()

            logger.warning("No image returned from Gemini.")
            return None

        except Exception as e:
            logger.error(f"Error in _generate_sync: {e}")
            return None

    async def generate(self, content: str) -> Optional[str]:
        """
        Generates an educational visual note image and returns it as a base64 string.
        """
        image = await asyncio.to_thread(self._generate_sync, content)

        if image:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")

        return None


visual_generator = VisualGenerator()
