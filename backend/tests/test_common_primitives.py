from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.common.datetime import ensure_timezone_aware, format_iso, to_utc, utc_now
from app.common.pagination import PaginationParams, create_paginated_response
from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ExampleModel(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "example_models_for_tests"


def test_datetime_helpers_return_timezone_aware_utc_values() -> None:
    now = utc_now()
    naive = datetime(2026, 1, 1, 12, 0, 0)

    assert now.tzinfo is not None
    assert ensure_timezone_aware(naive).tzinfo == UTC
    assert to_utc(naive).tzinfo == UTC
    assert format_iso(naive).endswith("+00:00")


def test_base_model_mixins_define_expected_columns() -> None:
    columns = ExampleModel.__table__.columns

    assert columns["id"].primary_key is True
    assert columns["created_at"].nullable is False
    assert columns["updated_at"].nullable is False
    assert columns["deleted_at"].nullable is True


def test_soft_delete_mixin_marks_instance_deleted() -> None:
    instance = ExampleModel()

    assert instance.is_deleted is False

    instance.mark_deleted()

    assert instance.is_deleted is True
    assert instance.deleted_at is not None
    assert instance.deleted_at.tzinfo is not None


def test_uuid_primary_key_default_generates_uuid() -> None:
    default = ExampleModel.__table__.columns["id"].default

    assert default is not None
    assert default.is_callable is True


def test_pagination_defaults_and_response_shape() -> None:
    assert PaginationParams().limit == 50

    params = PaginationParams(limit=2)
    response = create_paginated_response(items=["a", "b"], params=params, total=3)

    assert params.limit == 2
    assert response.items == ["a", "b"]
    assert response.pagination.limit == 2
    assert response.pagination.offset == 0
    assert response.pagination.total == 3
    assert response.pagination.has_more is True


def test_pagination_rejects_limit_above_max() -> None:
    with pytest.raises(ValidationError):
        PaginationParams(limit=201)


def test_fernet_dependency_available_for_encryption_tests() -> None:
    assert isinstance(Fernet.generate_key(), bytes)
