"""
Session management for Atomic Search.

Provides secure session handling with encrypted storage.
"""

import hashlib
import hmac
import json
import secrets
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SessionData:
    """Session data container."""
    session_id: str
    data: Dict[str, Any]
    created_at: float
    last_accessed: float
    expires_at: float


class SessionManager:
    """Secure session manager."""

    def __init__(self, secret_key: str = None, session_ttl: int = 86400):
        self.secret_key = secret_key or secrets.token_hex(32)
        self.session_ttl = session_ttl
        self._sessions: Dict[str, SessionData] = {}
        self._lock = threading.RLock()
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    def create_session(self, data: Dict[str, Any] = None) -> str:
        """Create a new session."""
        session_id = self._generate_session_id()

        now = time.time()
        session = SessionData(
            session_id=session_id,
            data=data or {},
            created_at=now,
            last_accessed=now,
            expires_at=now + self.session_ttl,
        )

        with self._lock:
            self._sessions[session_id] = session

        self._maybe_cleanup()

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        with self._lock:
            session = self._sessions.get(session_id)

            if not session:
                return None

            # Check expiration
            if time.time() > session.expires_at:
                del self._sessions[session_id]
                return None

            # Update access time
            session.last_accessed = time.time()

            return session.data.copy()

    def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data."""
        with self._lock:
            session = self._sessions.get(session_id)

            if not session:
                return False

            if time.time() > session.expires_at:
                del self._sessions[session_id]
                return False

            session.data.update(data)
            session.last_accessed = time.time()

            return True

    def delete_session(self, session_id: str):
        """Delete a session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

    def extend_session(self, session_id: str, ttl: int = None) -> bool:
        """Extend session expiration."""
        with self._lock:
            session = self._sessions.get(session_id)

            if not session:
                return False

            session.expires_at = time.time() + (ttl or self.session_ttl)
            session.last_accessed = time.time()

            return True

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get session metadata."""
        with self._lock:
            session = self._sessions.get(session_id)

            if not session:
                return None

            return {
                "session_id": session.session_id,
                "created_at": session.created_at,
                "last_accessed": session.last_accessed,
                "expires_at": session.expires_at,
                "data_keys": list(session.data.keys()),
            }

    def _generate_session_id(self) -> str:
        """Generate secure session ID."""
        timestamp = str(time.time())
        random_bytes = secrets.token_bytes(32)
        raw = timestamp.encode() + random_bytes

        signature = hmac.new(
            self.secret_key.encode(),
            raw,
            hashlib.sha256
        ).hexdigest()[:16]

        return f"{raw.hex()[:32]}.{signature}"

    def _validate_session_id(self, session_id: str) -> bool:
        """Validate session ID signature."""
        try:
            parts = session_id.split(".")
            if len(parts) != 2:
                return False

            raw_hex, signature = parts

            expected_sig = hmac.new(
                self.secret_key.encode(),
                bytes.fromhex(raw_hex),
                hashlib.sha256
            ).hexdigest()[:16]

            return hmac.compare_digest(signature, expected_sig)
        except Exception:
            return False

    def _maybe_cleanup(self):
        """Cleanup expired sessions."""
        now = time.time()

        if now - self._last_cleanup < self._cleanup_interval:
            return

        with self._lock:
            expired = [
                sid for sid, session in self._sessions.items()
                if session.expires_at < now
            ]

            for sid in expired:
                del self._sessions[sid]

            self._last_cleanup = now

    def cleanup(self) -> int:
        """Force cleanup expired sessions."""
        with self._lock:
            now = time.time()
            expired = [
                sid for sid, session in self._sessions.items()
                if session.expires_at < now
            ]

            for sid in expired:
                del self._sessions[sid]

            self._last_cleanup = now

            return len(expired)

    def get_stats(self) -> Dict:
        """Get session statistics."""
        with self._lock:
            now = time.time()
            active = sum(1 for s in self._sessions.values() if s.expires_at > now)
            expired = len(self._sessions) - active

            return {
                "total_sessions": len(self._sessions),
                "active_sessions": active,
                "expired_sessions": expired,
                "session_ttl": self.session_ttl,
            }


class AnonymousSessionManager(SessionManager):
    """Session manager for anonymous users."""

    def __init__(self, secret_key: str = None):
        super().__init__(secret_key, session_ttl=604800)  # 7 days
        self.anon_prefix = "anon_"

    def create_anonymous(self) -> str:
        """Create anonymous session."""
        session_id = self.create_session({
            "is_anonymous": True,
            "theme": "dark",
            "language": "en",
        })
        return session_id

    def get_anonymous(self, session_id: str) -> Optional[Dict]:
        """Get anonymous session."""
        if not session_id.startswith(self.anon_prefix):
            return None

        return self.get_session(session_id)


# Global session managers
session_manager = SessionManager()
anon_session_manager = AnonymousSessionManager()
