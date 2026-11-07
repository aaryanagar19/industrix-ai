from datetime import datetime, timezone
from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, PlainSerializer

T = TypeVar("T")


def _ser(d: datetime) -> str:
    return d.isoformat() + "Z" if d.tzinfo is None else d.isoformat()


def _naive_utc(d: datetime) -> datetime:
    """Inputs may carry tz info (e.g. trailing 'Z'); the DB stores naive UTC."""
    return d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d


UTCDatetime = Annotated[datetime, AfterValidator(_naive_utc), PlainSerializer(_ser, return_type=str, when_used="json")]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
