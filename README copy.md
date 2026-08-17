# Road Intersection AI

Full-stack foundation for road marking analysis and intersection improvement. This milestone loads real nearby road geometry from OpenStreetMap and displays it as GeoJSON on a MapLibre map.

## Architecture

The system uses `IntersectionScene` as the future semantic representation and GeoJSON as the frontend/backend interchange format. OSM is treated as one data source, not the domain model.

Current request flow:

```text
Vue MapLibre click
  -> Pinia store
  -> typed API service
  -> FastAPI /api/intersections
  -> OSMClient
  -> OSMParser
  -> GeoJSON FeatureCollection EPSG:4326
  -> MapLibre road layer
```

Future AI/CV, TDX enrichment, criteria evaluation, improvement planning, and controlled image generation have architectural boundaries but no fake implementation.

## Technology Stack

- Frontend: Vue 3, TypeScript, Vite, Pinia, Vue Router, MapLibre GL JS, Axios
- Backend: Python 3.12+, FastAPI, Pydantic, SQLAlchemy, httpx, GeoPandas, Shapely, PyProj
- Docker: backend Dockerfile plus Compose for backend and frontend

## Directory Structure

```text
road-intersection-ai/
├── frontend/
│   └── src/
│       ├── components/
│       ├── router/
│       ├── services/
│       ├── stores/
│       ├── types/
│       └── views/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── database/
│   │   ├── domain/
│   │   ├── schemas/
│   │   └── services/
│   └── tests/
├── docker-compose.yml
└── README.md
```

## Environment Requirements

- Python 3.12+
- Node.js 20+ or 22+
- npm
- Docker Desktop, optional

## Installation

Backend:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env
```

## Backend Startup

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/api/health
```

## Frontend Startup

```bash
cd frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

## Docker Startup

```bash
docker compose up --build
```

Then open `http://localhost:5173`.

## Environment Variables

Backend:

- `APP_NAME`
- `CORS_ORIGINS`
- `OVERPASS_URL`
- `OSM_TIMEOUT_SECONDS`

Frontend:

- `VITE_API_BASE_URL`, defaults to `http://localhost:8000/api`

## API Overview

`GET /api/health`

```json
{
  "status": "ok"
}
```

`POST /api/intersections`

```json
{
  "latitude": 25.033,
  "longitude": 121.565,
  "radiusMeters": 100
}
```

Response:

```json
{
  "intersectionId": "generated-id",
  "location": {
    "latitude": 25.033,
    "longitude": 121.565
  },
  "geojson": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

Tests cover the health endpoint, coordinate validation, mocked intersection GeoJSON responses, and OSM parser conversion. They do not depend on the public Overpass API.

## Current Milestone

Implemented:

- MapLibre map with pan, zoom, click selection, and marker
- Selected coordinate display
- `Analyze Intersection` request to FastAPI
- OSM Overpass road query
- Raw OSM parsing into normalized road features
- GeoJSON FeatureCollection response in WGS84 / EPSG:4326
- MapLibre rendering of returned road geometry
- Loading and structured error states

## Future Roadmap

- Add PostgreSQL/PostGIS persistence
- Add TDX traffic data enrichment
- Add satellite imagery ingestion and georeferencing
- Add CV-based semantic vectorization
- Add machine-readable road design criteria
- Add specialized evaluators returning structured findings
- Add improvement planning that creates a revised `IntersectionScene`
- Add controlled before/after image generation from deterministic geometry
