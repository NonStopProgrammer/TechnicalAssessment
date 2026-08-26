"""AGENT-1.3: mocked/seeded transaction store standing in for a real
core-banking integration (see requirements/11-non-goals-and-assumptions.md).
"""

import json
from pathlib import Path

from agentic.errors import TransactionNotFoundError
from shared.db.base import session_scope
from shared.db.models import SeededTransaction
from shared.models.transaction import TransactionPayload

SEED_FILE = Path(__file__).resolve().parent.parent / "seed_data" / "transactions.json"


def seed_transactions() -> int:
    records = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    with session_scope() as db:
        for record in records:
            db.merge(SeededTransaction(transaction_id=record["transaction_id"], payload=record))
    return len(records)


def get_transaction_details(transaction_id: str) -> TransactionPayload:
    with session_scope() as db:
        row = db.get(SeededTransaction, transaction_id)
        if row is None:
            raise TransactionNotFoundError(transaction_id)
        return TransactionPayload.model_validate(row.payload)
