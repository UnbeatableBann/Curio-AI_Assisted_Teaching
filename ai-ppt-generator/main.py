import os
import shutil
from typing import List, Optional, Dict, Any
from datetime import datetime
from io import BytesIO
import asyncio
import traceback

from fastapi import FastAPI, File, UploadFile, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from scalar_fastapi import get_scalar_api_reference
from pydantic import BaseModel
import uvicorn

# Imports from slide generator logic
try:
    from vector_store import store_document, extract_text
    from slidetext_generator import user_input
    from ppt_export import export_to_pptx
    from classifier import classify_content
    from transcriber import transcribers
except ImportError as e:
    print(f"Warning: Could not import backend modules: {e}")
    transcribers = None

app = FastAPI(title="Curio AI Tutor API", docs_url=None, redoc_url=None)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
UPLOAD_DIR = "uploads"
PPTX_DIR = "generated_pptx"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PPTX_DIR, exist_ok=True)

# --- Endpoints ---

@app.get("/")
async def root():
    return {"message": "Curio  Tutor API is running"}

@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Curio AI Tutor API"}

@app.post("/api/upload-doc")
async def upload_document(files: List[UploadFile] = File(...)):
    """
    Upload documents, store them in vector DB, and categorize them using Gemini.
    """
    uploaded_files_info = []
    
    try:
        for file in files:
            # Read content
            content = await file.read()
            file_stream = BytesIO(content)
            
            # Store in Vector DB (RAG)
            doc_id = store_document(file_stream, file.filename)
            
            # Re-read for classification
            file_stream.seek(0)
            text_content = extract_text(file_stream, file.filename)
            
            # Classify
            category = classify_content(text_content)
            
            print(f"Processed: {file.filename} -> ID: {doc_id} | Category: {category}")
            
            uploaded_files_info.append({
                "filename": file.filename,
                "doc_id": doc_id,
                "category": category
            })
            
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
        
    return {
        "status": "success", 
        "files": uploaded_files_info,
        "message": "Files uploaded and categorized successfully"
    }

class GenerateRequest(BaseModel):
    topic: str

@app.post("/api/generate-ppt")
def generate_ppt(request: GenerateRequest):
    """
    Generate PPT based on the uploaded documents (context) and topic.
    """
    try:
        print(f"Generating PPT for topic: {request.topic}")
        data = user_input(request.topic)
        
        # Pass full data to export_to_pptx to use the theme
        pptx_filename = export_to_pptx(data)
        
        # Format response
        slides_for_frontend = data['slides'] if isinstance(data, dict) and 'slides' in data else data
            
        return {
            "status": "success",
            "slides": slides_for_frontend, 
            "pptx_filename": pptx_filename,
            "download_url": f"/api/download-ppt/{pptx_filename}"
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download-ppt/{filename}")
async def download_ppt(filename: str):
    file_path = os.path.join(PPTX_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(
            file_path, 
            filename=filename, 
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    raise HTTPException(status_code=404, detail="File not found")

# WebSocket (Mock)
@app.websocket("/ws/home")
async def home_updates(websocket: WebSocket):
    await websocket.accept()
    # Mock data...
    try:
        while True:
            await asyncio.sleep(10)
    except:
        pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
