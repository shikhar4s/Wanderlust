# Wanderlust

Wanderlust is a travel-planning and local-guide marketplace for building geographically sensible itineraries, finding guides who genuinely cover the destination, and moving a guide request through chat, negotiation, booking and review.

![Wanderlust interface reference](docs/reference-interface.png)

## What works

- Responsive Tourist experience: discovery, attraction cards, selected-place trip builder, editable route workspace with Leaflet/OpenStreetMap markers and lines, saved trips and local-guide marketplace.
- Deterministic itinerary generation based on coordinates, geographic grouping and nearest-neighbour ordering. It does not use an LLM and does not claim a mathematically optimal route.
- A trip-aware Travel Assistant endpoint that never mutates a trip and returns an explicit configuration error when no provider is configured.
- One token-auth architecture with Tourist and Guide roles.
- Normalized guide coverage at city, region, area or attraction level; multiple services with fixed or negotiable pricing.
- Weekly availability and date-time exceptions, plus a master `accepting_bookings` control.
- Transactional guide locking and overlap revalidation at confirmation time. Only the confirmed interval is blocked; cancellation exposes the underlying schedule again.
- Private, participant-authorized WebSocket conversations and append-only negotiation offers.
- Review eligibility tied to the Tourist on a completed booking.
- Separate Tourist and Guide signup/login routes backed by JWT, unique email identities, persisted sessions and matching frontend/backend role enforcement.
- Live global destination geocoding plus OpenStreetMap/Overpass attraction discovery with a cached-results fallback.
- Prefix city suggestions, city/attraction photos when a matching free image is available, and a photo-backed Tourist dashboard.
- Expanded Tourist and Guide profiles with account details and JPG/PNG/WebP uploads (5 MB limit).
- Guide requests can reuse a saved trip or create a one-day trip automatically, then appear under Tourist requests until confirmed.
- A floating Travel Assistant panel appears throughout both authenticated portals.
- Tourist persistence: select attractions, generate/store a dated trip, reorder/move/add/remove stops, optimize a day, save notes and reopen after refresh.
- Guide profile, coverage, services, weekly hours, exceptions and booking toggle screens backed by Django APIs.
- Request, REST chat, price offers, booking confirmation/cancellation, reviews and notifications backed by database records.

## Current implementation boundary

Core Tourist and Guide write flows are connected to the backend. Messaging uses authenticated Channels WebSockets with periodic REST refresh as a fallback. AI guidance requires a configured server-side OpenAI-compatible provider (`AI_API_KEY`, `AI_API_URL`, `AI_MODEL`). City/attraction imagery is best-effort and depends on a matching free Wikimedia thumbnail; places without one use the city's image. OpenStreetMap tiles and live place search depend on external services. Uploaded profile photos are stored in `backend/media/` during development; production needs persistent object storage. PostgreSQL/Redis and production deployment still need to be configured for concurrent use.

## Architecture

```text
React + Redux Toolkit + Vite
        │ REST / WebSocket
Django REST Framework + Channels
        │
PostgreSQL + Redis
        │
Replaceable service adapters
(location, places, routing, imagery, AI)
```

The frontend and backend are independently deployable. Development uses SQLite and the in-memory Channels layer if PostgreSQL/Redis variables are absent; production should use PostgreSQL, Redis and a real ASGI server.

## Project structure

```text
Wanderlust/
├── frontend/                 React application and responsive design system
├── backend/
│   ├── wanderlust/           Django configuration, HTTP and ASGI entrypoints
│   └── core/                 Domain models, APIs, services, chat and tests
├── docs/                     Product reference material
├── docker-compose.yml
├── .env.example
└── README.md
```

## Local setup

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Accounts, trips, guides and requests come from the backend database, not frontend placeholders.

### Backend

```bash
cd backend
python -m venv .venv
# activate the virtual environment
pip install -r requirements.txt
python manage.py makemigrations core
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API starts at `http://localhost:8000/api/`; JWT endpoints are `/api/auth/token/` and `/api/auth/refresh/`. WebSocket chat uses `/ws/conversations/<id>/`.

### Docker

```bash
docker compose up --build
```

Copy `.env.example` to `.env`, replace the development values, and never commit it.

## Environment variables

Core variables are documented in `.env.example`. Provider keys are optional during development. The app should use server-side keys only; no provider or LLM secret belongs in the Vite bundle.

Suggested providers:

- City search and suggestions: Open-Meteo Geocoding API (GeoNames data), or another compatible provider for commercial use.
- Places: OpenTripMap, Foursquare or Google Places through `PlacesService`.
- Routing: OSRM, Mapbox or Google Routes through `RoutingService`.
- Images: matching free Wikipedia/Wikimedia page thumbnails, with a city-level fallback.
- AI: an OpenAI-compatible chat completion endpoint configured only on the server.

The Open-Meteo geocoding endpoint supports prefix search; check its licence and configure a suitable provider for commercial deployment. The public Nominatim endpoint must not be used for autocomplete. Public Overpass instances may be overloaded, so the UI shows cached attraction data when available.

## Core logic

### Itinerary generation

`ItineraryService` sorts coordinates deterministically, distributes them across the available days by geographic band, and applies nearest-neighbour ordering within each day. Provider-backed travel times can replace the haversine fallback without changing the trip API. Manual edits carry a `manually_edited` flag; regeneration is an explicit endpoint action.

### Availability and conflict prevention

Availability combines recurring weekday intervals with explicit available/unavailable exceptions. A confirmed booking is itself the booked interval; the rest of the recurring window is untouched. `Booking.confirm()` locks the guide row in a database transaction, queries for interval overlap (`existing.start < requested.end` and `existing.end > requested.start`), and persists the agreed price separately from the current service price. PostgreSQL is required for meaningful concurrent production protection.

### AI assistant

The assistant receives destination, dates, days and stops as context. It returns guidance only. No AI suggestion is offered as a one-click trip addition; users must verify and add a place themselves through Discover or the planner.

### Chat and negotiation

WebSocket chat requires JWT authentication and conversation membership, persists messages with timestamps/read state, and falls back to REST plus periodic refresh. Negotiation offers are append-only so counteroffers never erase history; the booking snapshots both original and final agreed price.

## Testing

```bash
cd backend
python manage.py test

cd ../frontend
npm run build
```

The included backend suite covers deterministic itinerary output, legal request transitions, overlapping booking rejection and adjacent-time acceptance. Extend it with API permission matrices, exception merging, chat authorization, cancellation and review eligibility before production launch.

## Deployment

- Build the frontend with `npm run build` and deploy `frontend/dist` to a static host or CDN.
- Deploy the backend with Daphne/Uvicorn behind TLS, PostgreSQL and Redis. Run migrations as a release step.
- Configure strict hosts/CORS, secure cookies where applicable, provider rate limits, logging, backups and monitoring.
- Keep external APIs behind the service boundaries in `backend/core/services.py`.

## Screenshots

The polished frontend includes desktop and mobile layouts for Discover, the itinerary planner, Your Trips, Local Guides and the Travel Assistant. Add release screenshots here after deploying to the target environment.
