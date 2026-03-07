from typing import Any, Dict, List

from pydantic import BaseModel, Field


class BrainState(BaseModel):
    # Current Context
    context: Dict[str, Any] = {
        "current_topic": None,
        "current_subtopic": None,
        "current_phase": None,
        "current_transcript_summary": None,
    }

    # Inputs
    inputs: Dict[str, Any] = Field(default_factory=dict)

    # Memory of Session
    concepts_covered: List[str] = Field(default_factory=list)
    past_summaries: List[str] = Field(default_factory=list)
    past_topics: List[str] = Field(default_factory=list)
    past_subtopics: List[str] = Field(default_factory=list)
    resources_used: List[str] = Field(default_factory=list)

    # Planning
    planned_actions: List[Dict[str, Any]] = Field(default_factory=list)
    future_actions: List[Dict[str, Any]] = Field(default_factory=list)
    completed_actions: List[Dict[str, Any]] = Field(default_factory=list)
    failed_actions: List[Dict[str, Any]] = Field(default_factory=list)

    # Transition Tracking
    transition: Dict[str, Any] = Field(
        default_factory=lambda: {
            "transition_type": None,
            "transition_summary": None,
            "topic_shift_intensity": None,
            "is_new_topic": False,
            "new_transcript_summary": None,
            "transition_details": None,
        }
    )

    # Execution Monitoring
    progress: float = 0.0

    # Meta-Cognition
    reasoning_trace: List[str] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    learning_goals: List[str] = Field(default_factory=list)
