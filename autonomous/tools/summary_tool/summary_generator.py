import asyncio

from google import genai

from autonomous.config.settings import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)


async def summary_generator_tool(query: str, context: str) -> str:
    """
    Stateless async summary generator.
    Runs blocking Gemini call in a thread so FastAPI event loop is not blocked.
    """

    if not context or not context.strip():
        return "None"

    prompt = f"""
    You are an expert educational assistant.

    Create a high-quality summary based on the provided query and context.

    Rules:
    - Be concise and clear.
    - Focus on the key concepts related to the query.
    - Use the provided context to ground your answer.
    - If the context mentions specific topics or subtopics, ensure they are reflected.

    Query:
    {query}

    Content/Context:
    {context}

    - If the context is not related to the query, then generate a summary based on the query alone, but note that context was insufficient.
    """

    def _generate():
        resp = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config={"temperature": 0.5},
        )
        return resp.text or "None"

    return await asyncio.to_thread(_generate)
