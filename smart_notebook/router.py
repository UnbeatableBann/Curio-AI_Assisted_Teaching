from fastapi import APIRouter, HTTPException
from smart_notebook.models import (
    SmartNoteModel,
    NotebookResponse,
    ImageGenRequest,
    ImageGenResponse,
)
from smart_notebook.generator import notebook_generator
from smart_notebook.visual_generator import visual_generator
from smart_notebook.db import notebook_db
from autonomous.brain.db import brain_db
from autonomous.config.logger import get_logger
import asyncio

router = APIRouter(prefix="/notebook", tags=["Smart Notebook"])
logger = get_logger("curio.smart_notebook.api")


@router.post("/generate", response_model=SmartNoteModel)
async def generate_smart_note():
    """
    Fetches the latest brain state from database and generates a smart note from it.
    """
    try:
        # 1. Fetch latest state from database
        latest_state = await asyncio.to_thread(brain_db.get_latest_state)
        if not latest_state:
            raise HTTPException(
                status_code=404, detail="No brain state found in database."
            )

        # 2. Generate Note Content
        note_content = await notebook_generator.generate_note(latest_state)

        # 3. Construct Note Object
        topic = latest_state.get("current_topic") or "General"
        subtopic = latest_state.get("current_subtopic") or "General"

        note_data = {
            "topic": topic,
            "subtopic": subtopic,
            "content": note_content,
        }

        image = await visual_generator.generate(note_content)

        if image:
            note_data["image"] = image
        # 4. Save to DB
        saved_note = await asyncio.to_thread(notebook_db.save_note, note_data)
        if not saved_note:
            logger.warning("Note generated but failed to save to DB.")
            return SmartNoteModel(
                topic=topic, subtopic=subtopic, content=note_content, image=image
            )

        return SmartNoteModel(**saved_note)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in generate_smart_note: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-from-latest", response_model=SmartNoteModel)
async def create_note_from_latest_state():
    """
    Fetches the latest brain state from Supabase, generates a note, saves it, and returns it.
    """
    try:
        # 1. Fetch latest state
        latest_state = await asyncio.to_thread(brain_db.get_latest_state)
        if not latest_state:
            raise HTTPException(
                status_code=404, detail="No brain state found in database."
            )

        # 2. Convert directly to request model (filtering compatible fields)
        # Using construct or parse_obj to handle potential extra fields gracefully if needed
        # But here we just pass the dict to the generator

        # 3. Generate Note Content
        note_content = await notebook_generator.generate_note(latest_state)

        # 4. Construct Note Object
        topic = latest_state.get("current_topic") or "General"
        subtopic = latest_state.get("current_subtopic") or "General"

        note_data = {
            "topic": topic,
            "subtopic": subtopic,
            "content": note_content,
        }

        # 5. Save to DB
        saved_note = await asyncio.to_thread(notebook_db.save_note, note_data)

        if not saved_note:
            logger.warning("Note generated from latest state but failed to save.")
            return SmartNoteModel(topic=topic, subtopic=subtopic, content=note_content)

        return SmartNoteModel(**saved_note)

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in create_note_from_latest_state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=NotebookResponse)
async def get_notebook():
    """
    Retrieves all smart notes to form a complete notebook.
    """
    try:
        notes_data = await asyncio.to_thread(notebook_db.get_all_notes)
        notes = [SmartNoteModel(**n) for n in notes_data]
        return NotebookResponse(notes=notes)
    except Exception as e:
        logger.error(f"Error fetching notebook: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch notebook.")
