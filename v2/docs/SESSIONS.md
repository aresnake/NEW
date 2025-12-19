# Sessions & Locks (v2)

This document describes the in-memory Session Manager and Lock Manager added in v2.

## Sessions
- create_session(name) -> session_id
- get_session(session_id)
- list_sessions()
- close_session(session_id)

## Locks
- acquire(resource, session_id, ttl=30.0)
  - Raises `ResourceLockedError` if resource is currently owned.
- release(resource, session_id)
  - Raises `ResourceLockedError` if releasing from non-owner.
- get_lock(resource) -> {owner, expires_at} | None

These components are currently in-memory. Future work: expose HTTP/MCP endpoints for session creation and lock management, persistence, and distributed coordination.
