from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from playwright.async_api import async_playwright

from app.config import OUTPUT_DIR
from app.graphs import ingestion_graph, matching_graph
from app.schemas import (
    MatchResponse,
    PipelineRequest,
    PipelineResponse,
    ProfileRequest,
    ScrapeRequest,
    ScrapeResponse,
)
from app.services.scraper import scrape_jobs_for_query

router = APIRouter()


@router.post("/jobs/scrape", response_model=ScrapeResponse)
async def scrape_jobs(req: ScrapeRequest) -> ScrapeResponse:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            jobs = await scrape_jobs_for_query(browser, str(req.base_url), req.job_description, req.max_jobs)
        finally:
            await browser.close()

    if not jobs:
        raise HTTPException(
            status_code=404,
            detail=(
                "Nenhuma vaga foi encontrada com esse termo na página inicial. "
                "Tente um termo mais genérico ou uma URL de página de vagas."
            ),
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_domain = urlparse(str(req.base_url)).netloc.replace(":", "_")
    filename = OUTPUT_DIR / f"jobs_{safe_domain}_{timestamp}.json"

    payload: dict[str, Any] = {
        "base_url": str(req.base_url),
        "query": req.job_description,
        "created_at_utc": timestamp,
        "count": len(jobs),
        "jobs": [job.model_dump() for job in jobs],
    }
    filename.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return ScrapeResponse(
        base_url=str(req.base_url),
        query=req.job_description,
        count=len(jobs),
        output_file=str(filename),
        jobs=jobs,
    )


@router.post("/pipeline/ingest", response_model=PipelineResponse)
async def run_ingestion_pipeline(req: PipelineRequest) -> PipelineResponse:
    final_state = await ingestion_graph.ainvoke(
        {
            "base_url": str(req.base_url),
            "job_description": req.job_description,
            "max_jobs": req.max_jobs,
            "similar_terms_limit": req.similar_terms_limit,
        }
    )

    return PipelineResponse(
        base_url=str(req.base_url),
        query=req.job_description,
        similar_terms=final_state.get("similar_terms", []),
        json_files=final_state.get("json_files", []),
        inserted_rows=final_state.get("inserted_rows", 0),
    )


@router.post("/pipeline/match", response_model=MatchResponse)
async def run_matching_pipeline(req: ProfileRequest) -> MatchResponse:
    final_state = matching_graph.invoke(
        {
            "profile_text": req.profile_text,
            "max_jobs": req.limit,
        }
    )

    matched_jobs = final_state.get("matched_jobs", [])
    return MatchResponse(
        profile_text=req.profile_text,
        keywords=final_state.get("keywords", []),
        count=len(matched_jobs),
        jobs=matched_jobs,
    )
