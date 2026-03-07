from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
import traceback
import shutil
import os
import tempfile
from transcriber import transcribers

router = APIRouter(
    tags=["Transcribe"]
)

@router.post("/transcribe-bytes")
async def transcribe_bytes(
    audio: UploadFile = File(...),
    chunk_number: int = Form(...),
    timestamp: str = Form(...)
):
    try:
        content = await audio.read()
        print(f"Received chunk {chunk_number} at {timestamp}, size: {len(content)} bytes")

        transcription = ""
        if transcribers:
            print(f"Transcribing raw PCM bytes...")
            # Frontend sends Raw PCM 16-bit 16000Hz (no WAV header)
            # Use transcribe_bytes which expects raw PCM and will add WAV header internally
            transcription = transcribers.transcribe_bytes(content, sample_rate=16000)
            print(f"Transcription: {transcription}")
        else:
            print("Transcriber not available.")
            raise HTTPException(status_code=503, detail="Transcriber service not available")

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Audio processed",
                "transcription": transcription
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing audio chunk: {str(e)}")
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.post("/transcribe-file")
async def transcribe_file_endpoint(file: UploadFile = File(...), language: str = "en"):
    """
    Transcribe an uploaded audio file (wav, mp3, etc.).
    """
    if not transcribers:
        raise HTTPException(status_code=503, detail="Transcriber service not available")
    
    tmp_path = None
    try:
        suffix = os.path.splitext(file.filename)[1]
        if not suffix:
            suffix = ".tmp"
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        
        text = transcribers.transcribe_file(tmp_path, language=language)
        return {
            "status": "success", 
            "filename": file.filename,
            "transcription": text
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass
