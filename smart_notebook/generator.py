import asyncio
from google import genai

from autonomous.config.settings import settings
from autonomous.config.logger import get_logger

logger = get_logger("curio.smart_notebook.generator")


class SmartNotebookGenerator:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = "gemini-3-flash-preview"  # Or use a config value

    async def generate_note(self, context_data: dict) -> str:
        """
        Generates student-style smart notes based on the provided brain context.
        """
        prompt = f"""
        You are an expert student note-taker. Your goal is to transform the following "Brain State" data into clean, structured, student-style notes.
        
        **Input Data:**
        {context_data}
        
        **Requirements:**
        1. **Format**: Use Markdown.
        2. **Style**: Not messy. Use:
           - Bullets
           - Arrows (-> or =>) to show flow/logic
           - Short phrases (avoid long paragraphs)
           - **Bold** for keywords
           - Boxed key concepts (use blockquotes > or code blocks ```)
           - Formulas where applicable (LaTeX style $...$ or simple text representation)
           - Examples
           - Quick definitions
           - Mind maps (use indented lists to represent hierarchy)
        3. **Content**: Focus on the 'current_transcript_summary', 'current_subtopic', and 'current_topic'. Use 'past_*' context to link ideas if relevant, but focus on the new information.
        4. **Visuals**: If a concept is abstract, suggest a simple text-based diagram or ASCII art if helpful, but keep it clean.
        
        **Output:**
        A single coherent note entry for this topics. Do not include introductory text like "Here are your notes:". Just give the notes.
        """

        try:
            # We use asyncio.to_thread because the genai library might be synchronous blocking
            # If the library supports async natively, we should use that.
            # The user's snippet was synchronous: client.models.generate_content

            response = await asyncio.to_thread(
                self.client.models.generate_content, model=self.model, contents=[prompt]
            )

            # Extract text
            if response.text:
                return response.text

            # Fallback if text is scattered in parts (though usually .text aggregates it)
            full_text = []
            if response.parts:
                for part in response.parts:
                    if part.text:
                        full_text.append(part.text)

            return "".join(full_text)

        except Exception as e:
            logger.error(f"Error generating smart note: {e}")
            return "Error generating notes."


notebook_generator = SmartNotebookGenerator()
