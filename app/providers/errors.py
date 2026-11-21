class ProviderIntegrationError(Exception):
    """Base class for provider integration failures."""


class ProviderConfigurationError(ProviderIntegrationError):
    pass


class ProviderRequestError(ProviderIntegrationError):
    pass


class ProviderRejectedRequest(ProviderIntegrationError):
    pass
