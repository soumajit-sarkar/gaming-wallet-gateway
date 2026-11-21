import hashlib
import json
from contextlib import nullcontext
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.idempotency_record import IdempotencyRecord
from app.models.outbox_event import OutboxEvent
from app.models.transaction import Transaction
from app.models.wallet_ledger import WalletLedger
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.player_repository import PlayerRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.wallet_ledger_repository import WalletLedgerRepository
from app.repositories.wallet_repository import WalletRepository
from app.services.provider_service import ProviderCatalogService
from app.services.errors import (
    BusinessRuleError,
    IdempotencyConflictError,
    InsufficientBalanceError,
    InvalidTransactionError,
    ResourceNotFoundError,
    WalletServiceError,
)


def utcnow_naive() -> datetime:
    """Return UTC as a naive datetime for MySQL DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class TransactionService:
    """Coordinates an atomic wallet transaction.

    `client_id` must come from a trusted authentication layer. Never accept it
    from an untrusted request body or query parameter.

    The service owns commit/rollback for the current Session transaction. This
    also supports an authentication dependency that has already queried Client.
    """

    def __init__(self, db: Session, lock_manager: Any | None = None) -> None:
        self.db = db
        self.lock_manager = lock_manager
        self.players = PlayerRepository(db)
        self.provider_catalog = ProviderCatalogService(db)
        self.wallets = WalletRepository(db)
        self.transactions = TransactionRepository(db)
        self.ledger = WalletLedgerRepository(db)
        self.idempotency = IdempotencyRepository(db)

    def debit(
        self, *, client_id: int, idempotency_key: str, external_player_id: str,
        amount: Decimal, currency: str, provider_reference: str | None = None,
        provider_code: str | None = None, game_external_id: str | None = None,
    ) -> dict[str, Any]:
        return self._execute(
            client_id=client_id,
            idempotency_key=idempotency_key,
            operation="DEBIT",
            payload={
                "external_player_id": external_player_id,
                "amount": amount,
                "currency": currency,
                "provider_reference": provider_reference,
                "provider_code": provider_code,
                "game_external_id": game_external_id,
            },
        )

    def credit(
        self, *, client_id: int, idempotency_key: str, external_player_id: str,
        amount: Decimal, currency: str, provider_reference: str | None = None,
        provider_code: str | None = None, game_external_id: str | None = None,
    ) -> dict[str, Any]:
        return self._execute(
            client_id=client_id,
            idempotency_key=idempotency_key,
            operation="CREDIT",
            payload={
                "external_player_id": external_player_id,
                "amount": amount,
                "currency": currency,
                "provider_reference": provider_reference,
                "provider_code": provider_code,
                "game_external_id": game_external_id,
            },
        )

    def refund(
        self, *, client_id: int, idempotency_key: str, external_player_id: str,
        original_transaction_uuid: str, amount: Decimal, currency: str,
        provider_reference: str | None = None,
    ) -> dict[str, Any]:
        return self._execute(
            client_id=client_id,
            idempotency_key=idempotency_key,
            operation="REFUND",
            payload={
                "external_player_id": external_player_id,
                "original_transaction_uuid": str(original_transaction_uuid),
                "amount": amount,
                "currency": currency,
                "provider_reference": provider_reference,
            },
        )

    def rollback(
        self, *, client_id: int, idempotency_key: str, external_player_id: str,
        original_transaction_uuid: str, currency: str,
        provider_reference: str | None = None,
    ) -> dict[str, Any]:
        return self._execute(
            client_id=client_id,
            idempotency_key=idempotency_key,
            operation="ROLLBACK",
            payload={
                "external_player_id": external_player_id,
                "original_transaction_uuid": str(original_transaction_uuid),
                "currency": currency,
                "provider_reference": provider_reference,
            },
        )

    def adjust(
        self, *, client_id: int, idempotency_key: str, external_player_id: str,
        amount: Decimal, currency: str, direction: str, reason: str,
    ) -> dict[str, Any]:
        return self._execute(
            client_id=client_id,
            idempotency_key=idempotency_key,
            operation="ADJUSTMENT",
            payload={
                "external_player_id": external_player_id,
                "amount": amount,
                "currency": currency,
                "direction": direction,
                "reason": reason,
            },
        )

    def get_history(
        self,
        *,
        client_id: int,
        external_player_id: str,
        currency: str,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        if offset < 0 or not 1 <= limit <= 100:
            raise InvalidTransactionError(
                "History offset must be non-negative and limit must be between 1 and 100."
            )
        player = self.players.get_by_client_and_external_id(
            client_id, external_player_id
        )
        if player is None:
            raise ResourceNotFoundError("Player was not found for this client.")
        wallet = self.wallets.get_by_player_id_and_currency(player.id, currency)
        if wallet is None:
            raise ResourceNotFoundError("Wallet was not found.")
        transactions, total = self.transactions.get_by_wallet(
            wallet.id, offset=offset, limit=limit
        )
        return {
            "items": [
                {
                    "transaction_uuid": item.transaction_uuid,
                    "type": item.type,
                    "amount": item.amount,
                    "status": item.status,
                    "provider_reference": item.provider_reference,
                    "created_at": item.created_at,
                }
                for item in transactions
            ],
            "total": total,
        }

    def _execute(
        self, *, client_id: int, idempotency_key: str, operation: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if self.lock_manager is None:
            lock_context = nullcontext()
        else:
            # A retry of an already-recorded request can be replayed without
            # Redis. MySQL idempotency and row constraints remain authoritative.
            existing = self.idempotency.get_by_client_and_key(
                client_id, idempotency_key
            )
            if existing is not None:
                return self._execute_atomic(
                    client_id=client_id,
                    idempotency_key=idempotency_key,
                    operation=operation,
                    payload=payload,
                )
            lock_context = self.lock_manager.wallet_lock(
                client_id=client_id,
                external_player_id=payload["external_player_id"],
                currency=str(payload["currency"]),
            )
        with lock_context:
            return self._execute_atomic(
                client_id=client_id,
                idempotency_key=idempotency_key,
                operation=operation,
                payload=payload,
            )

    def _execute_atomic(
        self, *, client_id: int, idempotency_key: str, operation: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 150:
            raise InvalidTransactionError("A valid Idempotency-Key header is required.")
        if client_id <= 0:
            raise InvalidTransactionError("A valid authenticated client is required.")

        normalized_payload = {
            key: _json_value(value) if value is not None else None
            for key, value in payload.items()
        }
        normalized_payload["currency"] = str(payload["currency"]).strip().upper()
        if normalized_payload.get("provider_code"):
            normalized_payload["provider_code"] = str(
                normalized_payload["provider_code"]
            ).strip().upper()
        if normalized_payload.get("direction"):
            normalized_payload["direction"] = str(
                normalized_payload["direction"]
            ).strip().upper()
        request_hash = hashlib.sha256(
            json.dumps(
                {"operation": operation, "payload": normalized_payload},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        deferred_error: WalletServiceError | None = None
        result: dict[str, Any] | None = None

        try:
            # Authentication dependencies may already have opened an implicit
            # read transaction on this Session. The service owns and commits
            # that unit of work rather than calling Session.begin() again.
            # Do not gap-lock a missing idempotency key. The unique
            # (client_id, idempotency_key) constraint arbitrates concurrent inserts.
            existing = self.idempotency.get_by_client_and_key(
                client_id, idempotency_key
            )
            if existing is not None:
                replay = self._replay(existing, request_hash)
                self.db.commit()
                return replay

            now = utcnow_naive()
            record = IdempotencyRecord(
                client_id=client_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                status="PROCESSING",
                created_at=now,
                updated_at=now,
            )
            self.idempotency.create(record)

            try:
                result = self._apply_operation(
                    client_id=client_id,
                    operation=operation,
                    payload=payload,
                )
                record.status = "COMPLETED"
                record.response_data = result
                record.updated_at = utcnow_naive()
                self.db.flush()
            except WalletServiceError as exc:
                error_data = {
                    "error": {"code": exc.code, "message": exc.message},
                    "http_status": exc.http_status,
                }
                record.status = "FAILED"
                record.response_data = error_data
                record.updated_at = utcnow_naive()
                self.db.flush()
                deferred_error = exc

            # The idempotency record, transaction, wallet balance and ledger
            # posting are committed atomically.
            self.db.commit()
        except IntegrityError:
            # A concurrent request may have inserted the same client/key after
            # our initial SELECT. Roll back before reading the committed winner.
            self.db.rollback()
            existing = self.idempotency.get_by_client_and_key(
                client_id, idempotency_key
            )
            if existing is None:
                raise
            try:
                replay = self._replay(existing, request_hash)
                self.db.commit()
                return replay
            except Exception:
                self.db.rollback()
                raise
        except Exception:
            self.db.rollback()
            raise

        if deferred_error is not None:
            raise deferred_error
        if result is None:
            raise RuntimeError("Transaction completed without a result.")
        return result

    def _replay(
        self, record: IdempotencyRecord, request_hash: str
    ) -> dict[str, Any]:
        if record.request_hash != request_hash:
            raise IdempotencyConflictError(
                "This Idempotency-Key was already used with a different request."
            )
        if record.status == "COMPLETED" and record.response_data is not None:
            return record.response_data
        if record.status == "FAILED" and record.response_data is not None:
            error = record.response_data.get("error", {})
            status = int(record.response_data.get("http_status", 409))
            error_types = {
                "BUSINESS_RULE_VIOLATION": BusinessRuleError,
                "INSUFFICIENT_BALANCE": InsufficientBalanceError,
                "INVALID_TRANSACTION": InvalidTransactionError,
                "RESOURCE_NOT_FOUND": ResourceNotFoundError,
                "IDEMPOTENCY_CONFLICT": IdempotencyConflictError,
            }
            error_code = error.get("code", "PREVIOUS_REQUEST_FAILED")
            error_type = error_types.get(error_code, WalletServiceError)
            exc = error_type(error.get("message", "Previous request failed."))
            exc.code = error_code
            exc.http_status = status
            raise exc
        raise BusinessRuleError("An operation with this Idempotency-Key is still processing.")

    def _apply_operation(
        self, *, client_id: int, operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        amount = payload.get("amount")
        if amount is not None:
            if isinstance(amount, float):
                raise InvalidTransactionError("Floating-point amounts are not accepted.")
            amount = amount if isinstance(amount, Decimal) else Decimal(str(amount))
            if (
                not amount.is_finite()
                or amount <= 0
                or amount.as_tuple().exponent < -4
                or amount.adjusted() > 15
                or len(amount.as_tuple().digits) > 20
            ):
                raise InvalidTransactionError(
                    "Amount must fit NUMERIC(20, 4), be positive, and use at most four decimal places."
                )
            amount = amount.quantize(Decimal("0.0001"))

        currency = str(payload["currency"]).strip().upper()
        player = self.players.get_by_client_and_external_id_for_update(
            client_id, payload["external_player_id"]
        )
        if player is None:
            raise ResourceNotFoundError("Player was not found for this client.")
        if player.status != "ACTIVE":
            raise BusinessRuleError("Player is not active.")

        wallet = self.wallets.get_by_player_id_and_currency_for_update(
            player.id, currency
        )
        if wallet is None:
            raise ResourceNotFoundError("Wallet was not found for this player and currency.")
        if wallet.status != "ACTIVE":
            raise BusinessRuleError("Wallet is not active.")

        game_id: int | None = None
        provider_code = payload.get("provider_code")
        game_external_id = payload.get("game_external_id")
        if bool(provider_code) != bool(game_external_id):
            raise InvalidTransactionError(
                "provider_code and game_external_id must be supplied together."
            )
        if provider_code and game_external_id:
            _provider, game = self.provider_catalog.get_active_game(
                provider_code, game_external_id
            )
            game_id = game.id

        parent: Transaction | None = None
        parent_id: int | None = None
        if operation in {"REFUND", "ROLLBACK"}:
            parent = self.transactions.get_by_uuid_for_update(
                payload["original_transaction_uuid"]
            )
            if parent is None or parent.client_id != client_id:
                raise ResourceNotFoundError("Original transaction was not found.")
            if parent.wallet_id != wallet.id:
                raise InvalidTransactionError(
                    "Original transaction does not belong to the specified player wallet."
                )
            if parent.status != "SUCCESS":
                raise BusinessRuleError("Only successful transactions can be reversed.")
            if parent.type not in {"DEBIT", "CREDIT"}:
                raise BusinessRuleError("Only original debit or credit transactions can be reversed.")
            if operation == "REFUND" and parent.type != "DEBIT":
                raise BusinessRuleError("Refund is only valid for debit transactions; use rollback for credits.")
            parent_id = parent.id

        reversed_amount = (
            self.transactions.get_reversed_amount(parent.id) if parent else Decimal("0")
        )
        if operation == "REFUND":
            remaining = parent.amount - reversed_amount
            if remaining <= 0:
                raise BusinessRuleError("The original transaction has already been fully reversed.")
            if amount > remaining:
                raise BusinessRuleError("Refund amount exceeds the remaining refundable amount.")
        elif operation == "ROLLBACK":
            if reversed_amount > 0:
                raise BusinessRuleError("The original transaction has already been partially or fully reversed.")
            amount = parent.amount

        if operation == "ADJUSTMENT":
            direction = str(payload["direction"]).upper()
            if direction not in {"DEBIT", "CREDIT"}:
                raise InvalidTransactionError("Adjustment direction must be DEBIT or CREDIT.")
            ledger_direction = direction
            transaction_type = "ADJUSTMENT"
        elif operation in {"DEBIT", "REFUND"}:
            ledger_direction = "DEBIT" if operation == "DEBIT" else "CREDIT"
            transaction_type = operation
        elif operation == "ROLLBACK":
            ledger_direction = "CREDIT" if parent.type == "DEBIT" else "DEBIT"
            transaction_type = "ROLLBACK"
        else:
            ledger_direction = "CREDIT"
            transaction_type = "CREDIT"

        balance_before = Decimal(wallet.balance)
        if ledger_direction == "DEBIT":
            if balance_before < amount:
                raise InsufficientBalanceError("Wallet balance is insufficient.")
            balance_after = balance_before - amount
        else:
            balance_after = balance_before + amount

        if balance_after > Decimal("9999999999999999.9999"):
            raise InvalidTransactionError("Resulting balance exceeds NUMERIC(20, 4).")

        now = utcnow_naive()
        transaction = Transaction(
            client_id=client_id,
            wallet_id=wallet.id,
            game_id=parent.game_id if parent is not None else game_id,
            parent_transaction_id=parent_id,
            transaction_uuid=str(uuid4()),
            type=transaction_type,
            amount=amount,
            status="SUCCESS",
            provider_reference=payload.get("provider_reference"),
            reason=payload.get("reason"),
            created_at=now,
            updated_at=now,
        )
        self.transactions.create(transaction)

        wallet.balance = balance_after
        wallet.updated_at = now
        self.db.flush()

        self.ledger.create(
            WalletLedger(
                wallet_id=wallet.id,
                transaction_id=transaction.id,
                entry_type=ledger_direction,
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                created_at=now,
            )
        )

        event_uuid = str(uuid4())
        self.db.add(
            OutboxEvent(
                event_uuid=event_uuid,
                event_type="wallet.transaction.completed",
                aggregate_type="wallet_transaction",
                aggregate_id=transaction.id,
                payload={
                    "event_uuid": event_uuid,
                    "event_type": "wallet.transaction.completed",
                    "transaction_uuid": transaction.transaction_uuid,
                    "client_id": client_id,
                    "player_id": player.id,
                    "wallet_id": wallet.id,
                    "transaction_type": transaction.type,
                    "amount": format(amount, "f"),
                    "currency": wallet.currency,
                    "balance_before": format(balance_before, "f"),
                    "balance_after": format(balance_after, "f"),
                    "provider_reference": transaction.provider_reference,
                    "game_id": transaction.game_id,
                    "occurred_at": now.isoformat(),
                },
                status="PENDING",
                attempts=0,
                available_at=now,
                locked_until=None,
                published_at=None,
                last_error=None,
                created_at=now,
                updated_at=now,
            )
        )
        self.db.flush()

        return {
            "transaction_uuid": transaction.transaction_uuid,
            "type": transaction.type,
            "amount": format(amount, "f"),
            "currency": wallet.currency,
            "status": transaction.status,
            "wallet_id": wallet.id,
            "provider_reference": transaction.provider_reference,
            "balance_before": format(balance_before, "f"),
            "balance_after": format(balance_after, "f"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
