# System Architecture

## Request path

1. A gaming client sends `X-Client-API-Key`.
2. FastAPI hashes the supplied key and resolves an active `Client` row.
3. The authenticated `client_id` scopes player lookup. The client ID is never accepted from the request body.
4. Pydantic validates the request, including currency and decimal amount constraints.
5. `TransactionService` checks the idempotency key and canonical request hash.
6. The service locks the player and wallet rows using `SELECT ... FOR UPDATE`.
7. It validates the requested operation and computes the new balance using `Decimal`.
8. It inserts a transaction and one ledger posting, updates the wallet, and inserts an outbox event.
9. The idempotency response and all financial records commit atomically.
10. A separate publisher forwards the committed outbox event to RabbitMQ.

## Components

| Component | Responsibility |
|---|---|
| API dependencies | Client API-key authentication and DB session lifecycle |
| Schemas | Input validation and response serialization |
| Services | Business rules and transaction boundaries |
| Repositories | SQL queries and row-locking reads; never commit |
| MySQL/InnoDB | Financial source of truth, constraints and transaction isolation |
| Redis lock manager | Optional cross-instance request coordination; not a correctness substitute |
| Transactional outbox | Durable record of events to publish after the financial commit |
| RabbitMQ publisher | Persistent message publishing with publisher confirms |
| Consumer inbox | Deduplication by consumer name and message UUID |
| Provider adapter | Generic outbound HTTP transport with provider secrets outside the DB |

## Tenant isolation

The client is resolved from its API key. Player reads use both `client_id` and `external_id`. The transaction service verifies that the wallet belongs to the resolved player. A transaction's client and wallet IDs are derived from those validated records, not request-supplied IDs.

## Locking strategy

The database is authoritative. A transaction locks the player row and then the wallet row. This intentionally serializes operations for one player, including operations against different currencies. It is conservative and can be optimized only after measured contention and a revised lock-order analysis.

When Redis is enabled, a token-owned expiring lock is acquired before the SQL unit of work. Release uses a Lua compare-and-delete script. Redis failure fails closed for new operations, while already-recorded idempotent requests can be replayed from MySQL. The InnoDB locks and unique constraints remain necessary because Redis leases can expire.
