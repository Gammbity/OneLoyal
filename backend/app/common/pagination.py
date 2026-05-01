from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.core.settings import get_settings


class PaginationParams(BaseModel):
    limit: int | None = None
    offset: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def apply_defaults_and_limits(self) -> "PaginationParams":
        settings = get_settings()
        if self.limit is None:
            self.limit = settings.pagination_default_limit
        if self.limit < 1:
            raise ValueError("limit must be greater than or equal to 1")
        if self.limit > settings.pagination_max_limit:
            raise ValueError(
                f"limit must be less than or equal to {settings.pagination_max_limit}"
            )
        return self


class PaginationMeta(BaseModel):
    limit: int
    offset: int
    total: int | None = None

    @computed_field
    @property
    def has_more(self) -> bool | None:
        if self.total is None:
            return None
        return self.offset + self.limit < self.total


class PaginatedResponse[T](BaseModel):
    items: list[T]
    pagination: PaginationMeta


def create_paginated_response[T](
    *,
    items: list[T],
    params: PaginationParams,
    total: int | None = None,
) -> PaginatedResponse[T]:
    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            limit=params.limit or get_settings().pagination_default_limit,
            offset=params.offset,
            total=total,
        ),
    )
