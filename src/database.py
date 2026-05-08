"""sinkMAIND database module — SQLite FTS5 + vector embeddings store."""

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Optional, List, Dict


DB_PATH = os.path.expanduser("~/sinkia-memory/data/memory.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            source_path TEXT,
            doc_type TEXT,
            app TEXT,
            category TEXT,
            level TEXT,
            tags TEXT,
            created_at DATETIME,
            indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            content_hash TEXT UNIQUE,
            embedding BLOB
        )
    """)

    c.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
        USING fts5(content, source, app, tags, content=documents, content_rowid=id)
    """)

    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source)
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_app ON documents(app)
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type)
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category)
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_level ON documents(level)
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at)
    """)

    # Triggers to keep FTS in sync
    c.execute("""
        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, content, source, app, tags)
            VALUES (new.id, new.content, new.source, new.app, new.tags);
        END
    """)

    c.execute("""
        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, content, source, app, tags)
            VALUES ('delete', old.id, old.content, old.source, old.app, old.tags);
        END
    """)

    c.execute("""
        CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, content, source, app, tags)
            VALUES ('delete', old.id, old.content, old.source, old.app, old.tags);
            INSERT INTO documents_fts(rowid, content, source, app, tags)
            VALUES (new.id, new.content, new.source, new.app, new.tags);
        END
    """)

    conn.commit()
    conn.close()


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def insert_document(
    content: str,
    source: str,
    source_path: str = None,
    doc_type: str = None,
    app: str = None,
    category: str = None,
    level: str = None,
    tags: str = None,
    created_at: str = None,
) -> Optional[int]:
    """Insert a document with deduplication by content_hash. Returns id or None if duplicate."""
    content_hash = _hash_content(content)
    conn = _get_conn()
    try:
        cursor = conn.execute(
            """INSERT INTO documents
               (content, source, source_path, doc_type, app, category, level, tags, created_at, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (content, source, source_path, doc_type, app, category, level, tags, created_at, content_hash),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # Duplicate — skip
        return None
    finally:
        conn.close()


def search_text(query: str, filters: dict = None, limit: int = 20, sort: str = "relevance") -> List[dict]:
    """Full-text search with optional filters."""
    conn = _get_conn()
    filters = filters or {}

    # Build WHERE clause for non-FTS columns
    where_parts = []
    params = []

    if filters.get("source"):
        where_parts.append("d.source = ?")
        params.append(filters["source"])
    if filters.get("doc_type"):
        where_parts.append("d.doc_type = ?")
        params.append(filters["doc_type"])
    if filters.get("app"):
        where_parts.append("d.app = ?")
        params.append(filters["app"])
    if filters.get("category"):
        where_parts.append("d.category = ?")
        params.append(filters["category"])
    if filters.get("level"):
        where_parts.append("d.level = ?")
        params.append(filters["level"])
    if filters.get("since"):
        where_parts.append("d.created_at >= ?")
        params.append(filters["since"])
    if filters.get("until"):
        where_parts.append("d.created_at <= ?")
        params.append(filters["until"])
    if filters.get("path"):
        where_parts.append("d.source_path LIKE ?")
        params.append(f"%{filters['path']}%")
    if filters.get("tag"):
        where_parts.append("d.tags LIKE ?")
        params.append(f"%{filters['tag']}%")

    where_sql = ""
    if where_parts:
        where_sql = "AND " + " AND ".join(where_parts)

    # Escape single quotes in query for FTS5
    safe_query = query.replace('"', '""')

    order_sql = "rank" if sort == "relevance" else "d.created_at DESC"

    sql = f"""
        SELECT d.id, d.content, d.source, d.source_path, d.doc_type,
               d.app, d.category, d.level, d.tags, d.created_at, d.indexed_at
        FROM documents_fts f
        JOIN documents d ON d.id = f.rowid
        WHERE documents_fts MATCH ? {where_sql}
        ORDER BY {order_sql}
        LIMIT ?
    """
    params = [safe_query] + params + [limit]

    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        # FTS query syntax error — try simpler approach
        sql = f"""
            SELECT d.id, d.content, d.source, d.source_path, d.doc_type,
                   d.app, d.category, d.level, d.tags, d.created_at, d.indexed_at
            FROM documents d
            WHERE d.content LIKE ? {where_sql.replace('AND', 'AND', 1)}
            ORDER BY {order_sql}
            LIMIT ?
        """
        params = [f"%{query}%"] + params[1:] + [limit]
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return [dict(r) for r in rows]


def get_stats(by: str = None) -> List[dict]:
    """Get document statistics. by: 'app', 'source', 'doc_type', 'category'."""
    conn = _get_conn()
    if by:
        sql = f"SELECT {by} AS key, COUNT(*) AS count FROM documents GROUP BY {by} ORDER BY count DESC"
    else:
        sql = "SELECT COUNT(*) AS total FROM documents"

    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent(limit: int = 10) -> List[dict]:
    """Get most recently indexed documents."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT id, content, source, source_path, doc_type, app, category, level, tags, created_at, indexed_at
           FROM documents ORDER BY indexed_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_apps() -> List[str]:
    """Get list of unique apps in the database."""
    conn = _get_conn()
    rows = conn.execute("SELECT DISTINCT app FROM documents WHERE app IS NOT NULL ORDER BY app").fetchall()
    conn.close()
    return [r["app"] for r in rows]


def get_sources() -> List[str]:
    """Get list of unique sources in the database."""
    conn = _get_conn()
    rows = conn.execute("SELECT DISTINCT source FROM documents ORDER BY source").fetchall()
    conn.close()
    return [r["source"] for r in rows]


def get_documents_without_embeddings(limit: int = 100) -> List[dict]:
    """Get documents that don't have embeddings yet."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT id, content, source, source_path, doc_type, app, category, level, tags, created_at, indexed_at
           FROM documents WHERE embedding IS NULL LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_embedding(doc_id: int, embedding: list[float]):
    """Store embedding for a document."""
    conn = _get_conn()
    conn.execute("UPDATE documents SET embedding = ? WHERE id = ?", (json.dumps(embedding), doc_id))
    conn.commit()
    conn.close()


def get_documents_with_embeddings(filters: dict = None, limit: int = 1000) -> List[dict]:
    """Get documents that have embeddings, with optional filters."""
    conn = _get_conn()
    filters = filters or {}

    where_parts = ["embedding IS NOT NULL"]
    params = []

    if filters.get("source"):
        where_parts.append("source = ?")
        params.append(filters["source"])
    if filters.get("doc_type"):
        where_parts.append("doc_type = ?")
        params.append(filters["doc_type"])
    if filters.get("app"):
        where_parts.append("app = ?")
        params.append(filters["app"])
    if filters.get("category"):
        where_parts.append("category = ?")
        params.append(filters["category"])
    if filters.get("since"):
        where_parts.append("created_at >= ?")
        params.append(filters["since"])
    if filters.get("until"):
        where_parts.append("created_at <= ?")
        params.append(filters["until"])

    where_sql = " AND ".join(where_parts)
    rows = conn.execute(
        f"""SELECT id, content, source, source_path, doc_type, app, category, level, tags, created_at, embedding
            FROM documents WHERE {where_sql} LIMIT ?""",
        params + [limit],
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["embedding"] = json.loads(d["embedding"]) if d["embedding"] else None
        results.append(d)
    return results
