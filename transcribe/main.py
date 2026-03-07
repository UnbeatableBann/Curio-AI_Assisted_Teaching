from fastapi import FastAPI
from router import router as transcribe_router
from scalar_fastapi import get_scalar_api_reference

app = FastAPI(title="Audio Transcription API")

app.include_router(transcribe_router)

@app.get("/")
def health():
    return {"status": "ok"}

@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )

