from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("CAIS starting up")
    yield
    log.info("CAIS shutting down")


app = FastAPI(
    title="CAIS — Citizen Application Intelligence System",
    version="1.0.0",
    description="AI-powered government document analysis for Indian citizens",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers — uncomment as you build them
# from app.api.upload import router as upload_router
# from app.api.analysis import router as analysis_router
# from app.api.guidance import router as guidance_router
# from app.api.progress import router as progress_router
# app.include_router(upload_router, prefix="/api/v1")
# app.include_router(analysis_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    return {"message": "CAIS API is running. Go to /docs for API reference."}