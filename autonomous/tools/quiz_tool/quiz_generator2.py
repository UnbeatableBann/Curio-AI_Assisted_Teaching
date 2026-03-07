from datetime import datetime, timedelta

import google.generativeai as genaia
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain.agents import AgentType, initialize_agent
from langchain.tools import Tool

from config.settings import settings

# ----------------------------
# Setup
# ----------------------------
load_dotenv()
genaia.configure(api_key=settings.GEMINI_API_KEY)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.7,
)


# ----------------------------
# Date Resolver Tool Function
# ----------------------------
def resolve_date(date_str: str) -> str:
    """Convert natural language date expressions into YYYYMMDD format."""
    today = datetime.now()

    normalized = date_str.strip().lower()

    if normalized in ["today", "now"]:
        return today.strftime("%Y%m%d")

    elif normalized == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y%m%d")

    elif normalized in ["day before yesterday", "the day before yesterday"]:
        return (today - timedelta(days=2)).strftime("%Y%m%d")

    elif normalized == "tomorrow":
        return (today + timedelta(days=1)).strftime("%Y%m%d")

    else:
        # Fallback
        try:
            # Validate format
            datetime.strptime(date_str, "%Y%m%d")
            return date_str
        except ValueError:
            return today.strftime("%Y%m%d")  # fallback to today


# ----------------------------
# Tool Functions
# ----------------------------
def generate_quiz(topic: str) -> str:
    """Generate a quiz from topic or transcript."""
    model = genaia.GenerativeModel("gemini-2.0-flash")
    prompt = f"""
    - Based on topic or contect length, importance, and complexity, generate a suitable number of multiple-choice questions.
    - Always optimize for quality over quantity.

    Generate multiple-choice quiz questions about this topic or content:
    {topic}

    Format:
    Question: ...
    A) ...
    B) ...
    C) ...
    D) ...
    (Correct Answer: X)

    If no meaningful topic, return 'None'.
    """
    response = model.generate_content(prompt)
    return response.text if response.text else "None"


# ----------------------------
# Tools
# ----------------------------
quiz_tool = Tool(
    name="Quiz Generator",
    func=generate_quiz,
    description="Generate a multiple-choice quiz from a topic or transcript.",
)

date_tool = Tool(
    name="Date Resolver",
    func=resolve_date,
    description="Use this tool to get date in 'YYYYMMDD'format. Convert natural language dates like 'today', 'yesterday', 'day before yesterday' into YYYYMMDD format.",
)


tools = [quiz_tool, date_tool]

# ----------------------------
# LangChain Agent
# ----------------------------
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,  # can also try OPENAI_FUNCTIONS
    verbose=True,
)


def quiz_generator_tool(query: str):
    result = agent.run(query)
    return result
