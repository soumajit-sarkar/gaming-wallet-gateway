# Gaming Wallet Gateway — Python Backend Architecture

A public-safe reference implementation of a multi-client gaming wallet gateway built with Python, FastAPI, SQLAlchemy and MySQL.

The project focuses on correctness of wallet operations: tenant isolation, atomic balance updates, database row locking, idempotent requests, append-only transaction/ledger postings and traceability.

> This repository is an independently developed reference implementation. It does not contain proprietary production source code, production credentials, customer data, private provider endpoints or confidential infrastructure.

## Current implementation status

| Area | Status |
|---|---|
| FastAPI application and health check | Implemented |
| Client API-key authentication | Implemented (SHA-256 hash stored in DB) |
| Client-scoped player creation | Implemented |
| Multi-currency wallet creation | Implemented |
| Balance retrieval | Implemented |
| Debit and credit | Implemented |
| Partial refund of a successful debit | Implemented |
| Full rollback of a successful debit or credit | Implemented, if no prior reversal exists |
| Administrative debit/credit adjustment | Implemented |
| Idempotency and request-payload conflict detection | Implemented |
| Atomic wallet + transaction + ledger + idempotency persistence | Implemented |
| MySQL migrations and financial check constraints | Implemented; requires local DB verification |
| Automated service/API tests | Implemented; SQLite-backed test suite |
| RabbitMQ | Transactional outbox publisher and idempotent example consumer implemented |
| Redis locking | Optional token-based distributed lock; MySQL row locks remain authoritative |
| Provider catalog and generic HTTP adapter framework | Implemented; concrete vendor-specific adapters/callbacks require provider API specifications |
| Transactional outbox and retry publisher | Implemented; requires RabbitMQ integration testing |
| MongoDB operational logging | Not implemented |

The production-scale figures sometimes discussed in connection with the author's professional experience are not performance benchmarks of this public repository.

## Architecture

```mermaid
flowchart TD
    Client[Gaming Client] -->|X-Client-API-Key| API[FastAPI Gateway]
    API --> Auth[Client Authentication]
    Auth --> Player[Player and Wallet Services]
    Auth --> Tx[Transaction Service]
    Tx --> Idem[Idempotency Repository]
    Tx --> PlayerRepo[Player Repository]
    Tx --> WalletRepo[Wallet Repository]
    Tx --> TxRepo[Transaction Repository]
    Tx --> LedgerRepo[Wallet Ledger Repository]
    Tx --> Outbox[Transactional Outbox]
    Outbox --> DB[(MySQL)]
    Idem --> DB
    PlayerRepo --> DB
    WalletRepo --> DB
    TxRepo --> DB
    LedgerRepo --> DB
    Outbox --> Publisher[Outbox Publisher]
    Publisher --> MQ[(RabbitMQ)]
    MQ --> Consumer[Idempotent Consumer]
    Tx -. optional lock .-> Redis[(Redis)]
    Tx --> Provider[Provider/Game Catalog]
```

## Financial consistency rules

1. `client_id` is derived from the authenticated API key. It is never accepted from the transaction request body.
2. Player lookup is scoped by `(client_id, external_player_id)`.
3. A wallet is uniquely identified by `(player_id, currency)`.
4. Amounts use `Decimal` and `NUMERIC(20, 4)`. Floating-point values are not used for money.
5. The transaction service locks the player and wallet rows before calculating a new balance. MySQL/InnoDB row locks serialize updates to the same player/wallet.
6. The wallet balance, transaction record, ledger entry and successful idempotency response are committed in one database transaction.
7. A failed business operation stores its failure response against the idempotency key without changing the wallet balance.
8. Reusing an idempotency key with a different operation or payload returns a conflict.
9. A refund creates a new transaction linked to the original debit. Partial refunds are allowed, but cumulative reversals cannot exceed the original amount.
10. A rollback creates a new transaction linked to the original debit or credit and reverses its full amount. A transaction with an existing refund/rollback cannot be rolled back again.
11. Database constraints enforce non-negative wallet balances, positive transaction/ledger amounts, valid transaction states and the ledger balance equation.

Redis is an optional coordination layer, not the financial source of truth. Database constraints and transactional row locking remain mandatory whether Redis is enabled or disabled.

## Technology

- Python 3.12+
- FastAPI
- Pydantic v2 / pydantic-settings
- SQLAlchemy 2.x
- MySQL 8 / InnoDB
- Alembic
- PyMySQL
- RabbitMQ / Pika (transactional outbox publisher, durable topic exchange and dead-letter queue)
- HTTPX (generic provider HTTP adapter)
- Redis (optional; install from `requirements-redis.txt`)
- pytest (test runner; install separately in the development environment)

## Setup

### 1. Install dependencies

Install [uv](https://docs.astral.sh/uv/) and run:

```bash
uv sync
```

### 2. Configure the database

Git Bash:

```bash
cp .env.example .env
```

Edit `.env` and set a valid MySQL connection string. Example:

```dotenv
DATABASE_URL=mysql+pymysql://wallet_user:your_password@127.0.0.1:3306/gaming_wallet
APP_NAME=Gaming Wallet Gateway
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=false
```

Create the database and user in MySQL before running migrations. Do not commit `.env`.

### 3. Apply migrations

```bash
uv run alembic upgrade head
```

The latest migration changes the wallet unique key, adds the original-transaction link and adjustment reason, adds financial check constraints, and adds a nullable client API-key hash. Review migrations against any existing database before applying them.

### 4. Create a client API key

```bash
uv run python -m scripts.create_client --code demo-client --name "Demo Client"
```

The command stores only the SHA-256 hash and prints the plaintext API key once. Store that key in a password manager or secret manager. Do not put it in source control.

### 5. Start the API

```bash
uv run uvicorn app.main:app --reload
```

- Health: `GET http://127.0.0.1:8000/health`
- OpenAPI UI: `http://127.0.0.1:8000/docs`

## API examples

Every business endpoint requires `X-Client-API-Key`. Every transaction endpoint also requires a unique `Idempotency-Key` header.

### Create a player

```bash
curl -X POST http://127.0.0.1:8000/api/v1/players \
  -H "X-Client-API-Key: YOUR_CLIENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"external_id":"player-1001","username":"demo-player"}'
```

### Create a wallet

```bash
curl -X POST http://127.0.0.1:8000/api/v1/wallets \
  -H "X-Client-API-Key: YOUR_CLIENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"external_player_id":"player-1001","currency":"INR"}'
```

### Credit a wallet

```bash
curl -X POST http://127.0.0.1:8000/api/v1/transactions/credit \
  -H "X-Client-API-Key: YOUR_CLIENT_API_KEY" \
  -H "Idempotency-Key: demo-credit-001" \
  -H "Content-Type: application/json" \
  -d '{"external_player_id":"player-1001","amount":"500.0000","currency":"INR"}'
```

### Debit a wallet

```bash
curl -X POST http://127.0.0.1:8000/api/v1/transactions/debit \
  -H "X-Client-API-Key: YOUR_CLIENT_API_KEY" \
  -H "Idempotency-Key: demo-debit-001" \
  -H "Content-Type: application/json" \
  -d '{"external_player_id":"player-1001","amount":"125.5000","currency":"INR"}'
```

### Get balance

```bash
curl "http://127.0.0.1:8000/api/v1/wallets/player-1001/balance?currency=INR" \
  -H "X-Client-API-Key: YOUR_CLIENT_API_KEY"
```

Additional endpoints: `POST /api/v1/transactions/refund`, `/rollback` and `/adjustment`; `GET /api/v1/transactions/{external_player_id}/history?currency=INR` returns paginated wallet history.

## Asynchronous event processing

Every successful wallet operation inserts a `wallet.transaction.completed` event into `outbox_events` in the same MySQL transaction as the wallet update, transaction row, ledger entry and idempotency response. The publisher sends committed outbox rows to the durable `wallet.events` topic exchange and marks them published only after a publisher confirm. Failed publishes are rescheduled with exponential backoff. The consumer queue has a dead-letter queue for invalid or failed messages.

Run the publisher and example consumer in separate terminals:

```bash
uv run python -m scripts.run_outbox_publisher
uv run python -m scripts.run_wallet_event_consumer
```

Delivery is **at least once**, not exactly once. A crash after RabbitMQ confirms a message but before the database records `PUBLISHED` can cause a duplicate delivery. The example consumer uses `processed_messages` to deduplicate by `(consumer_name, message_uuid)`. Any real consumer side effect must be committed in the same database transaction as its inbox record, or use an idempotency mechanism in the downstream system.

## Optional Redis coordination

Redis is optional. Without `REDIS_URL`, the service relies on MySQL/InnoDB row locks and unique constraints. To enable the additional distributed lock:

```bash
uv pip install -r requirements-redis.txt
```

Set `REDIS_URL=redis://127.0.0.1:6379/0` in `.env` and restart the API. If Redis is configured but unavailable, new wallet operations fail with HTTP 503 rather than silently bypassing the configured lock. Replays of already-recorded idempotency keys can still be served from MySQL. The Redis lock has a finite TTL; database row locking remains the final correctness guard.

## Provider catalog and adapter framework

Provider base URLs are stored in the provider catalog; API keys are read from environment variables named `PROVIDER_<CODE>_API_KEY` and are never stored in MySQL. Register a provider and a game:

```bash
uv run python -m scripts.register_provider --code DEMO --name "Demo Provider" --base-url https://provider.example.com
uv run python -m scripts.register_game --provider-code DEMO --external-id slot-001 --name "Demo Slot"
```

Debit/credit requests may include both `provider_code` and `game_external_id`; the service validates the active catalog entries and links the transaction to the internal game row. Example optional request fields are `"provider_code":"DEMO"` and `"game_external_id":"slot-001"`. The generic `HTTPProviderAdapter` provides HTTPS enforcement, timeout handling, API-key headers, provider idempotency headers and normalized transport errors. It is an adapter foundation, not a ready-made integration with a specific commercial provider. Concrete request/response mapping and callback signature verification must be implemented against that provider's official API specification.

## Tests

Install pytest in the active uv environment if it is not already installed:

```bash
uv pip install pytest
```

Run:

```bash
python -m pytest -q
```

The automated tests use SQLite to exercise service, HTTP, outbox and adapter behavior without requiring MySQL or RabbitMQ. SQLite does not reproduce InnoDB locking semantics. An optional MySQL concurrency test is included; set `MYSQL_TEST_DATABASE_URL` to a disposable database with migrations already applied, then run `python -m pytest tests/integration -q`. The MySQL test verifies that concurrent debits cannot overdraw the same wallet. Run the outbox publisher and consumer against a real RabbitMQ instance before relying on message delivery.

## Roadmap

- [ ] Verify migrations against a clean MySQL database and an existing development database
- [ ] Add MySQL integration and concurrent debit tests
- [x] Add provider/game identity to transaction requests and a generic HTTP adapter framework
- [x] Add RabbitMQ publisher/consumer workflows with durable queues and retry policy
- [x] Add transactional outbox to avoid database/message dual-write inconsistency
- [x] Add optional Redis lock coordination with bounded TTL and ownership-safe release
- [ ] Add vendor-specific callback authentication, reconciliation and recovery workflows
- [ ] Add operational logging, metrics and tracing
- [ ] Add load tests and publish measured results only

## Engineering documentation

- [System architecture](docs/architecture.md)
- [Transaction lifecycle and idempotency](docs/transaction-lifecycle.md)
- [Transactional outbox and messaging](docs/messaging.md)
- [Provider adapter design](docs/provider-adapters.md)
- [Known limitations and verification status](docs/known-limitations.md)
- [Transaction flow diagram](diagrams/transaction-flow.md)
- [Outbox flow diagram](diagrams/outbox-flow.md)

## Author

**Soumajit Sarkar** — Python Backend Engineer

GitHub: https://github.com/soumajit-sarkar
