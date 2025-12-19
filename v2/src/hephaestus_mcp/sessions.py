from __future__ import annotations

from dataclasses import dataclass, field
import time
import uuid
from typing import Dict, Any, Optional

from .shared.errors import HephaestusError, ResourceLockedError


@dataclass
class Session:
    id: str
    name: str
    created_at: float
    last_seen: float
    metadata: Dict[str, Any] = field(default_factory=dict)




class SessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    def create_session(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> Session:
        sid = str(uuid.uuid4())
        now = time.time()
        session = Session(id=sid, name=name, created_at=now, last_seen=now, metadata=metadata or {})
        self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[Session]:
        return list(self._sessions.values())

    def close_session(self, session_id: str) -> bool:
        return bool(self._sessions.pop(session_id, None))

    def touch_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.last_seen = time.time()
        return True


class LockManager:
    def __init__(self) -> None:
        # resource -> (owner_session_id, expires_at)
        self._locks: Dict[str, tuple[str, float]] = {}

    def acquire(self, resource: str, session_id: str, ttl: float = 30.0) -> None:
        now = time.time()
        # cleanup expired
        existing = self._locks.get(resource)
        if existing:
            owner, expires_at = existing
            if expires_at > now:
                raise ResourceLockedError(f"Resource '{resource}' is locked by '{owner}'", owner=owner)
            else:
                # expired, remove
                self._locks.pop(resource, None)

        self._locks[resource] = (session_id, now + ttl)

    def release(self, resource: str, session_id: str) -> bool:
        current = self._locks.get(resource)
        if not current:
            return False
        owner, expires_at = current
        if owner != session_id:
            raise ResourceLockedError(f"Cannot release resource '{resource}' not owned by '{session_id}'", owner=owner)
        self._locks.pop(resource, None)
        return True

    def get_lock(self, resource: str) -> Optional[dict[str, Any]]:
        now = time.time()
        current = self._locks.get(resource)
        if not current:
            return None
        owner, expires_at = current
        if expires_at <= now:
            # expired
            self._locks.pop(resource, None)
            return None
        return {"owner": owner, "expires_at": expires_at}
