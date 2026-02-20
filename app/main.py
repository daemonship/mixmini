from collections import defaultdict
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import (
    UserCreate,
    UserRead,
    UserUpdate,
    auth_backend,
    current_active_user,
    fastapi_users,
)
from app.database import get_db
from app.models import Paint, PaintStatus, User, UserPaint

app = FastAPI(title="MixMini", description="Miniature Paint Inventory & Recipe Manager")

BASE_DIR = Path(__file__).parent

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ---------------------------------------------------------------------------
# Auth routes (FastAPI-Users JSON API)
# ---------------------------------------------------------------------------

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/cookie",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# Optional auth — pages that change content based on login state
current_user_optional = fastapi_users.current_user(active=True, optional=True)


# ---------------------------------------------------------------------------
# Core routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user: Optional[User] = Depends(current_user_optional)):
    return templates.TemplateResponse(request, "index.html", {"user": user})


# ---------------------------------------------------------------------------
# Auth UI routes
# ---------------------------------------------------------------------------


@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request, user: Optional[User] = Depends(current_user_optional)
):
    if user:
        return RedirectResponse("/catalog", status_code=302)
    return templates.TemplateResponse(request, "login.html", {})


@app.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request, user: Optional[User] = Depends(current_user_optional)
):
    if user:
        return RedirectResponse("/catalog", status_code=302)
    return templates.TemplateResponse(request, "register.html", {})


# ---------------------------------------------------------------------------
# Catalog routes
# ---------------------------------------------------------------------------


@app.get("/catalog", response_class=HTMLResponse)
async def catalog(
    request: Request,
    q: Optional[str] = None,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(Paint).order_by(Paint.brand, Paint.range, Paint.name)
    if q:
        query = query.filter(Paint.name.ilike(f"%{q}%"))
    paints = query.all()

    # Map paint_id -> UserPaint for this user
    user_paints: dict[int, UserPaint] = {
        up.paint_id: up
        for up in db.query(UserPaint)
        .filter(UserPaint.user_id == current_user.id)
        .all()
    }

    # Group: brand -> range -> [(paint, user_paint|None)]
    grouped: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for paint in paints:
        grouped[paint.brand][paint.range].append((paint, user_paints.get(paint.id)))

    owned_count = len(user_paints)

    return templates.TemplateResponse(
        request,
        "catalog.html",
        {
            "user": current_user,
            "grouped": grouped,
            "search": q or "",
            "owned_count": owned_count,
            "total_count": len(paints),
        },
    )


@app.post("/catalog/toggle/{paint_id}", response_class=HTMLResponse)
async def catalog_toggle(
    paint_id: int,
    request: Request,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    paint = db.query(Paint).filter(Paint.id == paint_id).first()
    if not paint:
        raise HTTPException(status_code=404, detail="Paint not found")

    existing = (
        db.query(UserPaint)
        .filter(UserPaint.user_id == current_user.id, UserPaint.paint_id == paint_id)
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        user_paint = None
    else:
        new_up = UserPaint(
            user_id=current_user.id, paint_id=paint_id, status=PaintStatus.full
        )
        db.add(new_up)
        db.commit()
        db.refresh(new_up)
        user_paint = new_up

    return templates.TemplateResponse(
        request,
        "partials/paint_card.html",
        {"paint": paint, "user_paint": user_paint, "context": "catalog"},
    )


# ---------------------------------------------------------------------------
# Inventory routes
# ---------------------------------------------------------------------------


@app.get("/inventory", response_class=HTMLResponse)
async def inventory(
    request: Request,
    status: Optional[str] = None,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(UserPaint, Paint)
        .join(Paint, UserPaint.paint_id == Paint.id)
        .filter(UserPaint.user_id == current_user.id)
    )

    if status and status in ("full", "low", "empty"):
        query = query.filter(UserPaint.status == PaintStatus(status))

    rows = query.order_by(Paint.brand, Paint.range, Paint.name).all()

    # Group: brand -> range -> [(user_paint, paint)]
    grouped: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for up, paint in rows:
        grouped[paint.brand][paint.range].append((up, paint))

    # Counts for the filter tabs
    all_count = (
        db.query(UserPaint).filter(UserPaint.user_id == current_user.id).count()
    )
    full_count = (
        db.query(UserPaint)
        .filter(UserPaint.user_id == current_user.id, UserPaint.status == PaintStatus.full)
        .count()
    )
    low_count = (
        db.query(UserPaint)
        .filter(UserPaint.user_id == current_user.id, UserPaint.status == PaintStatus.low)
        .count()
    )
    empty_count = (
        db.query(UserPaint)
        .filter(UserPaint.user_id == current_user.id, UserPaint.status == PaintStatus.empty)
        .count()
    )

    return templates.TemplateResponse(
        request,
        "inventory.html",
        {
            "user": current_user,
            "grouped": grouped,
            "status_filter": status or "",
            "all_count": all_count,
            "full_count": full_count,
            "low_count": low_count,
            "empty_count": empty_count,
        },
    )


@app.post("/inventory/status/{paint_id}", response_class=HTMLResponse)
async def inventory_cycle_status(
    paint_id: int,
    request: Request,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    up = (
        db.query(UserPaint)
        .filter(UserPaint.user_id == current_user.id, UserPaint.paint_id == paint_id)
        .first()
    )
    if not up:
        raise HTTPException(status_code=404, detail="Paint not in inventory")

    paint = db.query(Paint).filter(Paint.id == paint_id).first()

    # Cycle: full → low → empty → full
    _cycle = {
        PaintStatus.full: PaintStatus.low,
        PaintStatus.low: PaintStatus.empty,
        PaintStatus.empty: PaintStatus.full,
    }
    up.status = _cycle[up.status]
    db.commit()
    db.refresh(up)

    return templates.TemplateResponse(
        request,
        "partials/paint_card.html",
        {"paint": paint, "user_paint": up, "context": "inventory"},
    )


@app.post("/inventory/remove/{paint_id}")
async def inventory_remove(
    paint_id: int,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    up = (
        db.query(UserPaint)
        .filter(UserPaint.user_id == current_user.id, UserPaint.paint_id == paint_id)
        .first()
    )
    if up:
        db.delete(up)
        db.commit()
    return Response(content="", media_type="text/html")
