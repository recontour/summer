"""
knowledge_base.py

Dedicated, isolated module for Summer's knowledge base (RAG).

Responsibilities:
- Embedding text (using the same model/logic pattern as your test ingest)
- Retrieving the most relevant chunks for a user query via Firestore vector search
- (Future) Adding new knowledge cleanly

This module is completely separate from chat logic, history, logging, and personality.
Change retrieval strategy, chunking, or even swap the vector store here without
touching routes/chat.py.

You already have a vector index set up for the "knowledge_base" collection.
Retrieval uses the exact same embedding model you used in ingest.py.

Collection used: "knowledge_base"
Embedding model: "text-embedding-004" (768 dimensions assumed)
"""

import os
from dotenv import load_dotenv
from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from typing import Optional

load_dotenv()

# ------------------------------------------------------------------
# Constants - match what you already tested in ingest.py
# ------------------------------------------------------------------
EMBEDDING_MODEL = "text-embedding-004"
KNOWLEDGE_COLLECTION = "knowledge_base"

# Vector search distance. 
# "COSINE" is the usual default for text embeddings.
# Change to "EUCLIDEAN" or "DOT_PRODUCT" to match how you created the index in Firestore.
# We'll verify after your first test.
DISTANCE_MEASURE = "COSINE"

# ------------------------------------------------------------------
# Internal lazy clients
# ------------------------------------------------------------------
_db: Optional[firestore.Client] = None
_genai_client: Optional[genai.Client] = None


def _get_clients():
    global _db, _genai_client
    if _genai_client is None:
        _genai_client = genai.Client()
    if _db is None:
        project_id = os.getenv("GCP_PROJECT_ID")
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if not project_id:
            raise RuntimeError(
                "GCP_PROJECT_ID is not set in your .env. "
                "This is required for the knowledge base / vector search. "
                "See .env.example for details."
            )

        # The google-cloud libraries auto-pick up GOOGLE_APPLICATION_CREDENTIALS
        # when the env var points to your service account JSON.
        _db = firestore.Client(project=project_id)
    return _genai_client, _db


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def embed_text(text: str) -> list[float]:
    """Embed a single string using the same model as your ingestion test."""
    client, _ = _get_clients()
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text
    )
    return response.embeddings[0].values


def retrieve_relevant(query: str, limit: int = 5) -> list[str]:
    """
    Retrieve the most relevant text chunks from the knowledge base.

    Returns a simple list of text strings (most relevant first).
    You can later extend this to return metadata, scores, sources etc.

    This is the core retrieval function for RAG.
    """
    client, db = _get_clients()

    # 1. Embed the user's query using the same model
    query_embedding = embed_text(query)
    query_vector = Vector(query_embedding)

    # 2. Perform vector similarity search
    # Requires a vector index on knowledge_base/embedding (you said you set one up)
    try:
        vector_query = db.collection(KNOWLEDGE_COLLECTION).find_nearest(
            vector_field="embedding",
            query_vector=query_vector,
            limit=limit,
            distance_measure=DISTANCE_MEASURE,
        )

        chunks: list[str] = []
        for doc_snapshot in vector_query.stream():
            data = doc_snapshot.to_dict() or {}
            text = data.get("text")
            if text:
                chunks.append(text)

        print(f"[knowledge_base] Retrieved {len(chunks)} relevant chunks for query")
        return chunks

    except Exception as e:
        print(f"[knowledge_base ERROR] Vector search failed: {e}")
        print("  → Make sure the vector index exists on the 'knowledge_base' collection")
        print("  → Collection: knowledge_base | field: embedding | distance: COSINE")
        return []


def add_knowledge(text: str, metadata: Optional[dict] = None) -> None:
    """
    Add a new piece of knowledge to the vector store.

    Uses the exact same saving pattern as your original ingest.py test.
    Useful for future admin tools / bulk loading.
    """
    client, db = _get_clients()

    embedding_values = embed_text(text)
    doc: dict = {
        "text": text,
        "embedding": Vector(embedding_values),
    }
    if metadata:
        doc.update(metadata)

    db.collection(KNOWLEDGE_COLLECTION).add(doc)
    print(f"[knowledge_base] Added new knowledge chunk ({len(text)} chars)")
