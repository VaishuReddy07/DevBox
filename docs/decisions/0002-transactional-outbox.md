# Decision 0002: publish events through a transactional outbox

**Status:** accepted
**Date:** 2026-11-20

## Context

Writing an event row and publishing it to Pub/Sub are separate operations. Publishing after a database commit can leave a durable event that is never delivered if the process exits between those operations.

## Decision

The API writes the event and its outbox row in the same PostgreSQL transaction. The scheduler service dispatches pending outbox rows and marks them published only after Pub/Sub acknowledges the message. Consumers remain idempotent because delivery is at least once.

## Consequences

The event is accepted even when Pub/Sub is temporarily unavailable; the durable outbox retries on the next scheduler pass. A process crash after publish but before marking the row can create a duplicate delivery, so the worker and notifier deduplicate by event ID. A production deployment should add backoff, dead-letter handling, and operational alerts for old pending rows.
