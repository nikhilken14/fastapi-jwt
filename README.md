# Auth Service — JWT & OAuth2 (FastAPI)

A small, production-shaped authentication service built with **FastAPI**,
**SQLAlchemy (async)**, **PyJWT**, and **bcrypt**. It implements the OAuth2
"password" grant for login and issues short-lived **access tokens** plus
long-lived **refresh tokens**, with role-based access control (`user` vs
`admin`).

## Features

- User registration with bcrypt password hashing
- OAuth2-compatible login (`/auth/token`) — works with Swagger UI's "Authorize" button
- Access + refresh token pairs, each JWT tagged with a `type` claim so an
  access token can't be used to refresh, and a refresh token can't be used
  to call protected routes
- `GET /users/me` — any authenticated user
- `GET /users/admin/all` — admin-only, returns `403` for non-admins
- Centralized, typed config via `pydantic-settings`
- Structured (JSON) logging
- Consistent error responses via a small typed-exception hierarchy
- Async SQLAlchemy + SQLite by default (swap `DATABASE_URL` for Postgres in production)
- Dockerfile + docker-compose for containerized runs
- Integration test suite (pytest + httpx) exercising the full register → login → protected route → refresh flow

## Project layout

```
app/
├── api/
│   ├── deps.py            # get_current_user / require_admin dependencies
│   └── routes/
│       ├── auth.py        # /auth/register, /auth/token, /auth/refresh
│       └── users.py       # /users/me, /users/admin/all
├── core/
│   ├── config.py          # Settings (env-driven)
│   ├── exceptions.py      # AppError hierarchy + FastAPI exception handlers
│   ├── logging.py         # JSON log formatter
│   └── security.py        # password hashing + JWT create/verify
├── db/
│   └── session.py         # async engine/session, init_db()
├── models/
│   └── user.py            # SQLAlchemy User model
├── schemas/
│   └── auth.py             # Pydantic request/response models
├── tests/
│   └── test_auth.py        # integration tests
└── main.py                  # FastAPI app assembly
```

## Requirements

- Python 3.12+ (or Docker)
- See `requirements.txt` for pinned versions (FastAPI, SQLAlchemy, PyJWT, bcrypt, pytest, etc.)

## Setup (local)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then edit SECRET_KEY, etc.
uvicorn app.main:app --reload
```

The API is now at `http://localhost:8000`, with interactive docs at
`http://localhost:8000/docs`.

## Setup (Docker)

```bash
docker compose up --build
```

This builds the image, runs it as a non-root user, and exposes it on
`http://localhost:8040` (mapped to container port `8000`). Data persists in
the `auth-data` volume. Override the signing secret at runtime:

```bash
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))") docker compose up --build
```

## Configuration

All settings are environment variables (see `.env.example`), loaded once via
`app/core/config.py`:

| Variable | Default | Notes |
|---|---|---|
| `APP_NAME` | `auth-service` | Shown in `/health` |
| `ENVIRONMENT` | `development` | `development` \| `staging` \| `production` |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `DATABASE_URL` | `sqlite+aiosqlite:///./auth.db` | Any async SQLAlchemy URL |
| `SECRET_KEY` | *(insecure placeholder)* | **Must** be overridden outside local dev |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |

## API quick reference

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | none | Create a new user |
| POST | `/auth/token` | none | Login (OAuth2 password grant) → access + refresh token |
| POST | `/auth/refresh` | refresh token | Exchange a refresh token for a new token pair |
| GET | `/users/me` | access token | Current user's profile |
| GET | `/users/admin/all` | access token, `admin` role | List all users |
| GET | `/health` | none | Liveness/readiness probe |

Example flow with `curl`:

```bash
# Register
curl -X POST localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "a@example.com", "password": "password123"}'

# Login
curl -X POST localhost:8000/auth/token \
  -d "username=a@example.com&password=password123"

# Call a protected route
curl localhost:8000/users/me -H "Authorization: Bearer <access_token>"
```

## Running the tests

```bash
pip install -r requirements.txt
pytest -v
```

`pytest.ini` sets `asyncio_mode = auto`, which is required for the async
fixtures/tests in `app/tests/test_auth.py` to run under `pytest-asyncio`
(without it, the async `client` fixture is never awaited and every test
fails with `AttributeError: 'async_generator' object has no attribute ...`).

Tests spin up the real FastAPI app against a fresh SQLite schema per test
(drop-all + create-all in the `client` fixture) — no mocking — covering:

- register → login succeeds
- duplicate email registration → `409`
- wrong password → `401`
- protected route without a token → `401`
- protected route with a valid access token → `200`
- non-admin hitting an admin-only route → `403`
- refresh token → new token pair
- access token rejected by the refresh endpoint → `401`

ugh an API response even if a handler is careless.
