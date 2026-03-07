from typing import List, Optional

from pydantic import BaseModel


class SmartNoteRequest(BaseModel):
    current_transcript_summary: Optional[str] = None
    current_subtopic: Optional[str] = None
    current_topic: Optional[str] = None
    past_subtopics: Optional[List[str]] = []
    past_topics: Optional[List[str]] = []
    past_summaries: Optional[List[str]] = []


class SmartNoteModel(BaseModel):
    topic: str
    subtopic: str
    content: str  # Markdown/HTML content
    image: Optional[str] = None
    # Potentially raw data if needed?


class NotebookResponse(BaseModel):
    notes: List[SmartNoteModel]


class ImageGenRequest(BaseModel):
    prompt: str


class ImageGenResponse(BaseModel):
    image_base64: str
