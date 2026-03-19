from __future__ import annotations

from app.db import insert_jobs_from_json
from app.schemas import PipelineState
from app.services.scraper import scrape_terms_and_save_json
from app.utils.text import build_similar_terms


async def scrape_and_save_json_agent(state: PipelineState) -> PipelineState:
    base_url = state["base_url"]
    query = state["job_description"]
    max_jobs = state.get("max_jobs", 10)
    limit = state.get("similar_terms_limit", 4)

    similar_terms = build_similar_terms(query, limit)
    json_files = await scrape_terms_and_save_json(base_url, query, similar_terms, max_jobs)

    return {"similar_terms": similar_terms, "json_files": json_files}


def extract_json_and_store_db_agent(state: PipelineState) -> PipelineState:
    inserted_rows = insert_jobs_from_json(state.get("json_files", []))
    return {"inserted_rows": inserted_rows}
