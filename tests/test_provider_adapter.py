import httpx
import pytest

from app.models.provider import Provider
from app.providers.adapters import HTTPProviderAdapter, ProviderAdapterRegistry
from app.providers.errors import (
    ProviderConfigurationError,
    ProviderRejectedRequest,
    ProviderRequestError,
)


def test_http_provider_adapter_sends_auth_and_idempotency_headers():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers.get("X-Provider-API-Key")
        captured["idempotency"] = request.headers.get("Idempotency-Key")
        return httpx.Response(200, json={"accepted": True})

    adapter = HTTPProviderAdapter(
        base_url="https://provider.example.test",
        api_key="provider-secret",
        transport=httpx.MockTransport(handler),
    )
    response = adapter.request(
        method="POST",
        path="/v1/bets",
        json_body={"amount": "10.0000"},
        idempotency_key="provider-operation-1",
    )

    assert response == {"accepted": True}
    assert captured["url"] == "https://provider.example.test/v1/bets"
    assert captured["api_key"] == "provider-secret"
    assert captured["idempotency"] == "provider-operation-1"


def test_http_provider_adapter_rejects_non_https_remote_url():
    with pytest.raises(ProviderConfigurationError):
        HTTPProviderAdapter(base_url="http://provider.example.test", api_key="secret")


def test_http_provider_adapter_maps_timeout_without_leaking_provider_details():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive provider internals")

    adapter = HTTPProviderAdapter(
        base_url="https://provider.example.test",
        api_key="secret",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderRequestError, match="timed out"):
        adapter.request(method="GET", path="/health")


def test_http_provider_adapter_maps_provider_http_error():
    adapter = HTTPProviderAdapter(
        base_url="https://provider.example.test",
        api_key="secret",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(503, json={"internal": "not exposed"})
        ),
    )
    with pytest.raises(ProviderRejectedRequest, match="HTTP 503"):
        adapter.request(method="GET", path="/health")


def test_registry_reads_provider_secret_from_environment(monkeypatch):
    monkeypatch.setenv("PROVIDER_DEMO_API_KEY", "demo-secret")
    provider = Provider(
        code="DEMO",
        name="Demo Provider",
        base_url="https://provider.example.test",
        status="ACTIVE",
    )
    adapter = ProviderAdapterRegistry().get(provider)
    assert adapter.base_url == "https://provider.example.test"
    assert adapter.api_key == "demo-secret"
