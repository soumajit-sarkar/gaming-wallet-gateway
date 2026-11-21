# Known Limitations and Verification Status

This is a public reference implementation, not a production-certified wallet platform.

## Verified in this build environment

- Python compilation for application, scripts and tests.
- Service and API behavior using SQLite.
- Idempotency, debit/credit, partial refund, rollback, adjustment, ledger and outbox behavior in unit tests.
- Generic provider HTTP adapter behavior using HTTPX mock transports.
- Redis lock acquisition/release behavior using a fake Redis client.
- Alembic migration chain renders MySQL SQL in offline mode.
- `uv.lock` is consistent with `pyproject.toml`.

## Requires local integration verification

- Applying migrations to a clean MySQL database and to the current development database.
- MySQL/InnoDB concurrency tests. An optional integration test is provided under `tests/integration` and is skipped unless `MYSQL_TEST_DATABASE_URL` is set.
- RabbitMQ topology, publisher confirms, dead-letter routing and consumer acknowledgements against a running RabbitMQ server. Pika is declared in the project dependencies, but the broker integration was not run in this build environment.
- Redis behavior against a running Redis-compatible server. The lock logic was tested with a fake client; redis-py is an optional dependency in `requirements-redis.txt`.
- Real provider requests and callback signature verification. These require provider-specific API documentation and credentials.

## Not implemented

- MongoDB operational logging.
- Vendor-specific provider adapters, launch workflows and callbacks.
- Consumer retry queues, event replay console and operational dashboards.
- Load testing, performance benchmarks and horizontal scale validation.
- Automated secret rotation and client API-key management UI.

Do not claim throughput or production-readiness based on this repository without the corresponding benchmarks and integration evidence.
