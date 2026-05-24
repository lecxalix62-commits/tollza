from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import auth, communities, drafts, monitor, autopilot


STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    autopilot.start_scheduler()
    yield


app = FastAPI(
    title="VK Comment Assistant",
    version="0.4.0",
    description="Post comments to VK community posts with manual approval workflow.",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(communities.router)
app.include_router(drafts.router)
app.include_router(monitor.router)
app.include_router(autopilot.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def landing() -> FileResponse:
    return FileResponse(STATIC_DIR / "landing.html")


@app.get("/app", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
