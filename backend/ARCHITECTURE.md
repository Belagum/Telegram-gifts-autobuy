# Backend architecture overview

The backend package now sits directly under the repository's `backend/` root,
so importing `backend.*` works without the extra `src/` hop. Inside the package
we retain the layered design for the autobuy subsystem:

- **Domain layer (`backend/domain`)** — immutable entities (`GiftCandidate`,
  `ChannelFilter`, `AccountSnapshot`) encapsulate invariants. A `PurchasePlan`
  acts as a unit-of-work collecting `PurchaseOperation` objects.
- **Application layer (`backend/application`)** — use-cases orchestrate domain
  logic. The `AutobuyUseCase` coordinates validation, planning, execution and
  reporting while relying on explicit ports.
- **Ports & adapters (`backend/application/interfaces.py`,
  `backend/infrastructure`)** — repositories and external integrations are
  described through thin Protocols. SQLAlchemy adapters materialise domain
  objects. Telegram access is routed via dedicated async adapters.
- **Composition (`backend/container.py`)** — a lightweight DI container wires
  together application services and adapters.
- **Cross-cutting concerns** — structured logging with per-request correlation
  identifiers lives in `backend/shared/logging`; reusable `ApplicationError`
  instances enable a single error handler in Flask.

Unit tests cover the planner, validator and use-case orchestration to prevent
regressions in critical business rules. Pytest uses the repository root as the
import base so the runtime layout matches the development one.
