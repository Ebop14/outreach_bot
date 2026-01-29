"""SQLite cache for scraped contexts and progress tracking."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiosqlite

from outreach_bot.config import get_settings
from outreach_bot.models.context import ScrapedContext


class SQLiteCache:
    """SQLite-based cache with TTL and progress tracking."""

    def __init__(self, db_path: Optional[Path] = None):
        settings = get_settings()
        self.db_path = db_path or settings.cache_db_path
        self.ttl_days = settings.cache_ttl_days
        self._db: Optional[aiosqlite.Connection] = None

    async def __aenter__(self) -> "SQLiteCache":
        """Enter async context and initialize database."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)
        await self._init_tables()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self._db:
            await self._db.close()

    async def _init_tables(self):
        """Create database tables if they don't exist."""
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS scraped_contexts (
                domain TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                scraped_at TEXT NOT NULL
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS processing_progress (
                csv_hash TEXT PRIMARY KEY,
                last_processed_index INTEGER NOT NULL,
                total_rows INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS generated_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_address TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        await self._db.commit()

    # Context caching methods

    async def get_context(self, domain: str) -> Optional[ScrapedContext]:
        """
        Get cached context for a domain if not expired.

        Returns:
            ScrapedContext if found and valid, None otherwise.
        """
        cursor = await self._db.execute(
            "SELECT data, scraped_at FROM scraped_contexts WHERE domain = ?",
            (domain.lower(),),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        data_json, scraped_at_str = row
        scraped_at = datetime.fromisoformat(scraped_at_str)

        # Check TTL
        if datetime.utcnow() - scraped_at > timedelta(days=self.ttl_days):
            # Cache expired, delete it
            await self._db.execute(
                "DELETE FROM scraped_contexts WHERE domain = ?",
                (domain.lower(),),
            )
            await self._db.commit()
            return None

        data = json.loads(data_json)
        return ScrapedContext.from_dict(data)

    async def set_context(self, context: ScrapedContext):
        """Cache a scraped context."""
        await self._db.execute(
            """
            INSERT OR REPLACE INTO scraped_contexts (domain, data, scraped_at)
            VALUES (?, ?, ?)
            """,
            (
                context.domain.lower(),
                json.dumps(context.to_dict()),
                context.scraped_at.isoformat(),
            ),
        )
        await self._db.commit()

    # Progress tracking methods

    async def get_progress(self, csv_hash: str) -> Optional[tuple[int, int]]:
        """
        Get processing progress for a CSV file.

        Returns:
            Tuple of (last_processed_index, total_rows) if found.
        """
        cursor = await self._db.execute(
            "SELECT last_processed_index, total_rows FROM processing_progress WHERE csv_hash = ?",
            (csv_hash,),
        )
        row = await cursor.fetchone()
        return (row[0], row[1]) if row else None

    async def set_progress(self, csv_hash: str, last_index: int, total_rows: int):
        """Update processing progress."""
        await self._db.execute(
            """
            INSERT OR REPLACE INTO processing_progress
            (csv_hash, last_processed_index, total_rows, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (csv_hash, last_index, total_rows, datetime.utcnow().isoformat()),
        )
        await self._db.commit()

    async def clear_progress(self, csv_hash: str):
        """Clear progress for a CSV file."""
        await self._db.execute(
            "DELETE FROM processing_progress WHERE csv_hash = ?",
            (csv_hash,),
        )
        await self._db.commit()

    # Email tracking methods

    async def save_email(self, email_address: str, email_data: dict):
        """Save a generated email record."""
        await self._db.execute(
            """
            INSERT INTO generated_emails (email_address, data, created_at)
            VALUES (?, ?, ?)
            """,
            (email_address, json.dumps(email_data), datetime.utcnow().isoformat()),
        )
        await self._db.commit()

    async def get_emails_for_address(self, email_address: str) -> list[dict]:
        """Get all generated emails for an address."""
        cursor = await self._db.execute(
            "SELECT data FROM generated_emails WHERE email_address = ?",
            (email_address,),
        )
        rows = await cursor.fetchall()
        return [json.loads(row[0]) for row in rows]

    # Utility methods

    async def clear_all(self):
        """Clear all cached data."""
        await self._db.execute("DELETE FROM scraped_contexts")
        await self._db.execute("DELETE FROM processing_progress")
        await self._db.execute("DELETE FROM generated_emails")
        await self._db.commit()

    async def clear_expired(self):
        """Remove expired cache entries."""
        expiry_date = datetime.utcnow() - timedelta(days=self.ttl_days)
        await self._db.execute(
            "DELETE FROM scraped_contexts WHERE scraped_at < ?",
            (expiry_date.isoformat(),),
        )
        await self._db.commit()

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        cursor = await self._db.execute("SELECT COUNT(*) FROM scraped_contexts")
        context_count = (await cursor.fetchone())[0]

        cursor = await self._db.execute("SELECT COUNT(*) FROM generated_emails")
        email_count = (await cursor.fetchone())[0]

        cursor = await self._db.execute("SELECT COUNT(*) FROM processing_progress")
        progress_count = (await cursor.fetchone())[0]

        return {
            "cached_contexts": context_count,
            "generated_emails": email_count,
            "active_jobs": progress_count,
        }
