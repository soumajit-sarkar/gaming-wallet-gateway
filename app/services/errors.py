class WalletServiceError(Exception):
    """Base class for expected wallet-domain failures."""

    code = "WALLET_ERROR"
    http_status = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ResourceNotFoundError(WalletServiceError):
    code = "RESOURCE_NOT_FOUND"
    http_status = 404


class BusinessRuleError(WalletServiceError):
    code = "BUSINESS_RULE_VIOLATION"
    http_status = 409


class InsufficientBalanceError(WalletServiceError):
    code = "INSUFFICIENT_BALANCE"
    http_status = 409


class IdempotencyConflictError(WalletServiceError):
    code = "IDEMPOTENCY_CONFLICT"
    http_status = 409


class InvalidTransactionError(WalletServiceError):
    code = "INVALID_TRANSACTION"
    http_status = 422


class ConcurrencyLockError(WalletServiceError):
    code = "CONCURRENCY_LOCK_UNAVAILABLE"
    http_status = 503
