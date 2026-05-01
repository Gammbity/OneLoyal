from enum import StrEnum
from typing import NewType
from uuid import UUID

EntityId = NewType("EntityId", UUID)


class EntityStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"

