import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

from langchain_core.prompts import PromptTemplate
from langchain_core.tools import Tool
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain.agents import AgentExecutor, create_react_agent

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from audio.orchestrator import orchestrators
from config.settings import settings

# --- Configuration ---
SUMMARIES_DIR = "class_summaries"
if not os.path.exists(SUMMARIES_DIR):
    os.makedirs(SUMMARIES_DIR)

llm = ChatGoogleGenerativeAI(model="gemini-pro", api_key=settings.GEMINI_API_KEY)


# --- Tool Functions ---
def load_yesterdays_summary_func(_input: str = None) -> str:
    """Retrieve the summary of yesterday's class."""
    yesterday = datetime.now() - timedelta(days=1)
    filepath = os.path.join(SUMMARIES_DIR, f"{yesterday.strftime('%Y-%m-%d')}.txt")
    try:
        with open(filepath, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "No summary was found for yesterday."


def generate_summary_func(transcript: str) -> str:
    """Generate a clean bullet-point summary (do not save)."""
    if not transcript or len(transcript.split()) < 10:
        return "The transcript is too short to create a meaningful summary."

    prompt = f"""
    Summarize the following class transcript into clear, concise bullet points.
    Focus only on the key topics and important points.

    Transcript:
    ---
    {transcript}
    ---
    """
    try:
        return llm.invoke(prompt).content
    except Exception as e:
        return f"Error generating summary: {e}"


def generate_and_save_summary_func(transcript: str) -> str:
    """Generate and save today’s summary."""
    summary = generate_summary_func(transcript)
    filepath = os.path.join(SUMMARIES_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.txt")
    with open(filepath, "w") as f:
        f.write(summary)
    return f"Summary generated and saved successfully:\n{summary}"


def get_current_transcription(_input: str = None) -> str:
    """Fetch ongoing class transcription."""
    return orchestrators.get_live_transcription() or "No live transcription."


def get_particular_transcription(date_str: str) -> str:
    """Fetch transcript of a particular date."""
    return orchestrators.get_transcript_by_date(date_str) or f"No transcript found for {date_str}."


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
        try:
            datetime.strptime(date_str, "%Y%m%d")
            return date_str
        except ValueError:
            return today.strftime("%Y%m%d")  # fallback

def get_transcripts_in_range(start_date: str, end_date: str) -> str:
    """Fetch all transcripts in a given date range (inclusive)."""
    transcripts = []
    current = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")

    while current <= end:
        date_str = current.strftime("%Y%m%d")
        transcript = orchestrators.get_transcript_by_date(date_str)
        if transcript:
            transcripts.append(f"--- {date_str} ---\n{transcript}")
        current += timedelta(days=1)

    return "\n\n".join(transcripts) if transcripts else f"No transcripts found between {start_date} and {end_date}."

def generate_range_summary(start_date: str, end_date: str) -> str:
    """Generate a summary across multiple transcripts in a date range."""
    transcripts = get_transcripts_in_range(start_date, end_date)
    if transcripts.startswith("No transcripts"):
        return transcripts
    return generate_summary_func(transcripts)


# --- Tool Wrappers ---
tools = [
    Tool(
        name="load_yesterdays_summary",
        func=load_yesterdays_summary_func,
        description="Retrieve the summary of yesterday's class."
    ),
    Tool(
        name="generate_summary",
        func=generate_summary_func,
        description="Generate a summary from a transcript without saving it."
    ),
    Tool(
        name="generate_and_save_summary",
        func=generate_and_save_summary_func,
        description="Generate and save a summary of today's class from a transcript."
    ),
    Tool(
        name="Current Transcript Retrieval",
        func=get_current_transcription,
        description="Retrieve the transcript of the current class."
    ),
    Tool(
        name="Past Transcript Retrieval",
        func=get_particular_transcription,
        description="Retrieve transcript of a specific date (YYYYMMDD)."
    ),
    Tool(
        name="Date Resolver",
        func=resolve_date,
        description="Convert natural language dates like 'yesterday' or 'day before yesterday' into YYYYMMDD format."
    ),
]


# --- Prompt Template ---
prompt = PromptTemplate.from_template(
    """
    You are a smart classroom summary assistant. You can retrieve transcripts and generate summaries
    based on user queries. You can also resolve natural language dates.

    Available Tools:
    {tools}

    To use a tool, use this format:
    Thought: Do I need to use a tool? Yes
    Action: The action to take, should be one of [{tool_names}]
    Action Input: The input to the action
    Observation: The result of the action

    If you have the final answer for the user, use this format:
    Thought: Do I need to use a tool? No
    Final Answer: [your response here]

    Begin!

    User Query: {input}

    Thought:{agent_scratchpad}
    """
)


# --- Agent Setup ---
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=settings.GEMINI_API_KEY)

react_agent = create_react_agent(llm, tools, prompt)

summary_agent_executor = AgentExecutor(
    agent=react_agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=5,
)


# --- Entrypoint Function ---
def run_summary_agent(query: str):
    """Main entry point to invoke the smart summary agent."""
    response = summary_agent_executor.invoke({"input": query})
    return response["output"]


# --- Example Usage ---
if __name__ == "__main__":
    queries = [
        "Can you summarize today's class?"
    ]

    for q in queries:
        print(f"\n>>> Query: {q}")
        print(run_summary_agent(q))
