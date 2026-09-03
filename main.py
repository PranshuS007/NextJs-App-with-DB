from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from api.auth_pg import router as auth_router, session_user
from api.bookings import router as bookings_router
from api.content import router as content_router
from api.stripe import router as stripe_router

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Still Studio Yoga",
    description="Minimal yoga studio website with class booking",
    version="1.0.0",
)
app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    return response


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(auth_router)
app.include_router(bookings_router)
app.include_router(content_router)
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


@app.get("/login", response_class=FileResponse)
async def login_page():
    return STATIC_DIR / "login.html"


@app.get("/register", response_class=FileResponse)
async def register_page():
    return STATIC_DIR / "register.html"


@app.get("/forgot-password", response_class=FileResponse)
async def forgot_password_page():
    return STATIC_DIR / "forgot-password.html"


@app.get("/dashboard")
async def dashboard(request: Request):
    if session_user(request) is None:
        return RedirectResponse("/login")
    return FileResponse(STATIC_DIR / "dashboard.html")
