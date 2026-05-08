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

    # Score textual results
    for rank, doc in enumerate(text_results):
        doc_id = doc["id"]
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
        if doc_id not in rrf_scores or "_doc" not in rrf_scores:
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0)
        # Store the doc data
        if f"_doc_{doc_id}" not in rrf_scores:
            rrf_scores[f"_doc_{doc_id}"] = doc

    # Score semantic results
    for rank, doc in enumerate(semantic_results):
        doc_id = doc["id"]
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
        # Store/overwrite doc data (semantic has score)
        rrf_scores[f"_doc_{doc_id}"] = doc

    # Sort by RRF score
    doc_ids = [key for key in rrf_scores if not key.startswith("_doc_")]
    doc_ids.sort(key=lambda x: rrf_scores[x], reverse=True)

    # Build result list
    results = []
    for doc_id in doc_ids[:limit]:
        doc = rrf_scores.get(f"_doc_{doc_id}", {})
        doc["score"] = round(rrf_scores[doc_id], 6)
        doc.pop("embedding", None)
        results.append(doc)

    return results
