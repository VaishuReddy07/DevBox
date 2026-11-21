# DevBox

Start the API, worker, scheduler, notifier, PostgreSQL, Redis, and a Pub/Sub emulator together with Docker Compose. DevBox is a local environment for developing event-driven backend flows.

## Requirements

- Docker Desktop with the Compose plugin (or Docker Engine and Compose)
- PowerShell on Windows, or Bash for the helper script

## Start

From this directory, run in PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
```

Or use the Bash helper, which creates `.env` from `.env.example` when needed:

```bash
bash scripts/devbox up
```

Open the API docs at [http://localhost:8100/docs](http://localhost:8100/docs) or check [http://localhost:8100/health](http://localhost:8100/health). `docker compose ps` shows service status.

## Use the environment

| Action | PowerShell command |
| --- | --- |
| Add reproducible sample events | `docker compose exec -T api python -m app.seed` |
| Clear events, outbox, notifications, and event cache | `docker compose exec -T api python -m app.reset` |
| Follow service logs | `docker compose logs -f` |
| Stop services and keep database data | `docker compose down` |
| Remove services and database data | `docker compose down -v --remove-orphans` |

The Bash helper also supports `seed`, `reset`, `logs`, `down`, and `clean`: `bash scripts/devbox <command>`. The `clean` command removes the database volume and its data.

Default host ports are API `8100`, PostgreSQL `55432`, Redis `56379`, and Pub/Sub `58085`. Change the corresponding `DEVBOX_*_PORT` values in `.env` if a port is already in use.

## Event flow

Use the API docs or send an event with `curl`:

```bash
curl -X POST http://localhost:8100/events \
  -H 'content-type: application/json' \
  -d '{"kind":"access.granted","payload":{"user_id":"user-42","resource":"reports"}}'
```

The API saves the event and an outbox record in one database transaction. The scheduler publishes it to the Pub/Sub emulator; the worker processes it, and the notifier records a notification. Check the event at `GET /events/{id}` and notifications at `GET /notifications`. Scheduled events use `POST /events/scheduled` with an ISO 8601 `scheduled_at` value that includes a timezone. Use an `Idempotency-Key` header when retrying a write.

## Checks and design notes

GitHub Actions validates Compose, builds and starts the stack, seeds sample data, and runs `scripts/smoke.sh` against the asynchronous flow. The Compose versus kind trade-offs are in [decision 0001](docs/decisions/0001-local-orchestration.md); the outbox design is in [decision 0002](docs/decisions/0002-transactional-outbox.md).

## Scope

This is a local development environment, not a production deployment. It uses local-only credentials and an unauthenticated sample API. Production use requires authentication, TLS, managed secrets, and deployment-specific resource limits.
