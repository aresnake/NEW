import time
import pytest

from hephaestus_mcp.sessions import SessionManager, LockManager
from hephaestus_mcp.shared.errors import ResourceLockedError


def test_session_create_list_close():
    sm = SessionManager()
    s = sm.create_session("test")
    assert s.id
    assert s.name == "test"

    listed = sm.list_sessions()
    assert any(sess.id == s.id for sess in listed)

    assert sm.get_session(s.id) is not None

    assert sm.close_session(s.id) is True
    assert sm.get_session(s.id) is None


def test_lock_acquire_release():
    lm = LockManager()
    s1 = "session-1"
    s2 = "session-2"
    lm.acquire("object:Cube.001", s1, ttl=1.0)
    with pytest.raises(ResourceLockedError) as exc:
        lm.acquire("object:Cube.001", s2, ttl=1.0)
    assert "locked" in str(exc.value)

    # release by non-owner should raise
    with pytest.raises(ResourceLockedError):
        lm.release("object:Cube.001", s2)

    assert lm.release("object:Cube.001", s1) is True


def test_lock_ttl_expiry():
    lm = LockManager()
    s1 = "s1"
    s2 = "s2"
    lm.acquire("obj:1", s1, ttl=0.05)
    time.sleep(0.06)
    # after ttl expiry, s2 should be able to acquire
    lm.acquire("obj:1", s2, ttl=1.0)
    assert lm.release("obj:1", s2) is True
