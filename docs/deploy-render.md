# Render Deployment (All-in-One)

This project runs locally with the root `docker-compose.yml` (Postgres, Redis,
frontend build, Django/Daphne, Celery worker, Celery beat). Render cannot run
Compose files or share the `spa_dist` volume between service builds, so the
all-in-one deploy uses two files:

- `Dockerfile.render` — multi-stage image: stage 1 builds the Vite SPA, stage 2
  builds the Django backend and bakes the SPA into `/app/spa_dist` (with the
  `.build-complete` marker the entrypoint expects). One image, all roles.
- `render.yaml` — Render Blueprint that provisions every service from that
  single image, plus managed Postgres and Redis.

No application code changes are required: Django still serves the SPA, the
WebSocket route (`/ws/weather/`) is served by Daphne directly, and all
environment-driven settings in `backend/config/settings.py` are reused.

## Deploy steps

1. Push this repository to GitHub/GitLab.
2. In the Render dashboard: **New → Blueprint**, select the repository.
   Render reads `render.yaml` and creates:
   - `weather-backend` (web, Dockerfile.render, health check `/health/`)
   - `weather-worker` (Celery worker)
   - `weather-beat` (Celery beat)
   - `weather-db` (managed Postgres)
3. The first deploy pauses on `sync: false` variables. In the dashboard set:
   - `REDIS_URL` (required): Render blueprints cannot provision Redis, so
     create a Render Key Value instance in the dashboard, or use a free
     provider such as Upstash, and paste its URL (e.g.
     `redis://default:pass@host:6379`).
   - `OPENWEATHER_API_KEY` (required for live data; empty is a supported
     degraded mode)
   - `LLM_API_KEY` / `LLM_API_BASE` (optional, chat assistant)
   - `LLM_MODEL` if you want a model other than `gpt-4o-mini`
4. Deploy finishes; verify `https://weather-backend.onrender.com/health/`
   reports `status: ok` and `provider_configured: true`.

## Plan/cost notes

- Background workers (`weather-worker`, `weather-beat`) require a paid Starter
  plan each on Render. On a strict free budget, the worker/beat pair can be
  replaced by a Render Cron Job running the refresh path every minute, at the
  cost of losing on-demand refresh tasks.
- Free Postgres expires after 30 days; upgrade or point `DATABASE_URL` at an
  external database.
- Key Value (Redis) has no free plan. To use a free managed Redis (e.g.
  Upstash), remove `weather-redis` from `render.yaml` and set `REDIS_URL` to
  the external URL in every service.

## Throttles and custom domains

`ALLOWED_HOSTS` defaults to `.onrender.com` (subdomain wildcard). When adding
a custom domain, update the variable to include it. Throttles are tunable via
`THROTTLE_REFRESH`, `THROTTLE_EXPORT`, `THROTTLE_CHAT` as in local mode.
