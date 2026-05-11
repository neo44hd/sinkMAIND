"""sinkMAIND search — combined textual + semantic search engine."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database
import embeddings


from typing import List, Optional

def search(query: str, semantic: bool = False, filters: dict = None, limit: int = 20, sort: str = "relevance") -> List[dict]:
    """Unified search: textual or semantic based on flag."""
    if semantic:
        return embeddings.semantic_search(query, limit=limit, filters=filters)
    else:
        return database.search_text(query, filters=filters, limit=limit, sort=sort)


def hybrid_search(query: str, filters: dict = None, limit: int = 20) -> List[dict]:
    """Hybrid search combining textual and semantic results using RRF."""
    # Get results from both methods
    text_results = database.search_text(query, filters=filters, limit=limit * 2)
    semantic_results = embeddings.semantic_search(query, limit=limit * 2, filters=filters)

    # Reciprocal Rank Fusion
    rrf_scores = {}
    k = 60  # RRF constant

    # Separate storage: scores dict and docs dict
    scores = {}
    docs_store = {}

    # Score textual results
    for rank, doc in enumerate(text_results):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
        docs_store[doc_id] = doc

    # Score semantic results
    for rank, doc in enumerate(semantic_results):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
        docs_store[doc_id] = doc  # semantic has score, overwrite

    # Sort by RRF score
    doc_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    # Build result list
    results = []
    for doc_id in doc_ids[:limit]:
        doc = docs_store.get(doc_id, {})
        doc["score"] = round(scores[doc_id], 6)
        doc.pop("embedding", None)
        results.append(doc)

    return results
