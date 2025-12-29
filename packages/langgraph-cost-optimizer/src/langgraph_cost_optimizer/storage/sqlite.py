"""SQLite storage backend for persistent cost tracking."""

import json
from typing import Optional
from datetime import datetime
from pathlib import Path

try:
    import aiosqlite
except ImportError:
    raise ImportError(
        "SQLite storage requires aiosqlite. "
        "Install with: pip install langgraph-cost-optimizer[sqlite]"
    )

from langgraph_cost_optimizer.tracker import CostRecord


class SQLiteStorage:
    """
    SQLite storage backend for persistent cost tracking.

    Stores cost records in a local SQLite database file.
    Requires the 'sqlite' extra: pip install langgraph-cost-optimizer[sqlite]

    Example:
        storage = SQLiteStorage("costs.db")
        await storage.initialize()
        await storage.save(record)
        records = await storage.get_all()
    """

    def __init__(self, db_path: str = "langgraph_costs.db"):
        """
        Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._initialized = False

    async def initialize(self) -> None:
        """Create tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cost_records (
                    id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    agent_name TEXT,
                    node_name TEXT,
                    metadata TEXT
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent ON cost_records(agent_name)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_node ON cost_records(node_name)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_model ON cost_records(model_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON cost_records(timestamp)
            """)
            await db.commit()
        self._initialized = True

    async def save(self, record: CostRecord) -> None:
        """Save a cost record."""
        if not self._initialized:
            await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO cost_records
                (id, model_id, input_tokens, output_tokens, cost_usd, timestamp, agent_name, node_name, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.model_id,
                    record.input_tokens,
                    record.output_tokens,
                    record.cost_usd,
                    record.timestamp.isoformat(),
                    record.agent_name,
                    record.node_name,
                    json.dumps(record.metadata),
                ),
            )
            await db.commit()

    async def get(self, record_id: str) -> Optional[CostRecord]:
        """Get a record by ID."""
        if not self._initialized:
            await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM cost_records WHERE id = ?", (record_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_record(row)
        return None

    async def get_all(
        self,
        agent_name: Optional[str] = None,
        node_name: Optional[str] = None,
        model_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[CostRecord]:
        """Get records with optional filtering."""
        if not self._initialized:
            await self.initialize()

        query = "SELECT * FROM cost_records WHERE 1=1"
        params = []

        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)
        if node_name:
            query += " AND node_name = ?"
            params.append(node_name)
        if model_id:
            query += " AND model_id = ?"
            params.append(model_id)
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        query += " ORDER BY timestamp DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        records = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    records.append(self._row_to_record(row))

        return records

    async def get_summary(self) -> dict:
        """Get aggregated summary."""
        if not self._initialized:
            await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT
                    COALESCE(SUM(cost_usd), 0) as total_cost,
                    COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                    COUNT(*) as num_records
                FROM cost_records
            """) as cursor:
                row = await cursor.fetchone()
                return {
                    "total_cost_usd": row[0],
                    "total_tokens": row[1],
                    "num_records": row[2],
                }

    async def clear(self) -> None:
        """Clear all records."""
        if not self._initialized:
            await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM cost_records")
            await db.commit()

    def _row_to_record(self, row) -> CostRecord:
        """Convert a database row to CostRecord."""
        return CostRecord(
            id=row["id"],
            model_id=row["model_id"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cost_usd=row["cost_usd"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            agent_name=row["agent_name"],
            node_name=row["node_name"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
