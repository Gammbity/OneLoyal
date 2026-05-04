from dataclasses import dataclass
from uuid import UUID

from fastapi import Request


@dataclass(frozen=True)
class AuditContext:
    actor_user_id: UUID | None = None
    actor_customer_id: UUID | None = None
    actor_type: str | None = None
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


def audit_context_from_request(
    request: Request,
    *,
    actor_user_id: UUID | None = None,
    actor_customer_id: UUID | None = None,
    actor_type: str | None = None,
) -> AuditContext:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    request_id = getattr(request.state, "request_id", None)
    return AuditContext(
        actor_user_id=actor_user_id,
        actor_customer_id=actor_customer_id,
        actor_type=actor_type,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def resolve_actor_type(context: AuditContext | None) -> str:
    if context is None:
        return "system"
    if context.actor_type:
        return context.actor_type
    if context.actor_user_id:
        return "user"
    if context.actor_customer_id:
        return "customer"
    return "system"
