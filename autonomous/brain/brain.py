# brain.py
import re
import json
import asyncio
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END

from .brain_state import BrainState

from autonomous.config.settings import settings

from autonomous.tools.quiz_tool.quiz_generator import quiz_generator_tool
from autonomous.tools.images_tool.visual_generator import image_generator_tool
from autonomous.tools.summary_tool.summary_generator import summary_generator_tool
from autonomous.config.logger import get_logger

logger = get_logger(__name__)


# ----------------------------
# Gemini LLM Wrapper
# ----------------------------
try:
    from google import genai
except ImportError:
    genai = None


class GeminiClient:
    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        if genai is None:
            raise RuntimeError("google package not installed.")
        self.api_key = settings.GEMINI_API_KEY
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set.")
        self.client = genai.Client(api_key=self.api_key)
        self.model = model
        self.max_retries = max_retries
        self.base_delay = base_delay

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable (503, 429, etc.)"""
        error_str = str(error).lower()
        error_dict = {}

        # Try to extract error code from exception
        if hasattr(error, "error"):
            if isinstance(error.error, dict):
                error_dict = error.error
            elif hasattr(error.error, "__dict__"):
                error_dict = error.error.__dict__

        # Check for retryable status codes
        status_code = error_dict.get("code", 0)
        if status_code in [503, 429, 500, 502, 504]:
            return True

        # Check error message for retryable patterns
        if any(
            keyword in error_str
            for keyword in [
                "overloaded",
                "unavailable",
                "rate limit",
                "timeout",
                "503",
                "429",
            ]
        ):
            return True

        return False

    async def generate(
        self, prompt: str, temperature: float = 0.2, max_tokens: int = 512
    ) -> str:
        logger.info("Generating with Gemini LLM...")

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model,
                    contents=prompt,
                    config={"temperature": temperature},
                )
                return resp.text

            except Exception as e:
                last_error = e

                # Check if error is retryable
                if self._is_retryable_error(e) and attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)  # Exponential backoff
                    logger.warning(
                        f"API error (attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                    continue

                else:
                    # Non-retryable error or max retries reached
                    logger.error(f"Error during generation: {e}")
                    if hasattr(e, "error") and isinstance(e.error, dict):
                        logger.error(f"Error details: {e.error}")
                    raise

        # If we get here, all retries failed
        raise RuntimeError(
            f"Failed to generate after {self.max_retries} attempts. Last error: {last_error}"
        )


# ----------------------------
# Reasoner class (LLM brain)
# ----------------------------
class Reasoner:
    def __init__(self, gemini: GeminiClient):
        self.llm = gemini

    def _safe_json_parse(self, text: str):
        cleaned = re.sub(r"^```(?:json)?|```$", "", text)
        return json.loads(cleaned)

    async def analyze_transcript(
        self, transcript: str, state: BrainState
    ) -> Dict[str, Any]:
        prompt = f"""
        You are Curio — an AI co-teacher that listens to classroom sessions and understands context.

        Analyze the following transcript and compare it with the maintained state.

        --- Transcript ---
        \"\"\"{transcript}\"\"\"

        --- Last current State ---
        topic: {state.context.get("current_topic")}
        subtopic: {state.context.get("current_subtopic")}
        phase: {state.context.get("current_phase")}
        last_summary: {state.context.get("current_transcript_summary")}

        --- Task ---
        Analyze and reason step-by-step. Do not give any other text beside this json file. Then, return only a JSON object with:
        - topic: main topic discussed (string or null)
        - subtopic: subtopic name  if the topic is partially shifted (string or null)
        - is_new_topic: true/false (is it completely new compared to previous topic?)
        - new_transcript_summary: brief summary of this transcript (string)
        - topic_shift_intensity: slight / moderate / complete
        - phase: explanation / quiz / recap / idle
        - transition_type: smooth / abrupt / none
        - transition_summary: short natural language sentence describing how the transition is with topic
        - confidence: 0–1 float (overall confidence in your analysis)
        """

        try:
            out = await self.llm.generate(prompt, temperature=0.0)
            res = self._safe_json_parse(
                out
            )  # this funcction is unsafe as LLM response may not be valid JSON

            # Ensure all expected keys exist
            defaults = {
                "topic": None,
                "subtopic": None,
                "is_new_topic": False,
                "topic_shift_intensity": "none",
                "phase": "idle",
                "transition_type": "none",
                "transition_summary": None,
                "confidence": 0.0,
                "new_transcript_summary": None,
            }
            for k, v in defaults.items():
                res.setdefault(k, v)

            return res

        except Exception as e:
            logger.warning(f"Analysis failed (LLM error or parse error): {e}")
            return {
                "topic": None,
                "subtopic": None,
                "is_new_topic": False,
                "topic_shift_intensity": "none",
                "phase": "idle",
                "transition_type": "none",
                "transition_summary": None,
                "confidence": 0.0,
                "new_transcript_summary": None,
            }

    async def interpret_command(
        self, command: str, state: BrainState
    ) -> Optional[Dict[str, Any]]:
        prompt = f"""
        Convert teacher command into structured action.
        Command: \"{command}\"
        Current topic: {state.context.get("current_topic")}

        Return JSON with: {{ "type": "quiz|image|recap|summary|null", "payload": string, "confidence": float }}
        """
        try:
            out = await self.llm.generate(prompt, temperature=0.0)
            return json.loads(out)
        except Exception:
            return None

    async def plan_the_state(self, state: BrainState) -> list:
        """
        Core planning logic:
        Uses LLM reasoning to decide what to do next based on the current brain state,
        transition intensity, and action history.
        Returns a list of planned actions.
        """

        transition = state.transition

        prompt = f"""
        You are Curio — an AI Co-Teacher helping a classroom session flow smoothly.

        --- Session History ---
        Topics covered so far: {state.past_topics[-5:]}
        Subtopics covered: {state.past_subtopics[-5:]}
        Recent transcript summaries: {state.past_summaries[-3:]}
        Current Topic: {state.context.get("current_topic")}
        Current Subtopic: {state.context.get("current_subtopic")}
        Current Phase: {state.context.get("current_phase")}
    
        --- Current Context ---
        Transition Type: {transition.get("transition_type")}
        Transition Summary: {transition.get("transition_summary")}
        Topic Shift Intensity: {transition.get("topic_shift_intensity")}
        Transistion Details : {transition.get("transition_details")}
        Is New Topic compare to previous: {transition.get("is_new_topic")}

        --- Action History ---
        Completed : {state.completed_actions}
        Currently Scheduled: {state.planned_actions}
        Future Plans: {state.future_actions}

        --- Objective ---
        1. Generate CURRENT actions to execute *now* needed immediately, based on:
        - current context
        - learning needs
        - gaps in understanding

        2. Generate FUTURE actions to support *upcoming teaching needs*, based on:
        - predicted subtopics
        - curriculum flow
        - upcoming concepts normally taught after this topic
        - transitions that indicate missing scaffolding

        Actions type can be:
        - "quiz": generate a short quiz. Use only AFTER certain topic or subtopic covered
        - "image": generate a relevant image.
        - "3D model": generate a relevant 3D model.
        - "summary": provide a concise summary. Use only at topic end.
        
        -- Instructions --
        - Avoid repeating any action.
        - You can suggest multiple actions of different types if needed.
        - Do not suggest actions for every single topic or subtopic—be selective. Let it be high-level, do not plan too many small actions.
        - Only add actions that are context-aware and meaningful.
        - Do not use summary or quiz action at introduction or immediately at starting of topic.
        - If nothing is needed for a section, return an empty list [].
        - Future actions must relate to:
            * likely upcoming topics
            * the next parts of the chapter
            * predicted gaps in understanding
            * standard teaching sequence

        Return ONLY a strict JSON.
        Example:
        {{
            "current_actions": [ {{ action1 }} , {{ action2 }} ],
            "future_actions": [ {{ action3 }} ]
        }}
        For each actions, the JSON list should contain action objects with:
        - type: "quiz" | "image" | "3D model" | "summary"
        - name: A short name for the action topic,
        - priority: confidence or importance score (0.0-1.0 only),
        - query: specific details or parameters for the action.

        Do not include any explanation or text outside the JSON.
        """

        try:
            out = await self.llm.generate(prompt, temperature=0.4, max_tokens=400)
            res = self._safe_json_parse(out)
            return res
        except Exception as e:
            logger.warning(f"Planning failed (LLM error): {e}")
            return []


# ----------------------------
# LangGraph Nodes
# ----------------------------
async def analyze_node(state: BrainState) -> BrainState:
    logger.info("Analyzing transcript...")
    inputs = state.inputs
    transcript = inputs.get("transcript")
    reasoner = _runner.reasoner

    if not transcript or not transcript.strip():
        state.reasoning_trace.append("No new transcript to analyze this cycle.")
        return state

    if transcript:
        analysis = await reasoner.analyze_transcript(transcript, state)

        if state.context.get("current_transcript_summary"):
            state.past_summaries.append(state.context["current_transcript_summary"])
        if state.context.get("current_subtopic"):
            state.past_subtopics.append(state.context["current_subtopic"])
        if state.context.get("current_topic"):
            state.past_topics.append(state.context["current_topic"])

        state.context.update(
            {
                "current_topic": analysis["topic"],
                "current_subtopic": analysis["subtopic"],
                "current_phase": analysis["phase"],
                "current_transcript_summary": analysis["new_transcript_summary"],
            }
        )

        state.transition.update(
            {
                "transition_type": analysis["transition_type"],
                "transition_summary": analysis["transition_summary"],
                "topic_shift_intensity": analysis["topic_shift_intensity"],
                "is_new_topic": analysis["is_new_topic"],
                "new_transcript_summary": analysis["new_transcript_summary"],
            }
        )

    return state


async def plan_node(state: BrainState) -> BrainState:
    logger.info("Planning next actions...")
    reasoner = _runner.reasoner
    actions = await reasoner.plan_the_state(state)

    if not isinstance(actions, dict):
        return state

    current = actions.get("current_actions", [])
    future = actions.get("future_actions", [])
    for act in current:
        if act not in state.completed_actions and act not in state.planned_actions:
            state.planned_actions.append(act)

    updated_future = []
    seen = set()

    # Keep only last 10 future actions to avoid explosion
    for f in state.future_actions[-10:] + future:
        key = f"{f.get('type')}_{f.get('name')}"
        if key not in seen:
            seen.add(key)
            updated_future.append(f)

    state.future_actions = updated_future
    state.future_actions = updated_future
    logger.info(
        f"Total planned actions: {len(state.planned_actions)} Total future actions: {len(state.future_actions)}"
    )
    return state


async def tool_action(action: dict, state: BrainState):
    if action["type"] == "quiz":
        # Extract context to give to the agent
        context_str = (
            f"Topic: {state.context.get('current_topic')}, "
            f"Subtopic: {state.context.get('current_subtopic')}, "
            f"Recent Summary: {state.context.get('current_transcript_summary')}"
        )
        return {
            "action": action,
            "result": await quiz_generator_tool(
                action.get("query", "Generate Quiz"), context_str
            ),
        }

    if action["type"] == "image":
        return {"action": action, "result": await image_generator_tool(action["query"])}

    if action["type"] == "summary":
        # Extract context to give to the agent
        context_str = (
            f"Topic: {state.context.get('current_topic')}, "
            f"Subtopic: {state.context.get('current_subtopic')}, "
            f"Recent Summary: {state.context.get('current_transcript_summary')}"
        )
        return {
            "action": action,
            "result": await summary_generator_tool(
                action.get("query", "Summarize"), context_str
            ),
        }

    if action["type"] == "recap":
        return {"action": action, "result": "Recap executed"}
    raise ValueError("Unknown action type")


async def execute_node(state: BrainState) -> BrainState:
    logger.info("Executing planned + future actions...")

    # merge both queues
    all_actions = state.planned_actions + state.future_actions

    if not all_actions:
        return state

    tasks = [tool_action(action, state) for action in all_actions]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for action, res in zip(all_actions, results):
        if isinstance(res, Exception):
            state.failed_actions.append({"action": action, "error": str(res)})
        else:
            state.completed_actions.append(res)

    # clear both queues after execution
    state.planned_actions.clear()
    state.future_actions.clear()

    state.reasoning_trace.append("Executed planned and future actions")

    return state


async def monitor_node(state: BrainState) -> BrainState:
    total = len(state.completed_actions) + len(state.planned_actions)
    state.progress = len(state.completed_actions) / max(1, total)
    state.state_summary = await _runner.reasoner.summarize_state(state)
    return state


# ----------------------------
# Build LangGraph
# ----------------------------
def build_brain():
    gemini = GeminiClient()
    reasoner = Reasoner(gemini)

    graph = StateGraph(BrainState)
    graph.add_node("analyze", analyze_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("monitor", monitor_node)

    graph.set_entry_point("analyze")
    graph.add_edge("analyze", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", END)
    # graph.add_edge("monitor", "analyze")

    compiled = graph.compile()
    return compiled, reasoner


# ----------------------------
# Runner
# ----------------------------
class BrainRunner:
    def __init__(self, compiled, reasoner: Reasoner):
        self.graph = compiled
        self.reasoner = reasoner
        self.state = BrainState()

    async def run_transcript(self, transcript: str) -> BrainState:
        """Process a single transcript chunk while preserving memory."""
        if not transcript or not transcript.strip():
            return self.state

        self.state.inputs = {
            "transcript": transcript,
        }

        result = await self.graph.ainvoke(self.state)
        self.state = BrainState(**result)  # persist updated memory
        return self.state


_compiled_graph, _reasoner = build_brain()
_runner = BrainRunner(_compiled_graph, _reasoner)


async def process_transcript(transcript: str) -> BrainState:
    """
    Global entrypoint.
    Memory is preserved across calls automatically.
    """
    return await _runner.run_transcript(transcript)
