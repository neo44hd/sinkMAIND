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


from typing import List, Optional

def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding vector from Ollama for a text string."""
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


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Calculate cosine similarity between two vectors using standard math."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def generate_and_store_embeddings(batch_size: int = 10):
    """Generate embeddings for all documents that don't have one yet."""
    docs = database.get_documents_without_embeddings(limit=10000)
    if not docs:
        print("  ✅ Todos los documentos ya tienen embeddings")
        return 0

    total = len(docs)
    print(f"  Generando embeddings para {total} documentos...")

    count = 0
    for i, doc in enumerate(docs):
        # Truncate content to avoid huge payloads
        content = doc["content"][:1000]
        embedding = get_embedding(content)
        if embedding:
            database.update_embedding(doc["id"], embedding)
            count += 1

        if (i + 1) % batch_size == 0:
            print(f"  Progreso: {i + 1}/{total} embeddings generados")
            time.sleep(1)  # Don't overwhelm Ollama

    print(f"  ✅ {count}/{total} embeddings generados")
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
