"""sinkMAIND embeddings — Ollama-based semantic search."""

import json
import math
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database

CONFIG_PATH = os.path.expanduser("~/sinkia-memory/config.yaml")


def _load_config() -> dict:
    import yaml
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def get_ollama_config() -> dict:
    """Get Ollama embedding config."""
    config = _load_config()
    return config.get("embeddings", {})


from typing import List, Optional, Tuple


def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding vector from Ollama for a single text string."""
    emb_config = get_ollama_config()
    url = emb_config.get("url", "http://localhost:11434")
    model = emb_config.get("model", "nomic-embed-text")

    try:
        resp = requests.post(
            f"{url}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("embedding")
    except Exception as e:
        print(f"  ⚠ Error obteniendo embedding: {e}")
        return None


def get_embeddings_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """Get embeddings for multiple texts in a single Ollama API call.
    
    Uses the /api/embed endpoint (Ollama >=0.22) which accepts an array of inputs.
    Returns a list of embedding vectors (or None for each failed text).
    """
    if not texts:
        return []

    emb_config = get_ollama_config()
    url = emb_config.get("url", "http://localhost:11434")
    model = emb_config.get("model", "nomic-embed-text")

    try:
        resp = requests.post(
            f"{url}/api/embed",
            json={"model": model, "input": texts},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings_list = data.get("embeddings", [])
        # Pad with None if fewer embeddings returned than requested
        while len(embeddings_list) < len(texts):
            embeddings_list.append(None)
        return embeddings_list
    except Exception as e:
        print(f"  ⚠ Error obteniendo batch embeddings: {e}")
        return [None] * len(texts)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Calculate cosine similarity between two vectors using standard math."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def generate_and_store_embeddings(batch_size: int = 10, max_docs: int = 100, embed_batch: int = 20):
    """Generate embeddings for documents that don't have one yet.
    
    Uses Ollama batch embed API for efficiency — processes embed_batch texts
    per single HTTP request, and writes to DB in bulk transactions.
    
    Args:
        batch_size: Print progress every N docs
        max_docs: Maximum docs to process in one call (default 100 for incremental)
        embed_batch: Number of texts sent per Ollama API call (default 20)
    """
    docs = database.get_documents_without_embeddings(limit=max_docs)
    if not docs:
        print("  ✅ Todos los documentos ya tienen embeddings")
        return 0

    total = len(docs)
    print(f"  Generando embeddings para {total} documentos (embed_batch={embed_batch})...")

    count = 0
    errors = 0

    # Process in embed_batch chunks for Ollama API efficiency
    for chunk_start in range(0, total, embed_batch):
        chunk = docs[chunk_start:chunk_start + embed_batch]
        
        # Prepare texts (truncated to 500 chars for semantic meaning)
        texts = [doc["content"][:500] for doc in chunk]
        ids = [doc["id"] for doc in chunk]
        
        # Get embeddings in batch
        embeddings_list = get_embeddings_batch(texts)
        
        # Collect successful results for bulk DB write
        bulk_updates = []
        for doc_id, embedding in zip(ids, embeddings_list):
            if embedding:
                bulk_updates.append((doc_id, embedding))
                count += 1
            else:
                errors += 1
        
        # Batch write to DB
        if bulk_updates:
            database.update_embeddings_batch(bulk_updates)
        
        # Progress reporting
        processed = min(chunk_start + embed_batch, total)
        if processed % batch_size == 0 or processed == total:
            print(f"  Progreso: {processed}/{total} embeddings ({errors} errores)")
        
        # Throttle to avoid overloading Ollama
        time.sleep(0.3)

    print(f"  ✅ {count}/{total} embeddings generados ({errors} errores)")
    return count


def semantic_search(query: str, limit: int = 20, filters: dict = None) -> List[dict]:
    """Search using semantic similarity via embeddings."""
    query_embedding = get_embedding(query)
    if not query_embedding:
        print("  ⚠ No se pudo generar embedding para la query")
        return []

    # Get all documents with embeddings, applying filters to reduce set
    docs = database.get_documents_with_embeddings(filters=filters, limit=5000)
    if not docs:
        return []

    # Calculate similarity for each
    scored = []
    for doc in docs:
        if doc.get("embedding"):
            sim = cosine_similarity(query_embedding, doc["embedding"])
            scored.append((sim, doc))

    # Sort by similarity descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Return top results
    results = []
    for sim, doc in scored[:limit]:
        doc["score"] = round(sim, 4)
        doc.pop("embedding", None)  # Remove large vector from output
        results.append(doc)

    return results
