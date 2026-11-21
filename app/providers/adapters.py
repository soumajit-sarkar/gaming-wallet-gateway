import os
from typing import Any
from urllib.parse import urlparse

import httpx

from app.models.provider import Provider
from app.providers.errors import (
    ProviderConfigurationError,
    ProviderRejectedRequest,
    ProviderRequestError,
)


class HTTPProviderAdapter:
    """Generic outbound HTTP adapter; provider-specific payload mapping belongs in subclasses."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ProviderConfigurationError("Provider base URL must be an absolute HTTP(S) URL without embedded credentials or fragments.")
        if timeout_seconds <= 0:
            raise ProviderConfigurationError("Provider timeout must be greater than zero.")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ProviderConfigurationError("Non-local provider endpoints must use HTTPS.")
        if not api_key:
            raise ProviderConfigurationError("Provider API key is not configured.")

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def request(
        self,
        *,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if not path.startswith("/") or "://" in path:
            raise ProviderConfigurationError("Provider request path must be a relative absolute-path, not a URL.")
        headers = {"X-Provider-API-Key": self.api_key}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout_seconds),
                transport=self.transport,
            ) as client:
                response = client.request(
                    method,
                    path,
                    json=json_body,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderRequestError("Provider request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderRejectedRequest(
                f"Provider returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderRequestError("Provider could not be reached.") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderRequestError("Provider returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise ProviderRequestError("Provider response must be a JSON object.")
        return data


class ProviderAdapterRegistry:
    """Builds provider adapters from non-secret DB configuration and environment secrets."""

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds

    def get(self, provider: Provider) -> HTTPProviderAdapter:
        if not provider.base_url:
            raise ProviderConfigurationError(
                f"Provider {provider.code} has no base URL configured."
            )
        normalized_code = provider.code.upper().replace("-", "_")
        env_name = f"PROVIDER_{normalized_code}_API_KEY"
        api_key = os.getenv(env_name)
        if not api_key:
            raise ProviderConfigurationError(
                f"Provider API key is not configured in {env_name}."
            )
        return HTTPProviderAdapter(
            base_url=provider.base_url,
            api_key=api_key,
            timeout_seconds=self.timeout_seconds,
        )
