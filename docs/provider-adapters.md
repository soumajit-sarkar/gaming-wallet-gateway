# Provider Adapter Design

## Catalog

`providers` stores the provider code, display name, status and non-secret base URL. `games` maps a provider's external game identifier to an internal game row.

Provider API keys are not stored in MySQL. They are read from environment variables using the naming convention `PROVIDER_<CODE>_API_KEY` (hyphens in codes become underscores).

## Generic HTTP transport

`HTTPProviderAdapter` provides:

- HTTPS enforcement for non-local endpoints;
- configurable request timeout;
- provider API-key header injection;
- optional idempotency-key forwarding;
- normalized timeout, transport and HTTP-status errors;
- no logging of provider credentials or response bodies.

It intentionally does not define a universal launch/bet/win payload. Provider APIs differ in authentication, signatures, request fields, response codes and rollback semantics. Implement a provider-specific subclass against that provider's official documentation rather than assuming a generic payload is correct.

## Transaction mapping

Debit/credit requests may include `provider_code` and `game_external_id` together. The transaction service verifies that both catalog records are active and stores the internal `game_id` on the transaction. Refund and rollback transactions inherit the original transaction's game association.

## Not included

No commercial provider's API, secret, callback signature algorithm or proprietary endpoint is included. Callback authentication and reconciliation are future work requiring the relevant provider specifications.
