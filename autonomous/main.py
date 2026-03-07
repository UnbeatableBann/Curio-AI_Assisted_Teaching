import asyncio
from typing import List, Optional

# Imports from the local package
from autonomous.brain.brain import _runner, process_transcript
from autonomous.brain.brain_state import BrainState as BrainStateModel
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from reverie_sdk import ReverieClient
from scalar_fastapi import get_scalar_api_reference
from autonomous.tools.images_tool.visual_generator import image_generator_tool
from autonomous.tools.quiz_tool.quiz_generator import quiz_generator_tool
from autonomous.tools.summary_tool.summary_generator import summary_generator_tool
from autonomous.brain.db import brain_db
from smart_notebook.generator import notebook_generator
from smart_notebook.db import notebook_db

from autonomous.config.settings import settings

from autonomous.config.logger import get_logger

# Setup logging
logger = get_logger("curio.brain.api")

# Lock to ensure sequential processing of brain tasks
processing_lock = asyncio.Lock()

app = FastAPI(
    title="Curio Autonomous Brain API",
    description="API wrapper for the Curio AI Co-Teacher autonomous brain.",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------------
# WebSocket Manager
# -------------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to websocket: {e}")


manager = ConnectionManager()


@app.websocket("/ws/home")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def broadcast_state(state: BrainStateModel):
    """
    Parses the brain state and broadcasts relevant updates to the frontend.
    """
    try:
        payload = {
            "images": [],
            "quiz": [],
            "summary": state.context.get("current_transcript_summary") or "",
            "model": state.context.get("current_transcript_summary") or "Processing...",
        }

        for action_result in state.completed_actions:
            # Each result is {"action": input_action, "result": output}
            if not isinstance(action_result, dict):
                continue

            action = action_result.get("action", {})
            result = action_result.get("result")
            action_type = action.get("type")

            if action_type == "image":
                if isinstance(result, list):
                    payload["images"].extend(result)

            elif action_type == "quiz":
                if isinstance(result, list):
                    payload["quiz"].extend(result)

            elif action_type == "summary":
                # result is string
                if isinstance(result, str):
                    payload["summary"] = result

        await manager.broadcast(payload)

    except Exception as e:
        logger.error(f"Error preparing broadcast: {e}")


reverie_client = ReverieClient(
    api_key=settings.REVERIE_API_KEY,
    app_id=settings.REVERIE_APP_ID,
)


class TranscriptRequest(BaseModel):
    transcript: str


class ToolRequest(BaseModel):
    query: str
    context: Optional[str] = "General context"


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "message": "Curio Autonomous Brain Service is running.",
        "endpoints": {
            "POST /process": "Send a transcript chunk to be processed.",
            "GET /state": "Get the current full state of the brain.",
            "POST /reset": "Reset the brain state.",
            "POST /tools/quiz": "Generate a quiz.",
            "POST /tools/image": "Generate/Search for images.",
            "POST /tools/summary": "Generate a summary.",
        },
    }


@app.post("/transcribe-bytes")
async def transcribe_bytes(
    audio: UploadFile = File(...),
    chunk_number: int = Form(...),
    timestamp: str = Form(...),
):
    """
    Transcribe uploaded audio bytes using Reverie ASR.
    Supports chunked streaming uploads.
    """
    try:
        # Read audio bytes
        audio_bytes = await audio.read()

        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        logger.info(
            f"Transcribing audio chunk={chunk_number}, "
            f"timestamp={timestamp}, "
            f"filename={audio.filename}"
        )

        # Call Reverie ASR
        response = await asyncio.to_thread(
            reverie_client.asr.stt_file,
            src_lang="en",
            data=audio_bytes,
        )

        logger.info(f"Transcription result: {response}")

        # Extract text from response
        transcript_text = ""
        # Check for object attributes based on log: id, text, final, cause, success, confidence, display_text
        if hasattr(response, "display_text") and response.display_text:
            transcript_text = response.display_text
        elif hasattr(response, "text") and response.text:
            transcript_text = response.text
        elif isinstance(response, dict):
            transcript_text = response.get("display_text") or response.get("text") or ""
        elif isinstance(response, str):
            transcript_text = response

        # Process the transcript with the brain
        if transcript_text and transcript_text.strip():
            logger.info(f"Processing transcript text with brain: {transcript_text}")
            # Ensure sequential processing
            async with processing_lock:
                try:
                    updated_state = await process_transcript(transcript_text)
                    # Broadcast updates to frontend via WebSocket
                    await broadcast_state(updated_state)
                except Exception as brain_error:
                    logger.error(f"Brain processing failed: {brain_error}")
                    # Continue execution to return transcript
                    pass

        return {
            "chunk_number": chunk_number,
            "timestamp": timestamp,
            "filename": audio.filename,
            "transcript": transcript_text,
        }

    except Exception as e:
        logger.error(f"ASR transcription error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to transcribe audio",
        )


@app.post("/process", response_model=BrainStateModel)
async def process_transcript_endpoint(request: TranscriptRequest):
    """
    Sends a transcript chunk to the autonomous brain.
    The brain analyzes it, updates its state, maintains context, and plans/executes actions.
    Returns the updated BrainState.
    """
    try:
        transcript = request.transcript
        if not transcript.strip():
            # If empty transcript, just return current state without processing
            return _runner.state

        logger.info(f"Processing transcript chunk of length {len(transcript)}...")

        # Invoke the brain
        updated_state = await process_transcript(transcript)

        # Log summary of actions if any
        if updated_state.completed_actions:
            logger.info(f"Completed actions: {len(updated_state.completed_actions)}")

        return updated_state

    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@app.get("/state", response_model=BrainStateModel)
async def get_current_state():
    """
    Retrieve the current persisted state of the brain.
    """
    return _runner.state


@app.post("/reset")
async def reset_brain_state():
    """
    Resets the internal state of the brain (clears history, context, etc.).
    """
    # Re-initialize the state
    _runner.state = BrainStateModel()
    logger.info("Brain state has been reset.")
    return {"message": "Brain state reset successfully."}


@app.post("/stop")
async def stop_session():
  """
  Stops the current session and saves the brain state to the database.
  """
  logger.info("Stop signal received. Saving brain state...")
  # Run DB operation in thread pool to avoid blocking event loop
  result = await asyncio.to_thread(brain_db.save_state, _runner.state)

  if result:
    # Supabase returns the inserted row as a dict, usually with 'id'
    saved_id = result.get("id") or "unknown"
    return {"message": "Session stopped and state saved.", "id": saved_id}
  else:
    # If saving failed, we still return 200 ok for the stop action, but with a warning message
    return {"message": "Session stopped, but failed to save state (check logs)."}


# -------------------------------------------------------------------------
# Tool Endpoints
# -------------------------------------------------------------------------


@app.post("/tools/quiz")
async def generate_quiz(req: ToolRequest):
    """
    Directly invoke the Quiz Generator Tool.
    """
    try:
        # Run synchronous tool in threadpool
        result = await asyncio.to_thread(quiz_generator_tool, req.query, req.context)
        return {"result": result}
    except Exception as e:
        logger.error(f"Quiz tool error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/image")
async def generate_image(req: ToolRequest):
    """
    Directly invoke the Image Generator Tool.
    """
    try:
        # This tool is already async
        result = await image_generator_tool(req.query)
        return {"result": result}
    except Exception as e:
        logger.error(f"Image tool error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/summary")
async def generate_summary(req: ToolRequest):
    """
    Directly invoke the Summary Generator Tool.
    """
    try:
        # Run synchronous tool in threadpool
        result = await asyncio.to_thread(summary_generator_tool, req.query, req.context)
        return {"result": result}
    except Exception as e:
        logger.error(f"Summary tool error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        # Your OpenAPI document
        openapi_url=app.openapi_url,
        # Avoid CORS issues (optional)
        scalar_proxy_url="https://proxy.scalar.com",
    )
