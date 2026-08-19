from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.stripe import router as stripe_router

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Still Studio Yoga",
    description="Minimal yoga studio website with class booking",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(stripe_router)


@app.get("/", response_class=FileResponse)
async def home():
    return STATIC_DIR / "index.html"


@app.get("/about", response_class=FileResponse)
async def about():
    return STATIC_DIR / "about.html"


@app.get("/classes", response_class=FileResponse)
async def classes():
    return STATIC_DIR / "classes.html"


@app.get("/blog", response_class=FileResponse)
async def blog():
    return STATIC_DIR / "blog.html"


@app.get("/contact", response_class=FileResponse)
async def contact():
    return STATIC_DIR / "contact.html"
