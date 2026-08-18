# MOVIES MAGIC CLUB 4.0

A production-ready Telegram movie filter bot built with **Aiogram 3**, **FastAPI webhooks**, **PostgreSQL**, **Redis**, and **TMDB**.

## Development status

**Phase 1 — Telegram webhook foundation**

The project is intentionally being built in stages. Telegram update delivery and bot responsiveness will be verified before movie indexing and search features are added.

## Architecture

- Python 3.12+
- Aiogram 3 — Telegram Bot API framework
- FastAPI — webhook and health endpoints
- PostgreSQL — persistent movie/file data
- Redis — cache and short-lived state
- TMDB — movie metadata and identity

## Phase 1 goals

1. Start the FastAPI application reliably.
2. Expose `/health` for deployment health checks.
3. Register a Telegram webhook safely.
4. Receive Telegram updates through the webhook.
5. Verify `/start` and basic message responses in private chats and groups.
6. Add structured logging and error handling.

Movie indexing and TMDB functionality will be added only after the Telegram foundation is proven healthy.

