"""Unit tests for tool caching and compact session memory (Phase 1)."""
from __future__ import annotations

from database.models import Merchant
from providers.cache.memory_adapter import InMemoryCache
from relational_test_fixtures import seed_relational_profile
from services.chat_session_service import ChatSessionService
import pytest
from tools.merchant.profile_tool import get_merchant_profile_summary
from tools.merchant.metrics_tool import get_merchant_operational_metrics


def test_tool_cache_profile_summary(db_session):
    cache = InMemoryCache()

    m = Merchant(
        merchant_id="m_cache_01",
        name="Quán Cache Profile",
        cuisine="Món Việt",
        city="Hà Nội",
        city_slug="ha-noi",
    )
    db_session.add(m)
    seed_relational_profile(db_session, "m_cache_01", scores={"food_quality": 0.88})
    db_session.commit()

    # First call: query DB and store in cache
    res1 = get_merchant_profile_summary("m_cache_01", db=db_session, cache=cache)
    assert res1["status"] == "ok"
    assert res1["dimensions"]["food_quality"] == 0.88

    # Modify DB directly without clearing cache
    m.name = "Tên Mới Đã Đổi"
    db_session.commit()

    # Second call with cache: should return cached data (old name)
    res2 = get_merchant_profile_summary("m_cache_01", db=db_session, cache=cache)
    assert res2["name"] == "Quán Cache Profile"

    # Call without cache: should return fresh DB data (new name)
    res3 = get_merchant_profile_summary("m_cache_01", db=db_session, cache=None)
    assert res3["name"] == "Tên Mới Đã Đổi"


def test_tool_cache_metrics(db_session):
    cache = InMemoryCache()
    res1 = get_merchant_operational_metrics("m_cache_metrics_01", db=db_session, cache=cache)
    assert res1["status"] == "not_found"

    # Verify cached entry exists
    res2 = get_merchant_operational_metrics("m_cache_metrics_01", db=db_session, cache=cache)
    assert res2["status"] == "not_found"
def test_compact_session_memory(db_session):
    session_svc = ChatSessionService(db_session)

    session_obj = session_svc.get_or_create_session(
        session_id="sess_compact_01",
        user_id=None,
        context_snapshot={"merchant_id": "m_test_01"},
    )
    assert session_obj.session_id == "sess_compact_01"

    # Add 8 messages (4 turns)
    for i in range(1, 5):
        session_svc.append_message("sess_compact_01", "user", f"User question {i}")
        session_svc.append_message(
            "sess_compact_01",
            "agent",
            f"Agent long response {i} " + ("x" * 500),
        )

    # get_compact_history with max_turns=3 should return last 6 messages as plain text
    compact_history = session_svc.get_compact_history("sess_compact_01", max_turns=3)
    lines = compact_history.split("\n")
    assert len(lines) == 6
    assert lines[0].startswith("user: User question 2")
    assert lines[1].startswith("assistant: Agent long response 2")
    assert lines[1].endswith("...")
    assert len(lines[1]) <= len("assistant: ") + 453


def test_replacing_session_snapshot_removes_stale_keys(db_session):
    session_svc = ChatSessionService(db_session)
    session_svc.get_or_create_session(
        session_id="sess_replace_snapshot",
        context_snapshot={
            "merchant_id": "94",
            "merchant_agentic.legacy_state": {"stale": True},
        },
    )

    session_svc.update_session_snapshot(
        "sess_replace_snapshot",
        {"merchant_id": "94"},
        replace=True,
    )

    assert session_svc.get_session_snapshot("sess_replace_snapshot") == {
        "merchant_id": "94"
    }
def test_session_rejects_a_different_merchant_context(db_session):
    service = ChatSessionService(db_session)
    service.get_or_create_session(
        session_id="sess-merchant-bound",
        context_snapshot={"merchant_id": "merchant-a"},
    )

    with pytest.raises(ValueError, match="different merchant"):
        service.get_or_create_session(
            session_id="sess-merchant-bound",
            context_snapshot={"merchant_id": "merchant-b"},
        )
