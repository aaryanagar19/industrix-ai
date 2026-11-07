from typing import Annotated

from fastapi import Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user, require_roles
from app.models import Machine

DB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[object, Depends(get_current_user)]

MANAGE_ASSETS = require_roles("plant_manager")
SAFETY = require_roles("safety_manager", "safety_officer")
SAFETY_MGMT = require_roles("safety_manager", "plant_manager")


class Pagination:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500)):
        self.page, self.page_size = page, page_size

    @property
    def offset(self):
        return (self.page - 1) * self.page_size


def paginate(q, p: Pagination):
    total = q.count()
    return q.offset(p.offset).limit(p.page_size).all(), total


def get_machine_or_404(db: Session, machine_id: int) -> Machine:
    m = db.get(Machine, machine_id)
    if not m:
        raise HTTPException(404, "Machine not found")
    return m


def bucket_expr(db: Session, column, seconds: int):
    """SQL expression bucketing a timestamp column into `seconds`-wide buckets (SQLite & PostgreSQL).
    The divisor is rendered as an integer literal on purpose: a bound NUMERIC parameter would turn SQLite's integer
    division into float division and silently disable bucketing."""
    import sqlalchemy as sa
    n = sa.literal_column(str(int(seconds)))
    if db.bind.dialect.name == "sqlite":
        return sa.cast(func.strftime("%s", column), sa.Integer) / n
    return func.floor(func.extract("epoch", column) / n)
