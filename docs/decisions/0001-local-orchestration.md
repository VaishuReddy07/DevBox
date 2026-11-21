# Decision 0001: local orchestration

**Status:** accepted
**Date:** 2026-11-20

## Context

The project needs a one-command local environment for four application services and shared PostgreSQL, Redis, and Pub/Sub dependencies. The default should be easy to run, reset, and understand on a developer laptop.

## Decision

Use Docker Compose as the supported default. Keep the application containers stateless, use health checks for dependencies, and make the local Pub/Sub emulator satisfy the same client API used by the services.

## Trade-offs

Compose starts quickly and has a small learning curve, with convenient service DNS and persistent named volumes. It does not reproduce Kubernetes scheduling, service accounts, network policies, or deployment rollouts. A kind cluster can validate Kubernetes manifests and Kubernetes-specific behavior, but it consumes more resources and adds cluster lifecycle and image-loading steps. It should be an optional deployment-learning path, not a prerequisite for running the app.

## Revisit when

Kubernetes manifests become a maintained deliverable, or when local development must reproduce cluster policies, operators, or deployment behavior.
