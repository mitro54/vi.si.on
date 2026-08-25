"""
Unit tests for SQLite conversation storage and promotion mechanics.
"""

from pathlib import Path

from desktop_ambient_ai.storage.conversation_store import ConversationStore


def test_conversation_crud_and_promotion(tmp_path: Path):
    db_file = tmp_path / "test_conversations.db"
    store = ConversationStore(db_path=db_file)

    # Create quick session
    session = store.create_session(mode="quick")
    assert session.mode == "quick"
    session.add_message("user", "How do I optimize OpenCV integral images in Python?")
    session.add_message("assistant", "Use cv2.integral() which calculates cumulative box sums in O(1).")

    # Before promotion, list_persistent should be empty
    assert len(store.list_persistent()) == 0

    # Auto-promotion to persistent
    session.promote_to_persistent()
    assert session.mode == "persistent"
    assert "OpenCV integral images" in session.title

    # Now it should show in list_persistent
    summaries = store.list_persistent()
    assert len(summaries) == 1
    assert summaries[0].id == session.id
    assert summaries[0].message_count == 2

    # Load session by ID
    loaded = store.get_session(session.id)
    assert loaded is not None
    assert loaded.id == session.id
    assert len(loaded.messages) == 2
    assert loaded.messages[0]["role"] == "user"
    assert loaded.messages[1]["role"] == "assistant"

    # Test latest persistent retrieval
    latest = store.get_latest_persistent()
    assert latest is not None
    assert latest.id == session.id
