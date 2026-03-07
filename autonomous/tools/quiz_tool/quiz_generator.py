import asyncio

from google import genai

from autonomous.config.settings import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)


async def quiz_generator_tool(query: str, context: str) -> str:
    """
    Stateless async quiz generator.
    Runs blocking Gemini call in a thread so FastAPI event loop is not blocked.
    """

    if not context or not context.strip():
        return "None"

    prompt = f"""
    You are an expert teacher.

    Create a high-quality multiple choice quiz.

    Rules:
    - Few but strong questions (5–8 max)
    - Conceptual, not rote
    - Mix difficulty
    - Avoid trivial questions

    Query:
    {query}

    Content:
    {context}

    Format:
    Question: ...
    A) ...
    B) ...
    C) ...
    D) ...
    (Correct Answer: X)

    - If the context is not related to the query, then create quiz based on the query
    """

    def _generate():
        resp = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config={"temperature": 0.5},
        )
        return resp.text or "None"

    return await asyncio.to_thread(_generate)
