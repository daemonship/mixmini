# Miniature Paint Inventory & Recipe Manager

> Tabletop painters struggle to track which paints they own across brands, manage custom mix recipes, and see what they need for upcoming projects.

## Feedback & Ideas

> **This project is being built in public and we want to hear from you.**
> Found a bug? Have a feature idea? Something feel wrong or missing?
> **[Open an issue](../../issues)** — every piece of feedback directly shapes what gets built next.

## Status

> 🚧 In active development — not yet production ready

| Feature | Status | Notes |
|---------|--------|-------|
| Project scaffold & CI | ✅ Complete | FastAPI + HTMX + Jinja2, SQLite, Alembic, Dockerfile, GitHub Actions |
| Database schema, auth & paint seed | ✅ Complete | SQLAlchemy models, FastAPI-Users cookie auth, 395-paint catalog |
| Paint catalog browse & inventory UI | 🚧 In Progress | |
| Recipe builder & recipe list | 📋 Planned | |
| Code review | 📋 Planned | |
| Pre-launch verification | 📋 Planned | |
| Deploy to production | 📋 Planned | Fly.io with persistent SQLite volume |

## What It Solves

Tabletop miniature hobbyists and painters need a way to:
- Track which paints they own across Citadel, Vallejo, and other brands
- Build and save custom mix recipes with paint ratios
- See at a glance which recipe components they own vs. need to buy

## Tech Stack

- **Backend:** Python + FastAPI
- **Frontend:** HTMX + Jinja2 templates (server-rendered, no JS framework)
- **Database:** SQLite via SQLAlchemy + Alembic migrations
- **Auth:** FastAPI-Users (email/password, cookie sessions) — Task 2
- **Deploy:** Fly.io with persistent volume for SQLite

## Getting Started

### Prerequisites

- Python 3.10+

### Local Development

```bash
# Install dependencies
pip install ".[dev]"

# Run the development server
uvicorn app.main:app --reload

# Run tests
pytest -q
```

The app will be available at `http://localhost:8000`.

### Database Migrations

```bash
# Run migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"
```

### Docker

```bash
docker build -t mixmini .
docker run -p 8000:8000 -v mixmini-data:/data mixmini
```

## Project Structure

```
mixmini/
├── app/
│   ├── main.py          # FastAPI app, routes, auth wiring
│   ├── database.py      # SQLAlchemy engine, session, Base
│   ├── models.py        # ORM models: User, Paint, UserPaint, Recipe, RecipeComponent
│   ├── auth.py          # FastAPI-Users setup, cookie transport, JWT strategy
│   ├── static/          # CSS, JS assets
│   └── templates/       # Jinja2 HTML templates
├── alembic/             # Database migrations
├── scripts/
│   └── seed_paints.py   # Seeds 395 Citadel + Vallejo Game Color paints
├── tests/               # pytest test suite
├── Dockerfile
└── pyproject.toml
```

### Seeding the paint catalog

After running migrations, seed the paint database:

```bash
python scripts/seed_paints.py
```

This loads 395 paints covering Citadel (Base, Layer, Shade, Dry, Contrast, Technical) and Vallejo Game Color, Game Air, and Wash ranges — with hex color values and paint type metadata.

### Data backup (Docker)

Your SQLite database lives in the `/data` volume. To find and copy it out:

```bash
# Find the volume path on disk
docker volume inspect mixmini-data

# Copy the database file out for backup
docker run --rm -v mixmini-data:/data busybox cat /data/mixmini.db > backup.db
```

---

*Built by [DaemonShip](https://github.com/daemonship) — autonomous venture studio*
