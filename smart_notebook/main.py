from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from smart_notebook.router import router as notebook_router
from autonomous.config.logger import get_logger

# Setup logging
logger = get_logger("curio.smart_notebook.main")

# Create FastAPI app
app = FastAPI(
    title="Curio Smart Notebook API",
    description="API for generating and managing AI-powered smart notes from brain states.",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(notebook_router)


@app.get("/")
async def root():
    """
    Root endpoint providing API information.
    """
    return {
        "message": "Curio Smart Notebook API is running.",
        "version": "1.0.0",
        "endpoints": {
            "POST /notebook/generate": "Generate a smart note from the latest brain state.",
            "POST /notebook/create-from-latest": "Create and save a note from the latest brain state.",
            "GET /notebook/all": "Retrieve all saved smart notes.",
            "GET /health": "Health check endpoint.",
            "GET /scalar": "API documentation (Scalar UI).",
        },
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok", "service": "smart_notebook"}


@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    """
    Scalar API documentation interface.
    """
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Curio Smart Notebook API",
    )


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Curio Smart Notebook API server...")
    uvicorn.run(
        "smart_notebook.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
    )
