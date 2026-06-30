from fastapi import APIRouter
from pydantic import BaseModel
from google import genai
from google.genai import types

# Completely separate modules (this is the philosophy you liked)
from chat_log import (
    DEFAULT_MAX_HISTORY_TOKENS,
    get_limited_conversation_history,
    log_interaction,
    MODEL_NAME,
)
from knowledge_base import retrieve_relevant
from personality import get_system_instruction

# Initialize router (like a mini-FastAPI app)
router = APIRouter()

client = genai.Client()

class ChatRequest(BaseModel):
    message: str
    session_id: str


# Use @router instead of @app
@router.post("/chat")
def chat(request: ChatRequest):
    # ------------------------------------------------------------------
    # 1. Get recent conversation history (token limited for cost + focus)
    #    Default 50,000 tokens as you requested. Change in the call if needed.
    # ------------------------------------------------------------------
    history = get_limited_conversation_history(
        request.session_id,
        max_tokens=DEFAULT_MAX_HISTORY_TOKENS,
    )

    # ------------------------------------------------------------------
    # 2. Retrieve relevant knowledge (RAG)
    #    This is completely isolated in knowledge_base.py
    # ------------------------------------------------------------------
    relevant_chunks = retrieve_relevant(request.message, limit=5)

    # ------------------------------------------------------------------
    # 3. Build temporary augmented history for *this generation only*.
    #    - We inject retrieved context as a temporary "user" turn.
    #    - This gives Gemini the knowledge without polluting our permanent
    #      conversation logs (only real user + bot turns are saved).
    # ------------------------------------------------------------------
    temp_history = list(history)  # copy

    if relevant_chunks:
        context_text = "\n\n---\n\n".join(relevant_chunks)
        context_turn = types.Content(
            role="user",
            parts=[types.Part.from_text(
                text=f"[Knowledge Base Context - use if relevant to answer]\n{context_text}"
            )]
        )
        temp_history.append(context_turn)

    # Debug output - very useful while developing
    print("\n" + "=" * 60)
    print("SUMMER CHAT DEBUG")
    print(f"Session: {request.session_id}")
    print(f"Model: {MODEL_NAME}")
    print(f"Retrieved chunks: {len(relevant_chunks)}")
    for i, chunk in enumerate(relevant_chunks[:2], 1):   # show first 2 only
        preview = chunk[:200].replace("\n", " ")
        print(f"  [{i}] {preview}...")
    print("\n--- HISTORY BEING SENT (limited) ---")
    for item in temp_history:
        text = item.parts[0].text if item.parts else ""
        role = item.role.upper()
        preview = text[:150].replace("\n", " ")
        print(f"[{role}]: {preview}{'...' if len(text) > 150 else ''}")
    print(f"\n[NEW USER MESSAGE]: {request.message}")
    print("=" * 60 + "\n")

    # ------------------------------------------------------------------
    # 4. Create Gemini chat session with:
    #    - limited + context-injected history
    #    - strong system instruction (this is Summer's personality)
    # ------------------------------------------------------------------
    chat_session = client.chats.create(
        model=MODEL_NAME,
        history=temp_history,
        config=types.GenerateContentConfig(
            system_instruction=get_system_instruction(),
        ),
    )

    # Single send (the original code was calling this twice)
    response = chat_session.send_message(request.message)
    bot_reply = response.text or ""

    # Token counts
    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    reply_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    total_tokens = getattr(usage, "total_token_count", None) if usage else None

    # ------------------------------------------------------------------
    # 5. Log via the isolated chat_log module
    #    We also record what knowledge was retrieved this turn.
    # ------------------------------------------------------------------
    log_extra = {
        "retrieved_knowledge_count": len(relevant_chunks),
    }
    # Only store short preview of knowledge in logs to avoid bloat
    if relevant_chunks:
        log_extra["retrieved_knowledge_preview"] = [
            c[:300] for c in relevant_chunks[:2]
        ]

    log_interaction(
        session_id=request.session_id,
        user_message=request.message,
        bot_reply=bot_reply,
        prompt_tokens=prompt_tokens,
        reply_tokens=reply_tokens,
        total_tokens=total_tokens,
        model=MODEL_NAME,
        extra=log_extra,
    )

    return {"reply": bot_reply}