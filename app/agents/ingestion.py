from __future__ import annotations

from app.db import insert_jobs_from_json
from app.schemas import PipelineState
from app.services.scraper import scrape_terms_and_save_json
from app.utils.text import build_similar_terms


async def scrape_and_save_json_agent(state: PipelineState) -> PipelineState:
    base_url = state["base_url"]
    query = state["job_description"]
    max_jobs = state.get("max_jobs", 15)
    min_jobs = state.get("min_jobs", 10)
    max_attempts = state.get("max_attempts", 8)
    limit = state.get("similar_terms_limit", 4)

    similar_terms = build_similar_terms(query, limit)
    json_files = await scrape_terms_and_save_json(
        base_url=base_url,
        query=query,
        similar_terms=similar_terms,
        max_jobs=max_jobs,
        min_jobs=min_jobs,
        max_attempts=max_attempts,
    )

    return {"similar_terms": similar_terms, "json_files": json_files}


def extract_json_and_store_db_agent(state: PipelineState) -> PipelineState:
    inserted_rows = insert_jobs_from_json(state.get("json_files", []))
    return {"inserted_rows": inserted_rows}
