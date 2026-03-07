# Curio AI Co-Teacher

Curio AI Co-Teacher is a multi-service classroom assistant that supports:
- Autonomous classroom understanding from streamed audio
- AI tools (quiz, images, summary)
- Smart notebook generation from saved class memory
- AI-powered PPT generation from uploaded classroom documents

This repository is a monorepo with separate backend services and one React frontend.

## Project Structure

```text
Curio-AI-Co-Teacher/
├── autonomous/                # Main autonomous brain API (FastAPI, LangGraph)
│   ├── main.py
│   ├── brain/
│   │   ├── brain.py
│   │   ├── brain_state.py
│   │   └── db.py
│   ├── tools/
│   │   ├── quiz_tool/
│   │   ├── images_tool/
│   │   └── summary_tool/
│   ├── config/
│   │   ├── settings.py
│   │   └── logger.py
│   ├── Dockerfile
│   └── docker-compose.yml
├── smart_notebook/            # Smart notebook API (FastAPI)
│   ├── main.py
│   ├── router.py
│   ├── generator.py
│   ├── visual_generator.py
│   └── db.py
├── ai-ppt-generator/          # PPT generation API (FastAPI)
│   ├── main.py
│   ├── vector_store.py
│   ├── slidetext_generator.py
│   ├── visual_generator.py
│   ├── ppt_export.py
│   └── classifier.py
├── frontend/                  # React web app
│   ├── package.json
│   └── src/components/
├── audio/                     # Local audio pipeline utilities (recorder/transcriber/wakeword)
├── uploads/                   # Uploaded documents runtime folder
├── generated_pptx/            # Generated presentations runtime folder
└── README.md
```

## How It Works

### 1. Autonomous Classroom Flow (`autonomous/`)

1. Frontend records microphone audio in browser and sends PCM chunks to `POST /transcribe-bytes`.
2. Autonomous API transcribes chunks via Reverie SDK.
3. Transcript text is sent to LangGraph brain (`process_transcript`).
4. Brain pipeline runs:
   - `analyze`: infer topic/subtopic/phase/summary
   - `plan`: create current + future actions
   - `execute`: run tools (quiz/image/summary)
5. Results are broadcast to frontend over `ws://localhost:8000/ws/home`.
6. On stop (`POST /stop`), brain state is saved to Supabase (`brain_memory` table).

### 2. Smart Notebook Flow (`smart_notebook/`)

1. Smart Notebook API reads latest autonomous brain state from Supabase via `brain_db.get_latest_state()`.
2. Gemini generates structured student notes.
3. Optional educational visual is generated (Gemini image model) and returned as Base64.
4. Final note is stored in Supabase (`smart_notes` table).
5. Frontend page fetches notes from `GET http://localhost:8002/notebook/all`.

### 3. PPT Generation Flow (`ai-ppt-generator/`)

1. User uploads docs via frontend to `POST /api/upload-doc`.
2. Service extracts text, stores embeddings in FAISS, and classifies content.
3. User provides topic via `POST /api/generate-ppt`.
4. Service performs retrieval + generation, creates slide content, exports `.pptx`.
5. File download is available at `GET /api/download-ppt/{filename}`.

## Server Communication Model

### Current Communication Paths

- `frontend -> autonomous` via HTTP + WebSocket (`:8000`)
- `frontend -> smart_notebook` via HTTP (`:8002`)
- `frontend -> ai-ppt-generator` via HTTP (`:8000` in that service)
- `autonomous -> Supabase` for brain memory persistence
- `smart_notebook -> Supabase` for reading brain memory and saving notes
- `autonomous/smart_notebook/ai-ppt-generator -> Gemini/Reverie/other external APIs`

### Important Note About Ports

Both `autonomous/main.py` and `ai-ppt-generator/main.py` are configured to run on port `8000` by default. They cannot run on the same host port at the same time without changing one port or adding a reverse proxy/API gateway.

### Service Coupling

- Smart Notebook does not call Autonomous over REST.
- It imports shared Python modules (`autonomous.config.*`, `autonomous.brain.db`) and uses the same Supabase backend.
- This is tight code-level coupling inside one monorepo Python environment.

## APIs Overview

### Autonomous API (`autonomous/main.py`)

- `GET /api/health`
- `POST /transcribe-bytes`
- `POST /process`
- `GET /state`
- `POST /reset`
- `POST /stop`
- `POST /tools/quiz`
- `POST /tools/image`
- `POST /tools/summary`
- `WS /ws/home`

### Smart Notebook API (`smart_notebook/main.py`)

- `GET /health`
- `POST /notebook/generate`
- `POST /notebook/create-from-latest`
- `GET /notebook/all`

### PPT Generator API (`ai-ppt-generator/main.py`)

- `GET /api/health`
- `POST /api/upload-doc`
- `POST /api/generate-ppt`
- `GET /api/download-ppt/{filename}`
- `WS /ws/home` (placeholder/mock loop)

## Tech Stack By Component

### Frontend (`frontend/`)

- React 18
- React Router
- Framer Motion
- Lucide React
- React Markdown
- Browser APIs: MediaDevices, Web Audio, WebSocket, Fetch

### Autonomous Service (`autonomous/`)

- FastAPI + Uvicorn
- LangGraph (stateful workflow orchestration)
- Gemini (`google-genai`) for reasoning and planning
- Reverie SDK for STT (audio-to-text)
- Supabase Python client for persistence
- FAISS + sentence-transformers + HuggingFace (image retrieval/ranking)
- Scalar for API docs (`/scalar`)
- Docker + Docker Compose

### Smart Notebook Service (`smart_notebook/`)

- FastAPI + APIRouter
- Gemini text generation for note synthesis
- Gemini image generation for notebook visuals
- Supabase persistence (`smart_notes`)
- Reuses Autonomous settings/logger/database access modules

### PPT Generator Service (`ai-ppt-generator/`)

- FastAPI + Uvicorn + python-multipart
- LangChain ecosystem (`langchain`, `langchain-community`, `langchain-google-genai`)
- FAISS vector index
- Document parsing: PyMuPDF, python-docx, python-pptx
- Pillow + HuggingFace Hub + Requests for visuals/assets
- Scalar docs

### Audio Utilities (`audio/`)

- Local orchestration classes for:
  - Continuous PCM recording
  - Wake word pipeline integration
  - Command capture and transcription
  - WAV export and transcript generation

## Environment Variables

Primary environment loading is handled in `autonomous/config/settings.py` (from `../.env`).

Key variables used across services include:
- `GEMINI_API_KEY`
- `REVERIE_API_KEY`, `REVERIE_APP_ID`
- `SUPABASE_URL`, `SUPABASE_KEY`
- `GOOGLE_SEARCH_API_KEY`, `GOOGLE_CX`, `SERPAPI_KEY`
- `UNSPLASH_ACCESS_KEY`
- `PICOVOICE_API_KEY`, `WAKEUP_WORD_PATH`
- `APPWRITE_*`

For PPT service-specific setup, see `ai-ppt-generator/.env.example`.

## Local Run Guide

### 1. Frontend

```bash
cd frontend
npm install
npm start
```

### 2. Autonomous API (default port 8000)

```bash
uvicorn autonomous.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Smart Notebook API (default port 8002)

```bash
uvicorn smart_notebook.main:app --host 0.0.0.0 --port 8002 --reload
```

### 4. PPT Generator API

If autonomous is already using `8000`, run PPT API on another port:

```bash
cd ai-ppt-generator
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Then update frontend API URLs or proxy config accordingly.

## Known Integration Gaps

- Hardcoded frontend URLs currently target localhost ports directly.
- No API gateway/unified backend routing yet.
- `autonomous` and `ai-ppt-generator` default port conflict (`8000`).
- Smart Notebook is coupled to autonomous Python modules rather than independent service contracts.

## License

This project is intended for educational and research usage. Ensure compliance with API provider terms and local regulations for classroom audio processing.

