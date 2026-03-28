# DarkStone Stratum

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![PostGIS](https://img.shields.io/badge/PostGIS-3.3-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5.x-37814A?style=flat-square&logo=celery&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![Leaflet](https://img.shields.io/badge/Leaflet-1.9-199900?style=flat-square&logo=leaflet&logoColor=white)
![Stripe](https://img.shields.io/badge/Stripe-Payments-635BFF?style=flat-square&logo=stripe&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

A production-grade, B2B geospatial risk intelligence platform that detects wildfire hazard zones between high-voltage transmission infrastructure and forest areas across India. Built with a fully async Python backend, distributed task processing, real-time geospatial computation, and an interactive map-based frontend.

---

## Table of Contents

- [Vision](#vision)
- [Architecture Overview](#architecture-overview)
- [Technical Deep Dive](#technical-deep-dive)
- [API Reference](#api-reference)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Collaborators](#collaborators)

---

## Vision

Powerlines that run near dense forests are a leading cause of wildfire ignition. Energy companies operating transmission grids in India lack accessible, automated tooling to continuously monitor and quantify the proximity risk between their infrastructure and surrounding forest coverage.

DarkStone Stratum solves this by giving grid operators a single platform to upload their powerline GeoJSON data, automatically compute geodesic proximity to curated national forest polygons, classify risk into three actionable tiers (High / Medium / Low), and visualize everything on an interactive map. The platform supports full user lifecycle management, a subscription billing layer via Stripe, offline field data sync with conflict resolution, and an ML pipeline that fetches satellite NDVI and LiDAR elevation data to score vegetation risk at each sector.

The goal is to reduce reactive disaster response and shift grid operators toward proactive, data-driven infrastructure management.

---

## Architecture Overview

The system is composed of seven Docker services orchestrated via Docker Compose:

```
[Browser / Frontend]
        |
     Nginx :3000
        |
   +----+----+
   |         |
Static     /api/* proxy
files       |
         FastAPI :8000
        /    |    \
    Auth   Geo   Analysis
    Routes  Routes  Routes
        |         |
   User DB    Analysis DB
  (Postgres)  (PostGIS + pgvector)
        \         /
          Redis :6379
              |
        Celery Worker
        (async task executor)
```

The frontend and backend are fully decoupled. Nginx serves static assets and proxies all API traffic to FastAPI, which means the frontend never needs hardcoded backend ports in production. Two separate Postgres databases are maintained: one for user/auth data and one for all geospatial and analysis data. This separation allows independent scaling and schema evolution.

---

## Technical Deep Dive

### Async FastAPI Backend

The entire backend is built on FastAPI with `asyncpg` as the database driver and `sqlalchemy[asyncio]` for the ORM layer. All database operations use `async/await` throughout, meaning the API never blocks on I/O. Session management uses Redis-backed session tokens rather than stateless JWTs on every protected route, giving us the ability to invalidate sessions server-side on logout or subscription change.

### Dual Database Architecture

Two separate PostgreSQL instances serve distinct domains:

- **User DB** (plain Postgres 15): Handles user registration, hashed passwords (bcrypt), subscription state, and per-user request quotas. Managed via Alembic migrations for schema versioning.
- **Analysis DB** (PostGIS 15-3.3): Stores all geospatial data including powerline LineStrings, forest Polygons, hazard zone Polygons, vegetation records, and analysis job metadata. PostGIS enables native spatial indexing (`GIST` indexes) and geometry operations directly in the database.

### Geospatial Engine (PostGIS + Shapely + pyproj)

The hazard computation engine (`hazard_engine.py`) is the core of the platform. A naive degree-based distance check would introduce significant error across India's latitudinal range. Instead, the engine:

1. Projects all geometries from WGS84 (EPSG:4326) to a UTM zone calculated dynamically from the centroid longitude of each powerline.
2. Computes true geodesic distances in metres using Shapely on the projected geometries.
3. Classifies risk based on distance thresholds: High < 300m, Medium < 600m, Low < 1000m.
4. Buffers the nearest point on the powerline to the forest centroid using the appropriate radius.
5. Reprojects the buffer polygon back to WGS84 for storage and frontend rendering.

This produces accurate, metre-precision hazard zone polygons rather than the crude bounding-box approximations common in simpler implementations.

### Distributed Task Queue with Celery and Redis

Long-running ML analysis jobs (Sentinel-2 NDVI ingestion, LiDAR DEM processing) are offloaded to a Celery worker. The `run_sector_analysis` task is configured with:

- Exponential backoff retry (`retry_backoff=True`, `retry_backoff_max=300s`) for transient API failures against the Sentinel Hub and OpenTopography APIs.
- Up to 5 automatic retries with per-attempt exponential delay.
- `task_acks_late=True` to prevent task loss if the worker crashes mid-execution.
- `worker_prefetch_multiplier=1` to prevent one slow job from blocking others.
- Job status is tracked in the `analysis_jobs` table (queued / running / completed / failed), so the frontend can poll for completion.

Redis serves as both the Celery message broker and the result backend, and also handles all session caching and API response caching.

### ML Pipeline: Satellite + LiDAR Fusion

For each analysis sector, the Celery worker executes a multi-source data fusion pipeline:

1. **Sentinel-2 NDVI** (`ingestion.py`): Calls the Sentinel Hub Process API with a custom evalscript to compute per-pixel NDVI (Normalized Difference Vegetation Index) from Band 4 and Band 8, filtered for cloud coverage under 20%. The result is a single floating-point NDVI value representing vegetation density.

2. **LiDAR / DEM** (`ingestion.py`, `lidar_ops.py`): Downloads a SRTM Digital Elevation Model GeoTIFF from OpenTopography for the sector bounding box. `extract_canopy_height` reads the raster with `rasterio` and returns the 95th percentile elevation as canopy height. `estimate_wire_height_from_dem` approximates wire height from the 10th percentile + 10m offset.

3. **Risk Scoring** (`risk.py`): A weighted composite score is computed from three signals: wire-to-canopy clearance (weight 0.5), NDVI value (weight 0.3), and estimated annual vegetation growth rate (weight 0.2). The score is normalized to [0, 1] and mapped to Critical / High / Medium / Low labels.

4. **Embedding Generation** (`fusion.py`): A 5-dimensional feature vector [NDVI, risk_score, tree_height, clearance, species_encoding] is L2-normalized and stored as JSONB per vegetation record. This enables cosine similarity search across records without a dedicated vector database extension at this stage.

### Hybrid Search

The search endpoint (`search.py`) supports three simultaneous filter modes:

- **Keyword search**: PostgreSQL `to_tsvector` / `plainto_tsquery` full-text search on species names, combined with `ILIKE` pattern matching.
- **Metadata filters**: Sector ID and risk label filtering via indexed columns.
- **Vector similarity**: If a `similar_to` record ID is provided, cosine similarity is computed in Python between the reference record's embedding and all candidate records, then re-ranked by score. This is a pre-computed similarity approach that avoids the need for `pgvector` at the current scale.

### Offline Sync with Conflict Resolution

Field operators working in areas with unreliable connectivity can batch-submit vegetation record updates via `POST /api/v1/sync`. The sync endpoint implements:

- **Idempotency via sync IDs**: Each record carries a client-generated UUID. Redis caches processed sync IDs for 7 days, preventing duplicate processing on re-submission.
- **Timestamp-based conflict resolution**: If a record was previously updated by a satellite analysis job, the human field override wins only if its timestamp is equal to or newer than the satellite timestamp.
- **Human override flag**: Records updated by field operators are flagged `human_override=True` and are excluded from future satellite overwrites, preserving ground-truth observations.

### Session-Based Authentication with Quota Enforcement

Authentication uses bcrypt password hashing and Redis session tokens with a 24-hour TTL. The `get_session_user` dependency resolves the full User object from cache on every protected request, avoiding a DB round-trip for the token lookup. The `require_active_quota` guard enforces per-plan request limits and subscription expiry before any analysis job is accepted.

### Stripe Subscription Billing

Stripe Checkout sessions are created server-side with plan-specific price IDs from environment configuration. A webhook handler at `POST /payments/webhook` processes `checkout.session.completed`, `customer.subscription.deleted`, and `invoice.payment_failed` events to keep subscription state in sync with the user record, including updating `max_requests` to the plan's allocation.

### Frontend: Vanilla SPA with Leaflet

The frontend is a zero-dependency vanilla JavaScript SPA across four HTML pages, served by Nginx. The interactive map uses Leaflet 1.9 with CartoDB tile layers (dark and light themes) and renders three distinct layer groups: powerline LineStrings (blue polylines), forest Polygons (green fills with density-mapped opacity), and hazard zone Polygons (risk-colour-coded with dashed borders for medium/low). All map data comes from the `/api/v1/geodata/dashboard` endpoint. A demo mode bypasses authentication and renders a pre-built dataset of six Indian forest areas and six matching powerline segments for evaluation purposes.

---

## API Reference

All protected routes require a `session_id` query parameter obtained from `POST /login`.

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/register` | Create user account |
| POST | `/login` | Authenticate and receive session token |
| POST | `/logout` | Invalidate session |
| GET | `/me` | Fetch authenticated user profile |
| POST | `/payments/create-checkout` | Create Stripe Checkout session |
| POST | `/payments/webhook` | Stripe webhook event handler |
| POST | `/api/v1/geodata/powerlines` | Upload powerline GeoJSON |
| DELETE | `/api/v1/geodata/powerlines/{id}` | Remove a powerline segment |
| POST | `/api/v1/geodata/hazards/recompute` | Rerun hazard computation for all user powerlines |
| GET | `/api/v1/geodata/dashboard` | Fetch all map data for authenticated user |
| POST | `/api/v1/analysis/sectors` | Create a vegetation analysis sector |
| POST | `/api/v1/analysis/jobs` | Submit an async analysis job |
| GET | `/api/v1/analysis/jobs/{job_id}` | Poll job status |
| GET | `/api/v1/analysis/sectors/{id}/records` | List vegetation records for a sector |
| GET | `/api/v1/search` | Hybrid keyword + vector similarity search |
| POST | `/api/v1/sync` | Batch sync field observation records |

Interactive Swagger docs are available at `http://localhost:8000/docs` when running locally.

---

## Getting Started

### Prerequisites

- Docker 24+
- Docker Compose v2+

### 1. Clone the repository

```bash
git clone https://github.com/your-org/darkstone-stratum.git
cd darkstone-stratum
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values. At minimum, set a strong `JWT_SECRET_KEY` and valid Stripe test keys. Sentinel and OpenTopography keys are optional for local development; the ML pipeline will gracefully skip data fetching if they are absent.

### 3. Place config files at the repo root

Ensure `docker-compose.yml`, `nginx.conf`, and `.env` are all at the repo root (same level as the `DarkStone_Stratum/` directory).

### 4. Build and start all services

```bash
docker compose up --build
```

This builds the Python image, starts both Postgres instances and Redis, runs the DB initialization script and Alembic migrations via the `migrate` service, then starts the API, Celery worker, and Nginx frontend.

### 5. Access the application

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| FastAPI Swagger UI | http://localhost:8000/docs |
| User DB | localhost:5434 |
| Analysis DB | localhost:5433 |
| Redis | localhost:6379 |

### 6. Useful commands

```bash
# Follow API logs
docker compose logs -f api

# Follow Celery worker logs
docker compose logs -f worker

# Restart the API after a code change
docker compose restart api

# Run migrations manually
docker compose run --rm migrate

# Full reset (destroys all data volumes)
docker compose down -v
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `USER_DB_URL` | Async SQLAlchemy URL for the user database |
| `ANALYSIS_DB_URL` | Async SQLAlchemy URL for the analysis/geospatial database |
| `CELERY_URL` | Redis URL used as Celery broker and result backend |
| `JWT_SECRET_KEY` | Secret key for JWT signing |
| `JWT_ALGORITHM` | JWT algorithm (default: HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiry window |
| `SENTINEL_API_KEY` | Sentinel Hub API key for NDVI ingestion |
| `OPENTOPO_API_KEY` | OpenTopography API key for LiDAR DEM download |
| `STRIPE_SECRET_KEY` | Stripe secret key (use test key for development) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `STRIPE_PRICE_INDIVIDUAL` | Stripe Price ID for the Individual plan |
| `STRIPE_PRICE_ENTREPRENEURIAL` | Stripe Price ID for the Entrepreneurial plan |
| `STRIPE_PRICE_GOVERNMENT` | Stripe Price ID for the Government plan |
| `RISK_THRESHOLD_METERS` | Clearance threshold for risk score computation |
| `MAX_REQUESTS_FREE` | Monthly request quota for Free plan users |
| `MAX_REQUESTS_INDIVIDUAL` | Monthly request quota for Individual plan |
| `MAX_REQUESTS_ENTREPRENEURIAL` | Monthly request quota for Entrepreneurial plan |
| `MAX_REQUESTS_GOVERNMENT` | Request quota for Government plan (-1 for unlimited) |

---

## Project Structure

```
./
|-- docker-compose.yml
|-- nginx.conf
|-- .env.example
|-- README.md
|-- DarkStone_Stratum/
    |-- backend/
    |   |-- Dockerfile
    |   |-- requirements.txt
    |   |-- alembic.ini
    |   |-- alembic/
    |   |   |-- env.py
    |   |   |-- versions/
    |   |-- app/
    |       |-- main.py
    |       |-- api/v1/endpoints/
    |       |   |-- analysis.py
    |       |   |-- geodata.py
    |       |   |-- search.py
    |       |   |-- sync.py
    |       |-- core/
    |       |   |-- config.py
    |       |   |-- security.py
    |       |-- db/
    |       |   |-- base.py
    |       |   |-- session.py
    |       |-- models/
    |       |   |-- user_models.py
    |       |   |-- analysis_models.py
    |       |   |-- geodata_models.py
    |       |-- schemas/
    |       |   |-- user_schema.py
    |       |   |-- analysis_schema.py
    |       |   |-- geodata_schema.py
    |       |-- ml_engine/
    |       |   |-- ingestion.py
    |       |   |-- lidar_ops.py
    |       |   |-- risk.py
    |       |   |-- fusion.py
    |       |   |-- hazard_engine.py
    |       |-- worker/
    |       |   |-- celery_app.py
    |       |   |-- tasks.py
    |       |-- scripts/
    |           |-- init_db.py
    |-- frontend/
        |-- index.html
        |-- auth.html
        |-- dashboard.html
        |-- subscription.html
        |-- css/main.css
        |-- js/app.js
```

---

## Collaborators

| Name | Role | GitHub |
|------|------|--------|
|  |  |  |
|  |  |  |
|  |  |  |

---

## License

This project is licensed under the MIT License.