# Gaming Wallet Gateway

A high-throughput backend gateway for gaming platforms that coordinates wallet transactions, game-provider integrations, asynchronous messaging, concurrency control, and transaction recovery.

**Public reference architecture:** Python · FastAPI · RabbitMQ · Redis · MySQL · SQLAlchemy · MongoDB · HTTPX

---

## Overview

Gaming platforms often need to integrate with multiple external game providers while maintaining a consistent wallet and transaction experience for players.

The gateway acts as an integration boundary between client platforms, wallet operations, asynchronous processing, and external gaming providers.

The architecture focuses on several core backend engineering requirements:

- High-throughput API processing
- Reliable wallet transactions
- Concurrent transaction handling
- Idempotent operations
- Asynchronous messaging
- Multiple provider integrations
- Failure recovery
- Transaction traceability
- Operational logging
- Rate limiting

This repository presents a FastAPI reference architecture based on my experience participating in the design and development of production gaming-wallet backend systems.

The public implementation is intentionally sanitized and does not contain proprietary source code, production credentials, customer data, private endpoints, provider secrets, or confidential infrastructure details.

---

# Production Experience

The architecture represented by this project is based on a production gaming-wallet system that operated at approximately:

| Metric | Production Scale |
|---|---:|
| Request throughput | **1,000–1,500 RPS** |
| Monthly transactions | **1M+** |
| Game-provider integrations | **60+** |
| Client platforms | **70+** |
| Games | **Thousands** |

> These figures describe the production system experience behind the architecture. They are not benchmarks of this public reference implementation.

---

# Architecture

The gateway separates synchronous API handling from asynchronous processing and provider-specific integrations.

```text
                         Client Platforms
                                |
                                v
                     +----------------------+
                     |    FastAPI Gateway   |
                     |----------------------|
                     | Routing              |
                     | Validation           |
                     | Request Context      |
                     | Authentication       |
                     | Error Handling       |
                     | Rate Limiting        |
                     +----------+-----------+
                                |
                                v
                     +----------------------+
                     |    Service Layer     |
                     |----------------------|
                     | Wallet Service       |
                     | Game Service         |
                     | Transaction Service  |
                     +----+------------+----+
                          |            |
                +---------+            +----------+
                |                                  |
                v                                  v
        +---------------+                  +---------------+
        |     Redis     |                  |   RabbitMQ    |
        |---------------|                  |---------------|
        | Distributed   |                  | Commands      |
        | Locks         |                  | Events        |
        | Idempotency   |                  | Async Work    |
        | Rate Limiting |                  | Retry Flow    |
        +---------------+                  +-------+-------+
                                                   |
                                                   v
                                          +-------------------+
                                          |     Consumers     |
                                          +---------+---------+
                                                    |
                                                    v
                                          +-------------------+
                                          | Provider Adapters |
                                          +---------+---------+
                                                    |
                           +----------------+--------+----------------+
                           |                |                         |
                           v                v                         v
                    +-----------+    +-----------+             +-----------+
                    | Provider A|    | Provider B|             | Provider C|
                    +-----------+    +-----------+             +-----------+

                          +-------------------+
                          |       MySQL       |
                          |-------------------|
                          | Players           |
                          | Wallets           |
                          | Games             |
                          | Transactions      |
                          +---------+---------+
                                    ^
                                    |
                         Services / Consumers


                          +-------------------+
                          |      MongoDB      |
                          |-------------------|
                          | Application Logs  |
                          | Audit Logs        |
                          | Error Logs        |
                          | Access Logs       |
                          +---------^---------+
                                    |
                           Application / Consumers
```

---

# Core Components

## FastAPI Gateway

The API gateway is responsible for handling synchronous client requests and providing a controlled entry point into the backend system.

Responsibilities include:

- Request routing
- Request validation
- Authentication-related processing
- Request context management
- Correlation ID propagation
- Rate limiting
- Error handling
- Delegation to backend services

---

## Service Layer

The service layer contains application-level business orchestration and separates API concerns from transaction and integration logic.

Typical responsibilities include:

- Wallet operations
- Game operations
- Transaction processing
- Provider orchestration
- Validation of business workflows
- Coordination between persistence, messaging, and external integrations

---

## Redis

Redis is used for low-latency coordination and state management.

Key responsibilities include:

- Distributed locking
- Idempotency control
- Rate limiting
- Short-lived coordination state
- Concurrency control

Distributed locks help prevent conflicting operations against the same wallet or transaction context when multiple requests are processed concurrently.

---

## RabbitMQ

RabbitMQ provides asynchronous communication between the gateway and background consumers.

It is used for:

- Commands
- Events
- Asynchronous processing
- Retry workflows
- Decoupling API processing from provider operations

This allows long-running or failure-prone operations to be processed independently from the synchronous API request lifecycle.

---

## Consumers

Consumers process asynchronous messages from RabbitMQ.

Depending on the workflow, consumers can be responsible for:

- Authentication-related processing
- Game-launch operations
- Wallet-related processing
- Provider communication
- Transaction recovery
- Retry handling

The consumer layer keeps asynchronous processing isolated from the API layer.

---

## Provider Adapters

Provider adapters isolate external game-provider APIs from the internal application architecture.

The adapter approach allows different providers to expose different:

- Authentication mechanisms
- Request formats
- Response formats
- Transaction workflows
- Error models
- API endpoints

while maintaining a consistent internal interface.

---

## MySQL

MySQL is the primary relational data store for transactional and business data.

Typical data includes:

- Players
- Wallets
- Games
- Transactions

Transactional consistency is particularly important for wallet operations because balance-changing operations must be handled safely under concurrent requests and partial failures.

---

## MongoDB

MongoDB is used for operational and audit-oriented logging.

Typical log categories include:

- Application logs
- Audit logs
- Error logs
- Access logs

Separating operational logs from transactional data helps keep the transactional database focused on business-critical workloads.

---

# Transaction Flow

A simplified wallet transaction flow looks like this:

```text
Client
  |
  v
FastAPI Gateway
  |
  v
Request Validation
  |
  v
Idempotency Check
  |
  v
Concurrency Control
  |
  v
Transaction Service
  |
  +--------------------+
  |                    |
  v                    v
MySQL               RabbitMQ
  |                    |
  |                    v
  |                Consumer
  |                    |
  |                    v
  |              Provider Adapter
  |                    |
  |                    v
  |              External Provider
  |                    |
  +---------+----------+
            |
            v
       Transaction State
            |
            v
          Result
```

The exact workflow can vary depending on the transaction type and provider integration.

---

# Reliability Considerations

Wallet and transaction systems must account for failures that can occur at multiple points in the request lifecycle.

The architecture therefore considers:

- Idempotent transaction handling
- Distributed concurrency control
- Retry-safe operations
- Transaction state tracking
- Asynchronous processing
- Provider failure handling
- Recovery workflows
- Correlation IDs
- Operational logging
- Failure traceability

The goal is to prevent duplicate wallet operations and maintain a traceable transaction state even when external dependencies fail.

---

# Concurrency Control

Wallet operations can be affected by concurrent requests targeting the same player or wallet.

For example:

```text
Request A ---> Wallet X
                    |
                    | Lock
                    v
              Process Operation
                    |
                    v
                  Unlock


Request B ---> Wallet X
                    |
                    | Wait / Retry
                    v
              Process After A
```

Redis-based distributed locking can be used to coordinate access when multiple application instances process requests concurrently.

The locking strategy must also consider:

- Lock expiration
- Ownership
- Failure during processing
- Retry behavior
- Avoiding unnecessary lock contention

---

# Idempotency

Financial and wallet-related operations must be protected against duplicate processing.

A repeated request with the same idempotency or transaction identifier should not result in multiple balance changes.

A simplified flow is:

```text
Incoming Request
       |
       v
Idempotency Key
       |
       v
Already Processed?
    /        \
  Yes         No
   |           |
   v           v
Return      Process
Existing       |
Result         v
            Store State
               |
               v
          Return Result
```

Idempotency is particularly important when clients retry requests because of network failures or timeouts.

---

# Failure Recovery

External provider communication can fail for several reasons:

- Network timeout
- Provider unavailable
- Connection failure
- Invalid provider response
- Temporary service failure
- Consumer failure

The architecture uses asynchronous processing, transaction state tracking, retry workflows, and recovery mechanisms to handle these situations.

The objective is to ensure that a temporary failure does not automatically result in an inconsistent wallet state.

---

# Observability

Transaction-heavy systems require traceability across multiple services and asynchronous boundaries.

The architecture uses correlation identifiers to connect related operations across:

```text
Client Request
      |
      v
FastAPI Gateway
      |
      v
Service Layer
      |
      v
RabbitMQ Message
      |
      v
Consumer
      |
      v
Provider Adapter
      |
      v
External Provider
```

Operational logs can then be correlated using the same request or transaction context.

---

# Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend development |
| FastAPI | API gateway and REST services |
| RabbitMQ | Asynchronous messaging |
| Redis | Distributed coordination, locking, idempotency and rate limiting |
| MySQL | Transactional and business data |
| SQLAlchemy | Database access |
| MongoDB | Operational and audit logging |
| HTTPX | External HTTP integrations |

---

# Public Reference Implementation

This repository is intended to demonstrate the engineering concepts and architecture behind a production-oriented gaming wallet gateway.

The public implementation is designed to remain independent from the original production system.

It will use:

- Generic provider interfaces
- Sanitized domain models
- Generic configuration
- Example transaction workflows
- Public-safe infrastructure definitions
- No production credentials
- No proprietary endpoints
- No customer information
- No company-specific business rules

The purpose is to demonstrate backend engineering decisions rather than reproduce proprietary production code.

---

# Current Project Status

The project is being developed incrementally.

Current focus:

- [x] System architecture defined
- [x] Core component responsibilities defined
- [x] Production-scale context documented
- [x] Public-safe architecture defined
- [ ] FastAPI implementation
- [ ] Database models
- [ ] Redis integration
- [ ] RabbitMQ integration
- [ ] Provider adapter implementation
- [ ] Transaction workflow
- [ ] Idempotency handling
- [ ] Distributed locking
- [ ] Retry and recovery workflows
- [ ] Automated tests
- [ ] Architecture documentation
- [ ] Production-oriented observability

---

# Disclaimer

This repository is an independently developed public reference implementation based on professional experience with production gaming-wallet backend systems.

It does not reproduce proprietary source code or confidential production infrastructure.

Production metrics presented in this README describe the scale of the production system that informed the architectural design and are not performance benchmarks of this repository.

---

# Author

**Soumajit Sarkar**

Senior Python Backend Engineer

Backend engineering focus:

- Python
- FastAPI
- Django
- Django REST Framework
- REST APIs
- Transaction processing
- Distributed systems
- Database engineering
- Asynchronous processing
- Third-party integrations
- Reliability engineering