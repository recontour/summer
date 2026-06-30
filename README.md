# Summer

Summer is a hobby chatbot project aiming to be maximally truthful and helpful, without the corporate safety-washing.

## Current structure (kept deliberately simple)

```
summer/
├── main.py              # FastAPI wiring only
├── chat_log.py          # ★ Logging + conversation history (with 50k token limit)
├── knowledge_base.py    # ★ Isolated RAG retrieval (vector search over knowledge_base)
├── personality.py       # ★ Summer's system prompt + personality (sent to Gemini calls)
├── routes/
│   └── chat.py          # Chat endpoint. Uses the modules above + personality
├── ingest.py            # Test ingestion script (leave for now)
├── .env.example
├── requirements.txt
└── .env                 # (gitignored)
```

## Why chat_log.py is separate

- The logging/persistence logic for every conversation turn is **completely isolated**.
- If you change the chat handler, add new features, or even rewrite how you call Gemini, the logging behavior stays consistent.
- All future improvements to logging (more fields, different collection, local JSONL backup, analytics collection, PII scrubbing, etc.) happen in **one file**.
- You (or future contributors) can look at `chat_log.py` and immediately understand "this is exactly how every interaction is recorded".

## How to run

1. `pip install -r requirements.txt`
2. Create `.env` with at least:
   ```
   GCP_PROJECT_ID=your-gcp-project
   # For Gemini:
   GOOGLE_API_KEY=your-gemini-api-key
   # or point to service account for Firestore if not using ADC:
   # GOOGLE_APPLICATION_CREDENTIALS=gcp-key.json
   ```
3. `uvicorn main:app --reload`

Then POST to `/chat`:
```json
{
  "message": "What is the capital of truth?",
  "session_id": "user-123-test"
}
```

## Logging details

Every turn is written to:
`sessions/{session_id}/messages`

The `chat_log.py` module is the single source of truth for that write.

You can also easily add a parallel write to a `chat_interactions` collection (see commented code inside `chat_log.py`) for easier global queries later.

## Current RAG + Personality setup

- `knowledge_base.py`: Handles retrieval. Uses the same embedding + vector storage approach from your ingest test.
- Conversation history is now token-limited (default 50,000 tokens — using latest turns).
- Basic but strong system instruction lives in `routes/chat.py` (Summer's personality and reasoning rules).
- Retrieved knowledge is injected temporarily for the Gemini call and recorded in logs (via `extra`).

RAG is for **knowledge**. Personality and behavior rules are in the system instruction (more reliable than putting rules in vector search).

## How to run

1. `pip install -r requirements.txt`
2. `cp .env.example .env` then edit `.env` and add your keys (see the comments in .env.example).
3. `uvicorn main:app --reload`

POST example:
```json
{
  "message": "Tell me about the evidence on topic X",
  "session_id": "test-user-1"
}
```

## Important setup note

For retrieval to work you need a vector index on the `knowledge_base` collection (field: `embedding`).

You said you have the vector DB set up — if `retrieve_relevant` fails at runtime, check the index in the Firebase / Firestore console.

## Next ideas

- Improve chunking / metadata in ingestion (when we revisit ingest.py)
- Better context formatting / reranking for RAG
- Expand Summer's system instruction with more specific principles
- Add a small always-included "constitution" for core values
- Switch the main brain to Grok API later

The modules (chat_log.py, knowledge_base.py, personality.py) are designed so you can evolve them independently.

