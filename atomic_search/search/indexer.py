"""
Search indexer for Atomic Search.

Indexes search results for faster retrieval and caching.
"""

import hashlib
import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


class SearchIndexer:
    """Indexes and caches search results."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or "/tmp/atomic_search_index.db"
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize the database."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Search results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    query_hash TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    engine TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_hash 
                ON search_results(query_hash)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON search_results(created_at)
            """)

            # Trending searches table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trending_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL UNIQUE,
                    count INTEGER DEFAULT 1,
                    last_searched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # User preferences table (encrypted)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anon_id TEXT NOT NULL UNIQUE,
                    preferences_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Voting data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result_hash TEXT NOT NULL,
                    query_hash TEXT NOT NULL,
                    vote_type INTEGER NOT NULL,
                    anon_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(result_hash, anon_id)
                )
            """)

            # Bookmarks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anon_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT,
                    snippet TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(anon_id, url)
                )
            """)

            # Collections table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anon_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(anon_id, name)
                )
            """)

            # Collection items table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS collection_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id INTEGER NOT NULL,
                    result_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (collection_id) REFERENCES collections(id)
                )
            """)

            conn.commit()
            conn.close()

    def index_result(self, query: str, result: Dict[str, Any], engine: str = "bing") -> int:
        """Index a search result."""
        query_hash = self._hash_query(query)
        result_json = json.dumps(result)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO search_results 
                (query, query_hash, result_json, engine)
                VALUES (?, ?, ?, ?)
            """, (query, query_hash, result_json, engine))

            result_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return result_id

    def get_cached_results(self, query: str, max_age_seconds: int = 3600) -> Optional[List[Dict]]:
        """Get cached results for a query."""
        query_hash = self._hash_query(query)
        max_age = datetime.now() - timedelta(seconds=max_age_seconds)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT result_json FROM search_results
                WHERE query_hash = ?
                AND created_at > ?
                ORDER BY engine = 'bing' DESC, created_at DESC
            """, (query_hash, max_age.isoformat()))

            rows = cursor.fetchall()

            # Update access count
            cursor.execute("""
                UPDATE search_results
                SET access_count = access_count + 1,
                    last_accessed = CURRENT_TIMESTAMP
                WHERE query_hash = ?
            """, (query_hash,))

            conn.commit()
            conn.close()

            if rows:
                return [json.loads(row[0]) for row in rows]

        return None

    def track_search(self, query: str):
        """Track a search query for trending."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO trending_searches (query, count, last_searched)
                VALUES (?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(query) DO UPDATE SET
                    count = count + 1,
                    last_searched = CURRENT_TIMESTAMP
            """, (query.lower().strip(),))

            conn.commit()
            conn.close()

    def get_trending(self, limit: int = 10) -> List[Dict]:
        """Get trending searches."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT query, count FROM trending_searches
                WHERE last_searched > datetime('now', '-7 days')
                ORDER BY count DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            return [{"query": row[0], "count": row[1]} for row in rows]

    def add_vote(self, result_hash: str, query_hash: str, vote_type: int, anon_id: str = None) -> bool:
        """Add a vote for a result."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO votes
                    (result_hash, query_hash, vote_type, anon_id)
                    VALUES (?, ?, ?, ?)
                """, (result_hash, query_hash, vote_type, anon_id))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
            finally:
                conn.close()

    def get_votes(self, result_hash: str = None) -> Dict:
        """Get vote counts."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if result_hash:
                cursor.execute("""
                    SELECT vote_type, COUNT(*) as count
                    FROM votes
                    WHERE result_hash = ?
                    GROUP BY vote_type
                """, (result_hash,))
            else:
                cursor.execute("""
                    SELECT result_hash, vote_type, COUNT(*) as count
                    FROM votes
                    GROUP BY result_hash, vote_type
                """)

            rows = cursor.fetchall()
            conn.close()

            if result_hash:
                upvotes = sum(1 for row in rows if row[0] > 0)
                downvotes = sum(1 for row in rows if row[0] < 0)
                return {"upvotes": upvotes, "downvotes": downvotes, "total": upvotes - downvotes}
            else:
                result = {}
                for row in rows:
                    rh, vt, count = row
                    if rh not in result:
                        result[rh] = {"upvotes": 0, "downvotes": 0}
                    if vt > 0:
                        result[rh]["upvotes"] = count
                    else:
                        result[rh]["downvotes"] = count
                return result

    def add_bookmark(self, anon_id: str, url: str, title: str = None, snippet: str = None) -> bool:
        """Add a bookmark."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                cursor.execute("""
                    INSERT INTO bookmarks (anon_id, url, title, snippet)
                    VALUES (?, ?, ?, ?)
                """, (anon_id, url, title, snippet))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
            finally:
                conn.close()

    def get_bookmarks(self, anon_id: str) -> List[Dict]:
        """Get user bookmarks."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT url, title, snippet, created_at
                FROM bookmarks
                WHERE anon_id = ?
                ORDER BY created_at DESC
            """, (anon_id,))

            rows = cursor.fetchall()
            conn.close()

            return [{"url": row[0], "title": row[1], "snippet": row[2], "created_at": row[3]} for row in rows]

    def create_collection(self, anon_id: str, name: str, description: str = None) -> int:
        """Create a new collection."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO collections (anon_id, name, description)
                VALUES (?, ?, ?)
            """, (anon_id, name, description))

            collection_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return collection_id

    def get_collections(self, anon_id: str) -> List[Dict]:
        """Get user collections."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, name, description, created_at
                FROM collections
                WHERE anon_id = ?
                ORDER BY created_at DESC
            """, (anon_id,))

            rows = cursor.fetchall()
            conn.close()

            return [{"id": row[0], "name": row[1], "description": row[2], "created_at": row[3]} for row in rows]

    def cleanup_old_entries(self, max_age_days: int = 30):
        """Remove old entries from the database."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM search_results
                WHERE created_at < datetime('now', '-{} days')
            """.format(max_age_days))

            deleted_results = cursor.rowcount

            cursor.execute("""
                DELETE FROM trending_searches
                WHERE last_searched < datetime('now', '-30 days')
            """)

            deleted_trending = cursor.rowcount

            conn.commit()
            conn.close()

            return {"deleted_results": deleted_results, "deleted_trending": deleted_trending}

    def _hash_query(self, query: str) -> str:
        """Create a hash of a query."""
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:32]

    def get_stats(self) -> Dict:
        """Get index statistics."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            stats = {}

            cursor.execute("SELECT COUNT(*) FROM search_results")
            stats["total_results"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM trending_searches")
            stats["tracked_queries"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM votes")
            stats["total_votes"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM bookmarks")
            stats["total_bookmarks"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM collections")
            stats["total_collections"] = cursor.fetchone()[0]

            cursor.execute("""
                SELECT AVG(access_count) FROM search_results
                WHERE access_count > 0
            """)
            avg = cursor.fetchone()[0]
            stats["avg_access_count"] = round(avg, 2) if avg else 0

            conn.close()

            return stats


# Global indexer instance
search_indexer = SearchIndexer()
