from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


def test_debit_api_requires_client_auth_and_idempotency(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        unauthenticated = client.post(
            "/api/v1/transactions/debit",
            headers={"Idempotency-Key": "api-debit-unauth"},
            json={
                "external_player_id": "player-001",
                "amount": "10.0000",
                "currency": "INR",
            },
        )
        assert unauthenticated.status_code == 401

        response = client.post(
            "/api/v1/transactions/debit",
            headers={
                "X-Client-API-Key": "test-client-secret",
                "Idempotency-Key": "api-debit-001",
            },
            json={
                "external_player_id": "player-001",
                "amount": "10.0000",
                "currency": "inr",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["type"] == "DEBIT"
        assert response.json()["balance_after"] == "990.0000"
    finally:
        app.dependency_overrides.clear()


def test_player_wallet_creation_and_balance_api(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    headers = {"X-Client-API-Key": "test-client-secret"}
    try:
        player_response = client.post(
            "/api/v1/players",
            headers=headers,
            json={"external_id": "new-player-42", "username": "new-player"},
        )
        assert player_response.status_code == 201, player_response.text

        wallet_response = client.post(
            "/api/v1/wallets",
            headers=headers,
            json={"external_player_id": "new-player-42", "currency": "inr"},
        )
        assert wallet_response.status_code == 201, wallet_response.text
        assert wallet_response.json()["currency"] == "INR"
        assert wallet_response.json()["balance"] == "0.0000"

        balance_response = client.get(
            "/api/v1/wallets/new-player-42/balance?currency=INR",
            headers=headers,
        )
        assert balance_response.status_code == 200, balance_response.text
        assert balance_response.json()["balance"] == "0.0000"
    finally:
        app.dependency_overrides.clear()


def test_transaction_history_api_returns_client_scoped_records(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    headers = {
        "X-Client-API-Key": "test-client-secret",
        "Idempotency-Key": "history-seed-debit",
    }
    try:
        debit_response = client.post(
            "/api/v1/transactions/debit",
            headers=headers,
            json={
                "external_player_id": "player-001",
                "amount": "5.0000",
                "currency": "INR",
            },
        )
        assert debit_response.status_code == 200, debit_response.text

        history_response = client.get(
            "/api/v1/transactions/player-001/history?currency=INR",
            headers={"X-Client-API-Key": "test-client-secret"},
        )
        assert history_response.status_code == 200, history_response.text
        body = history_response.json()
        assert body["total"] == 1
        assert body["items"][0]["type"] == "DEBIT"
    finally:
        app.dependency_overrides.clear()
