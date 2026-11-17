# Project status

Last updated: 2026-11-17. Update at the end of every work session.

## Where we are

M1 in progress. The backend skeleton is on `feat/backend-skeleton`: Django 5.2 with `dev`, `test`
and `prod` settings, ASGI through Channels and Daphne, a Celery app, a custom `accounts.User`
(email unique) in the first migration, and `/health/` checking MySQL and Redis (503 when either
fails). `compose.yaml` runs MySQL 8.4, Redis, the backend and one worker. pytest runs against the
Compose MySQL (coverage gate 90%, now 100%), and Ruff and mypy (strict, django-stubs) pass.
Dependencies are pinned in `backend/pyproject.toml` with `uv.lock`.

Color tokens are in `frontend/src/styles/tokens.css` (see [design.md](design.md)). No frontend app
yet.

## Next session

1. Vite + React + TypeScript app with Vitest and ESLint; import `tokens.css` and map the semantic
   tokens into the Tailwind theme.
2. Add the `backend` (MySQL and Redis service containers, Ruff, mypy, pytest), `frontend` (runs
   `node frontend/scripts/check-contrast.mjs`) and `codeql` CI jobs, then make them required
   checks in the "Protect main" ruleset (`.github/rulesets/protect-main.json` and the repository
   settings).
3. Dependabot entries for `uv`, npm and Docker.
4. Accounts: sign up, sign in, password reset, email verification (adds DRF and drf-spectacular).

## Open questions

- Presence design (see [architecture.md](architecture.md)).
- Guest permissions and the allowed message formatting.
- Typefaces, spacing and type scale (see [design.md](design.md)).
- `apps/core` 100% branch coverage gate: add a separate coverage run for it once it has code.
