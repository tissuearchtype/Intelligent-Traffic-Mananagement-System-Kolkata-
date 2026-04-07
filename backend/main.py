"""
=============================================================
  Intelligent Traffic Management System — Backend Entry Point
  Run: python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
=============================================================
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# FIX: Changed to relative imports based on the project root
from backend.model.detector import TrafficDetector
from backend.api.routes import router as api_router
from backend.api.websocket import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[ITMS] Loading Keras traffic detection model...")
    app.state.detector = TrafficDetector()
    app.state.detector.load()
    print("[ITMS] Model ready. Starting server.")
    yield
    print("[ITMS] Shutting down.")


app = FastAPI(
    title="Intelligent Traffic Management System — Kolkata",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# These assume you are running uvicorn from the ITMS_PROJECT root directory
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

app.include_router(api_router, prefix="/api")
app.include_router(ws_router, prefix="/ws")


@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"request": request})