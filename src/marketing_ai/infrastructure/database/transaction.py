"""Application-owned transaction context; repositories must never commit.

SQLAlchemy owns commit/rollback mechanics. A failed commit can be ambiguous:
propagate the exception, never retry automatically or claim it was rolled back.
Tests exercise commit, rollback, cancellation and ownership against PostgreSQL.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from marketing_ai.infrastructure.database.metrics import TRANSACTION_DURATION, TRANSACTIONS

logger = logging.getLogger(__name__)


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    if session.in_transaction():
        raise RuntimeError("The application must own a fresh transaction; nesting is not implicit")
    started = perf_counter()
    outcome = "failure"
    try:
        async with session.begin():
            yield session
        outcome = "committed"
        logger.info("database_transaction_committed")
    except asyncio.CancelledError:
        outcome = "cancelled"
        logger.info("database_transaction_cancelled")
        raise
    except Exception:
        logger.warning("database_transaction_failed")
        raise
    finally:
        TRANSACTIONS.labels(outcome).inc()
        TRANSACTION_DURATION.labels(outcome).observe(perf_counter() - started)
