from __future__ import annotations

from typing import Any

from app.db import load_jobs
from app.schemas import PipelineState
from app.utils.text import normalize_text, profile_keywords


def match_jobs_by_profile_agent(state: PipelineState) -> PipelineState:
    profile_text = state.get("profile_text", "")
    keywords = profile_keywords(profile_text)

    if not keywords:
        return {"keywords": [], "matched_jobs": []}

    rows = load_jobs()
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        blob = normalize_text(f"{row['title']} {row['description']} {row['source_query']} {row['similar_term']}")
        score = sum(1 for kw in keywords if kw in blob)
        if score > 0:
            scored.append(
                (
                    score,
                    {
                        "id": row["id"],
                        "url": row["url"],
                        "title": row["title"],
                        "source_query": row["source_query"],
                        "similar_term": row["similar_term"],
                        "collected_at_utc": row["collected_at_utc"],
                        "score": score,
                    },
                )
            )

    scored.sort(key=lambda item: (item[0], item[1]["collected_at_utc"], item[1]["id"]), reverse=True)
    limit = state.get("max_jobs", 20)
    matched_jobs = [item[1] for item in scored[:limit]]

    return {"keywords": keywords, "matched_jobs": matched_jobs}
