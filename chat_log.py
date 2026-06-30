"""
chat_log.py

Dedicated, self-contained module for logging all chat interactions to Firestore.

WHY THIS FILE EXISTS (separate from main chat code):
- All interaction persistence logic lives here.
- You can change, improve, or completely replace how logs are stored
  (different collection, add backup to file, switch to another DB, add filtering)
  WITHOUT touching routes/chat.py or any other business logic.
- Makes the logging flow reliable and easy to reason about as the project grows.

Also owns conversation history retrieval (with token limiting for cost/control).
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
from google import genai
from google.cloud import firestore
from google.genai import types
from typing import Any, Optional

load_dotenv()

# ------------------------------------------------------------------
# Internal: lazy Firestore client (only created when first needed)
# ------------------------------------------------------------------
_db: Optional[firestore.Client] = None
_genai_client: Optional[genai.Client] = None

MODEL_NAME = "gemini-3.1-flash-lite"   # The cheap model you want to use heavily

# Default history window for cost control and focus on recent context
DEFAULT_MAX_HISTORY_TOKENS = 50000


def _get_db() -> firestore.Client:
    """Create (once) and return the Firestore client.

    Looks for:
    - GCP_PROJECT_ID
    - GOOGLE_APPLICATION_CREDENTIALS (pointing to your service account json)
    """
    global _db
    if _db is None:
        project_id = os.getenv("GCP_PROJECT_ID")
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if not project_id:
            raise RuntimeError(
                "GCP_PROJECT_ID is not set in your .env. "
                "This is required for Firestore. See .env.example"
            )

        # google libraries will automatically use GOOGLE_APPLICATION_CREDENTIALS if set
        _db = firestore.Client(project=project_id)
    return _db


def _get_genai_client() -> genai.Client:
    """Lazy Gemini client (used for token counting etc.)."""
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client()
    return _genai_client


# ------------------------------------------------------------------
# Public API - this is the stable interface other code should use
# ------------------------------------------------------------------

def get_conversation_history(session_id: str) -> list[types.Content]:
    """
    Fetch previous turns for this session and return them in the exact
    format the Gemini client expects for chat history.

    This is the ONLY place that knows the Firestore storage format
    for conversation turns.
    """
    db = _get_db()
    messages_ref = (
        db.collection("sessions")
        .document(session_id)
        .collection("messages")
        .order_by("timestamp")
    )

    history: list[types.Content] = []
    for doc in messages_ref.stream():
        data = doc.to_dict() or {}
        if "user_message" in data and data["user_message"]:
            history.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=data["user_message"])],
                )
            )
        if "bot_reply" in data and data["bot_reply"]:
            history.append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=data["bot_reply"])],
                )
            )
    return history


def get_limited_conversation_history(
    session_id: str, max_tokens: int = 50000
) -> list[types.Content]:
    """
    Same as get_conversation_history but returns only the most recent turns
    that fit within the token budget.

    We truncate from the *oldest* messages so the latest context is always kept.
    This is important for cost control and to stay within practical context.

    Uses the real Gemini count_tokens API for accuracy.
    Falls back to last ~25 turns if counting fails.
    """
    full_history = get_conversation_history(session_id)
    if not full_history:
        return full_history

    if max_tokens <= 0:
        return full_history[-1:]  # at least something

    genai_client = _get_genai_client()

    # Try removing oldest turns until the remaining history is under budget
    for start in range(len(full_history)):
        candidate = full_history[start:]
        try:
            count_result = genai_client.models.count_tokens(
                model=MODEL_NAME,
                contents=candidate,
            )
            token_count = getattr(count_result, "total_tokens", 0) or 0
            if token_count <= max_tokens:
                if start > 0:
                    print(f"[chat_log] History truncated from {len(full_history)} to {len(candidate)} turns (~{token_count} tokens)")
                return candidate
        except Exception as e:
            print(f"[chat_log] Token count failed, using fallback: {e}")
            break

    # Fallback: keep the last 25 turns (safe default)
    fallback = full_history[-25:]
    print(f"[chat_log] Using fallback recent history (last {len(fallback)} turns)")
    return fallback


def log_interaction(
    session_id: str,
    user_message: str,
    bot_reply: str,
    *,
    prompt_tokens: Optional[int] = None,
    reply_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    model: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """
    Persist ONE complete user <-> bot exchange.

    This function is intentionally defensive:
    - It swallows errors so a logging problem never breaks the chat for the user.
    - It is the single place to modify if you want to change logging behavior.
    - Future ideas (all isolated here):
        * Write to a second "chat_interactions" collection for easier analytics
        * Append to a local JSONL file as backup
        * Add PII redaction
        * Log latency, safety scores, RAG sources used, etc.
    """
    try:
        db = _get_db()
        messages_ref = (
            db.collection("sessions")
            .document(session_id)
            .collection("messages")
        )

        record: dict[str, Any] = {
            "user_message": user_message,
            "bot_reply": bot_reply,
            "timestamp": firestore.SERVER_TIMESTAMP,
        }

        if prompt_tokens is not None:
            record["prompt_tokens"] = prompt_tokens
            record["reply_tokens"] = reply_tokens
            record["total_tokens"] = total_tokens

        if model:
            record["model"] = model

        if extra:
            record.update(extra)

        messages_ref.add(record)

        # ------------------------------------------------------------------
        # Optional: also write to a flat top-level collection for easier
        # querying / dashboards later. Uncomment if you want it.
        # ------------------------------------------------------------------
        # db.collection("chat_interactions").add({
        #     **record,
        #     "session_id": session_id,
        # })

        print(f"[chat_log] Interaction saved | session={session_id} | model={model or 'unknown'}")

    except Exception as e:
        # IMPORTANT: logging failures must never crash or delay the reply to the user.
        print(f"[chat_log ERROR] Failed to write interaction for session {session_id}: {e}")
        # In the future you could add a local file fallback here:
        # _write_fallback_log(session_id, user_message, bot_reply, str(e))


# Small helper you can expand later for local dev without Firestore
def _write_fallback_log(session_id: str, user_msg: str, bot_msg: str, error: str):
    """Placeholder for future local file backup when Firestore is unavailable."""
    pass
