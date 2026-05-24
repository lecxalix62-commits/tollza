from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.models import Community, CommunityCreate, CommentDraft, DraftStatus, PublishResult


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "vk_comment_assistant.db"

SCHEMA_VERSION = 4


class SQLiteStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]

            if version < 2:
                # Full reset for very old schemas
                connection.executescript(
                    """
                    DROP TABLE IF EXISTS posts;
                    DROP TABLE IF EXISTS profiles;
                    DROP TABLE IF EXISTS drafts;
                    DROP TABLE IF EXISTS communities;
                    """
                )

            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS communities (
                    id TEXT PRIMARY KEY,
                    vk_group_id INTEGER NOT NULL,
                    screen_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS drafts (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    community_ids TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    moderation_note TEXT,
                    publish_results TEXT NOT NULL DEFAULT '[]',
                    image_attachment TEXT
                );

                CREATE TABLE IF NOT EXISTS autopilot_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS autopilot_contacted (
                    user_id INTEGER PRIMARY KEY,
                    contacted_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS autopilot_log (
                    id TEXT PRIMARY KEY,
                    run_at TEXT NOT NULL,
                    found INTEGER NOT NULL DEFAULT 0,
                    dm_sent INTEGER NOT NULL DEFAULT 0,
                    comment_sent INTEGER NOT NULL DEFAULT 0,
                    skipped INTEGER NOT NULL DEFAULT 0,
                    errors TEXT NOT NULL DEFAULT '[]'
                );
                """
            )

            if version == 2:
                try:
                    connection.execute("ALTER TABLE drafts ADD COLUMN image_attachment TEXT")
                except sqlite3.OperationalError:
                    pass

            if version < SCHEMA_VERSION:
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def list_communities(self) -> list[Community]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM communities ORDER BY created_at ASC"
            ).fetchall()
        return [self._row_to_community(row) for row in rows]

    def create_community(self, payload: CommunityCreate) -> Community:
        community = Community(
            id=f"comm-{uuid4().hex[:8]}",
            created_at=datetime.utcnow(),
            **payload.model_dump(),
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO communities (id, vk_group_id, screen_name, name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    community.id,
                    community.vk_group_id,
                    community.screen_name,
                    community.name,
                    community.created_at.isoformat(),
                ),
            )
        return community

    def get_community(self, community_id: str) -> Community | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM communities WHERE id = ?", (community_id,)
            ).fetchone()
        return self._row_to_community(row) if row else None

    def delete_community(self, community_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM communities WHERE id = ?", (community_id,)
            )
        return cursor.rowcount > 0

    def list_drafts(self) -> list[CommentDraft]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM drafts ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_draft(row) for row in rows]

    def create_draft(self, text: str, community_ids: list[str], image_attachment: str | None = None) -> CommentDraft:
        draft = CommentDraft(
            id=f"draft-{uuid4().hex[:8]}",
            text=text,
            community_ids=community_ids,
            created_at=datetime.utcnow(),
            image_attachment=image_attachment,
        )
        return self.save_draft(draft)

    def save_draft(self, draft: CommentDraft) -> CommentDraft:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO drafts (id, text, community_ids, status, created_at, moderation_note, publish_results, image_attachment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    text = excluded.text,
                    community_ids = excluded.community_ids,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    moderation_note = excluded.moderation_note,
                    publish_results = excluded.publish_results,
                    image_attachment = excluded.image_attachment
                """,
                (
                    draft.id,
                    draft.text,
                    json.dumps(draft.community_ids, ensure_ascii=False),
                    draft.status.value if isinstance(draft.status, DraftStatus) else draft.status,
                    draft.created_at.isoformat(),
                    draft.moderation_note,
                    json.dumps(
                        [r.model_dump() for r in draft.publish_results],
                        ensure_ascii=False,
                    ),
                    draft.image_attachment,
                ),
            )
        return draft

    def get_draft(self, draft_id: str) -> CommentDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM drafts WHERE id = ?", (draft_id,)
            ).fetchone()
        return self._row_to_draft(row) if row else None

    def delete_draft(self, draft_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM drafts WHERE id = ?", (draft_id,)
            )
        return cursor.rowcount > 0

    # ── Autopilot ────────────────────────────────────────────────────────────

    def get_autopilot_config(self) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM autopilot_config WHERE key = 'main'"
            ).fetchone()
        return json.loads(row["value"]) if row else {}

    def save_autopilot_config(self, data: dict) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO autopilot_config (key, value) VALUES ('main', ?)",
                (json.dumps(data, ensure_ascii=False),),
            )

    def get_autopilot_contacted(self) -> set[int]:
        with self._connect() as connection:
            rows = connection.execute("SELECT user_id FROM autopilot_contacted").fetchall()
        return {row["user_id"] for row in rows}

    def add_autopilot_contacted(self, user_id: int) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO autopilot_contacted (user_id) VALUES (?)", (user_id,)
            )

    def clear_autopilot_contacted(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM autopilot_contacted")

    def add_autopilot_log_entry(
        self, run_at: str, found: int, dm_sent: int,
        comment_sent: int, skipped: int, errors: list[str],
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO autopilot_log
                   (id, run_at, found, dm_sent, comment_sent, skipped, errors)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid4()), run_at, found, dm_sent, comment_sent, skipped,
                 json.dumps(errors, ensure_ascii=False)),
            )

    def get_autopilot_log(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM autopilot_log ORDER BY run_at DESC LIMIT 30"
            ).fetchall()
        return [
            {
                "run_at": row["run_at"],
                "found": row["found"],
                "dm_sent": row["dm_sent"],
                "comment_sent": row["comment_sent"],
                "skipped": row["skipped"],
                "errors": json.loads(row["errors"]),
            }
            for row in rows
        ]

    def count_autopilot_contacted(self) -> int:
        with self._connect() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM autopilot_contacted"
            ).fetchone()[0]

    @staticmethod
    def _row_to_community(row: sqlite3.Row) -> Community:
        return Community(
            id=row["id"],
            vk_group_id=row["vk_group_id"],
            screen_name=row["screen_name"],
            name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_draft(row: sqlite3.Row) -> CommentDraft:
        raw_results = json.loads(row["publish_results"] or "[]")
        return CommentDraft(
            id=row["id"],
            text=row["text"],
            community_ids=json.loads(row["community_ids"]),
            status=DraftStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            moderation_note=row["moderation_note"],
            publish_results=[PublishResult(**r) for r in raw_results],
            image_attachment=row["image_attachment"],
        )


store = SQLiteStore(DB_PATH)
