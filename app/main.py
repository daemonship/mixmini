from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

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
from app.models import Paint, PaintStatus, Recipe, RecipeComponent, User, UserPaint

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


# ---------------------------------------------------------------------------
# Recipe routes
# ---------------------------------------------------------------------------


@app.get("/recipes", response_class=HTMLResponse)
async def recipe_list(
    request: Request,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    recipes = db.query(Recipe).filter(Recipe.user_id == current_user.id).order_by(Recipe.name).all()
    # For each recipe, load components and paints
    recipe_data = []
    for recipe in recipes:
        components = db.query(RecipeComponent, Paint).join(Paint, RecipeComponent.paint_id == Paint.id).filter(RecipeComponent.recipe_id == recipe.id).all()
        recipe_data.append({
            "recipe": recipe,
            "components": components,
        })
    return templates.TemplateResponse(
        request,
        "recipes/list.html",
        {"user": current_user, "recipe_data": recipe_data},
    )


@app.get("/recipes/new", response_class=HTMLResponse)
async def recipe_new(
    request: Request,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    # Get all paints for the searchable selection
    paints = db.query(Paint).order_by(Paint.brand, Paint.range, Paint.name).all()
    return templates.TemplateResponse(
        request,
        "recipes/new.html",
        {"user": current_user, "paints": paints},
    )


@app.post("/recipes", response_class=HTMLResponse)
async def recipe_create(
    request: Request,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    name = form.get("name")
    note = form.get("note", "")

    if not name:
        raise HTTPException(status_code=400, detail="Recipe name required")

    # Parse components: paint_id and ratio pairs
    # Expecting form fields like components[0][paint_id], components[0][ratio]
    # Simpler: we'll accept paint_ids and ratios as lists with matching indices
    paint_ids = form.getlist("paint_id")
    ratios = form.getlist("ratio")
    
    # Validate
    components = []
    for paint_id_str, ratio_str in zip(paint_ids, ratios):
        if not paint_id_str or not ratio_str:
            continue
        try:
            paint_id = int(paint_id_str)
            ratio = int(ratio_str)
            if ratio <= 0:
                raise ValueError("Ratio must be positive")
            paint = db.query(Paint).filter(Paint.id == paint_id).first()
            if not paint:
                raise HTTPException(status_code=400, detail=f"Paint {paint_id} not found")
            components.append((paint_id, ratio))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid paint id or ratio")

    # Create recipe
    recipe = Recipe(user_id=current_user.id, name=name, note=note)
    db.add(recipe)
    db.commit()
    db.refresh(recipe)

    # Add components
    for paint_id, ratio in components:
        comp = RecipeComponent(recipe_id=recipe.id, paint_id=paint_id, ratio=ratio)
        db.add(comp)
    db.commit()

    return RedirectResponse(f"/recipes/{recipe.id}", status_code=303)


@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(
    recipe_id: int,
    request: Request,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == current_user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Get components with paint details
    components = db.query(RecipeComponent, Paint).join(Paint, RecipeComponent.paint_id == Paint.id).filter(RecipeComponent.recipe_id == recipe.id).all()

    # Get user's paints for ownership check
    user_paint_ids = {up.paint_id for up in db.query(UserPaint).filter(UserPaint.user_id == current_user.id).all()}

    # Compute total ratio for normalization (optional)
    total_ratio = sum(rc.ratio for rc, _ in components)

    return templates.TemplateResponse(
        request,
        "recipes/detail.html",
        {
            "user": current_user,
            "recipe": recipe,
            "components": components,
            "user_paint_ids": user_paint_ids,
            "total_ratio": total_ratio,
        },
    )


@app.get("/recipes/{recipe_id}/edit", response_class=HTMLResponse)
async def recipe_edit(
    recipe_id: int,
    request: Request,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == current_user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Get existing components with paint details
    components = db.query(RecipeComponent, Paint).join(Paint, RecipeComponent.paint_id == Paint.id).filter(RecipeComponent.recipe_id == recipe.id).all()

    # All paints for selection
    paints = db.query(Paint).order_by(Paint.brand, Paint.range, Paint.name).all()

    return templates.TemplateResponse(
        request,
        "recipes/edit.html",
        {
            "user": current_user,
            "recipe": recipe,
            "components": components,
            "paints": paints,
        },
    )


@app.post("/recipes/{recipe_id}", response_class=HTMLResponse)
async def recipe_update(
    recipe_id: int,
    request: Request,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == current_user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    form = await request.form()
    name = form.get("name")
    note = form.get("note", "")

    if not name:
        raise HTTPException(status_code=400, detail="Recipe name required")

    # Parse components (same as create)
    paint_ids = form.getlist("paint_id")
    ratios = form.getlist("ratio")
    components = []
    for paint_id_str, ratio_str in zip(paint_ids, ratios):
        if not paint_id_str or not ratio_str:
            continue
        try:
            paint_id = int(paint_id_str)
            ratio = int(ratio_str)
            if ratio <= 0:
                raise ValueError("Ratio must be positive")
            paint = db.query(Paint).filter(Paint.id == paint_id).first()
            if not paint:
                raise HTTPException(status_code=400, detail=f"Paint {paint_id} not found")
            components.append((paint_id, ratio))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid paint id or ratio")

    # Update recipe
    recipe.name = name
    recipe.note = note
    # Delete existing components
    db.query(RecipeComponent).filter(RecipeComponent.recipe_id == recipe.id).delete()
    # Add new components
    for paint_id, ratio in components:
        comp = RecipeComponent(recipe_id=recipe.id, paint_id=paint_id, ratio=ratio)
        db.add(comp)
    db.commit()

    return RedirectResponse(f"/recipes/{recipe.id}", status_code=303)


@app.post("/recipes/{recipe_id}/delete")
async def recipe_delete(
    recipe_id: int,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == current_user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    db.delete(recipe)
    db.commit()
    return RedirectResponse("/recipes", status_code=303)


# HTMX endpoint for paint search in recipe builder
@app.get("/recipes/paint-search", response_class=HTMLResponse)
async def paint_search(
    request: Request,
    q: Optional[str] = None,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    query = db.query(Paint).order_by(Paint.brand, Paint.range, Paint.name)
    if q:
        query = query.filter(Paint.name.ilike(f"%{q}%"))
    paints = query.limit(20).all()
    return templates.TemplateResponse(
        request,
        "partials/paint_search_results.html",
        {"paints": paints},
    )
