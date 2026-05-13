import json
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.datetime import utc_now
from app.core.errors import NotFoundError, ValidationAppError
from app.core.security import decrypt_secret, encrypt_secret
from app.common.i18n import ensure_i18n_defaults
from app.modules.integrations.models import (
    Integration,
    IntegrationCredential,
    IntegrationProvider,
    IntegrationStatus,
)
from app.modules.integrations.providers.base import (
    ERPProvider,
    ProviderConnectionResult,
)
from app.modules.integrations.providers.registry import provider_registry
from app.modules.integrations.schemas import (
    IntegrationCreateRequest,
    IntegrationTranslationsUpdateRequest,
    IntegrationUpdateRequest,
)


def _encrypted_credentials(credentials_json: dict) -> str:
    try:
        return encrypt_secret(json.dumps(credentials_json, sort_keys=True))
    except RuntimeError as exc:
        raise ValidationAppError(
            "Encryption key is invalid.",
            details={"field": "encryption_key"},
        ) from exc


class IntegrationService:
    async def create_integration(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        data: IntegrationCreateRequest,
    ) -> Integration:
        provider = data.provider.value
        if provider not in provider_registry.supported_providers():
            raise ValidationAppError(
                "Unsupported integration provider.",
                details={"provider": provider},
            )
        if (
            provider == IntegrationProvider.MOYSKLAD.value
            and data.credentials_json is None
        ):
            raise ValidationAppError(
                "MoySklad credentials are required.",
                details={"provider": provider, "field": "credentials_json"},
            )

        integration = Integration(
            company_id=company_id,
            provider=provider,
            name=data.name.strip(),
            name_i18n=ensure_i18n_defaults(data.name.strip()) or {},
            status=IntegrationStatus.DRAFT.value,
            settings_json=data.settings_json or {},
            sync_cursor_json={},
        )
        session.add(integration)
        await session.flush()

        if data.credentials_json is not None:
            await self._replace_credentials(
                session,
                company_id=company_id,
                integration=integration,
                credentials_json=data.credentials_json,
            )

        await session.flush()
        return integration

    async def update_integration_translations(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration_id: UUID,
        data: IntegrationTranslationsUpdateRequest,
    ) -> Integration:
        integration = await self.get_integration(
            session,
            company_id=company_id,
            integration_id=integration_id,
        )
        integration.name_i18n = data.name_i18n or ensure_i18n_defaults(integration.name) or {}
        await session.flush()
        return integration

    async def list_integrations(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
    ) -> list[Integration]:
        result = await session.execute(
            select(Integration)
            .where(
                Integration.company_id == company_id,
                Integration.deleted_at.is_(None),
            )
            .order_by(Integration.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_integration(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration_id: UUID,
    ) -> Integration:
        result = await session.execute(
            select(Integration).where(
                Integration.id == integration_id,
                Integration.company_id == company_id,
                Integration.deleted_at.is_(None),
            )
        )
        integration = result.scalar_one_or_none()
        if integration is None:
            raise NotFoundError("Integration not found.")
        return integration

    async def update_integration(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration_id: UUID,
        data: IntegrationUpdateRequest,
    ) -> Integration:
        integration = await self.get_integration(
            session,
            company_id=company_id,
            integration_id=integration_id,
        )
        update_data = data.model_dump(exclude_unset=True)
        credentials_json = update_data.pop("credentials_json", None)

        for field, value in update_data.items():
            if field == "name" and value is not None:
                value = value.strip()
            if field == "status" and value is not None:
                value = value.value
            if field == "settings_json" and value is None:
                value = {}
            setattr(integration, field, value)

        if credentials_json is not None:
            await self._replace_credentials(
                session,
                company_id=company_id,
                integration=integration,
                credentials_json=credentials_json,
            )

        await session.flush()
        return integration

    async def delete_integration(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration_id: UUID,
    ) -> Integration:
        integration = await self.get_integration(
            session,
            company_id=company_id,
            integration_id=integration_id,
        )
        integration.status = IntegrationStatus.DISABLED.value
        integration.mark_deleted()
        await session.flush()
        return integration

    async def has_active_credentials(
        self,
        session: AsyncSession,
        *,
        integration_id: UUID,
    ) -> bool:
        result = await session.execute(
            select(IntegrationCredential.id).where(
                IntegrationCredential.integration_id == integration_id,
                IntegrationCredential.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None

    async def _active_credentials(
        self,
        session: AsyncSession,
        *,
        integration_id: UUID,
    ) -> IntegrationCredential | None:
        result = await session.execute(
            select(IntegrationCredential)
            .where(
                IntegrationCredential.integration_id == integration_id,
                IntegrationCredential.is_active.is_(True),
            )
            .order_by(desc(IntegrationCredential.created_at))
        )
        return result.scalars().first()

    async def decrypt_active_credentials(
        self,
        session: AsyncSession,
        *,
        integration: Integration,
    ) -> dict:
        credentials = await self._active_credentials(
            session,
            integration_id=integration.id,
        )
        if credentials is None:
            return {}
        try:
            decrypted = decrypt_secret(credentials.encrypted_credentials)
            return json.loads(decrypted)
        except RuntimeError as exc:
            raise ValidationAppError(
                "Encryption key is invalid.",
                details={"field": "encryption_key"},
            ) from exc
        except json.JSONDecodeError as exc:
            raise ValidationAppError(
                "Stored integration credentials are invalid."
            ) from exc

    async def build_provider(
        self,
        session: AsyncSession,
        *,
        integration: Integration,
    ) -> ERPProvider:
        credentials = await self.decrypt_active_credentials(
            session,
            integration=integration,
        )
        return provider_registry.create_provider(
            integration=integration,
            credentials=credentials,
        )

    async def test_integration(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration_id: UUID,
    ) -> ProviderConnectionResult:
        integration = await self.get_integration(
            session,
            company_id=company_id,
            integration_id=integration_id,
        )
        provider = await self.build_provider(session, integration=integration)
        return await provider.test_connection()

    async def _replace_credentials(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration: Integration,
        credentials_json: dict,
    ) -> IntegrationCredential:
        existing = await session.execute(
            select(IntegrationCredential).where(
                IntegrationCredential.integration_id == integration.id,
                IntegrationCredential.is_active.is_(True),
            )
        )
        active_credentials = list(existing.scalars().all())
        now = utc_now()
        next_version = 1
        for credential in active_credentials:
            next_version = max(next_version, credential.credential_version + 1)
            credential.is_active = False
            credential.rotated_at = now

        credential = IntegrationCredential(
            company_id=company_id,
            integration_id=integration.id,
            encrypted_credentials=_encrypted_credentials(credentials_json),
            credential_version=next_version,
            is_active=True,
        )
        session.add(credential)
        await session.flush()
        return credential


integration_service = IntegrationService()
