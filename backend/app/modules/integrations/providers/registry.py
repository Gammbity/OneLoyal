from typing import Any

from app.core.errors import ValidationAppError
from app.modules.integrations.models import Integration
from app.modules.integrations.providers.base import ERPProvider
from app.modules.integrations.providers.fake import FakeProvider
from app.modules.integrations.providers.moysklad import MoySkladProvider

ProviderFactory = type[FakeProvider] | type[MoySkladProvider]


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ProviderFactory] = {}

    def register(self, provider_name: str, provider_cls: ProviderFactory) -> None:
        self._providers[provider_name] = provider_cls

    def supported_providers(self) -> set[str]:
        return set(self._providers)

    def create_provider(
        self,
        *,
        integration: Integration,
        credentials: dict[str, Any],
    ) -> ERPProvider:
        provider_cls = self._providers.get(integration.provider)
        if provider_cls is None:
            raise ValidationAppError(
                "Unsupported integration provider.",
                details={"provider": integration.provider},
            )
        return provider_cls(
            integration=integration,
            credentials=credentials,
            settings=integration.settings_json or {},
        )


provider_registry = ProviderRegistry()
provider_registry.register(FakeProvider.provider_name, FakeProvider)
provider_registry.register(MoySkladProvider.provider_name, MoySkladProvider)
