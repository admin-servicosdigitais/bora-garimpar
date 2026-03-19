from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urljoin, urlparse

from fastapi import FastAPI, HTTPException
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, HttpUrl
from playwright.async_api import Browser, Page, async_playwright

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "jobs.db"

app = FastAPI(title="Job Scraper + LangGraph API", version="0.2.0")


class ScrapeRequest(BaseModel):
    base_url: HttpUrl = Field(..., description="URL base do site de vagas")
    job_description: str = Field(..., min_length=3, description="Descrição/termo da vaga")
    max_jobs: int = Field(default=10, ge=1, le=50)


class PipelineRequest(ScrapeRequest):
    similar_terms_limit: int = Field(default=4, ge=1, le=10)


class ProfileRequest(BaseModel):
    profile_text: str = Field(..., min_length=8, description="Resumo do perfil profissional")
    limit: int = Field(default=20, ge=1, le=100)


class JobResult(BaseModel):
    url: str
    title: str
    description: str


class ScrapeResponse(BaseModel):
    base_url: str
    query: str
    count: int
    output_file: str
    jobs: list[JobResult]


class PipelineResponse(BaseModel):
    base_url: str
    query: str
    similar_terms: list[str]
    json_files: list[str]
    inserted_rows: int


class MatchResponse(BaseModel):
    profile_text: str
    keywords: list[str]
    count: int
    jobs: list[dict[str, Any]]


class PipelineState(TypedDict, total=False):
    base_url: str
    job_description: str
    max_jobs: int
    similar_terms_limit: int
    profile_text: str
    similar_terms: list[str]
    json_files: list[str]
    inserted_rows: int
    keywords: list[str]
    matched_jobs: list[dict[str, Any]]


def _initialize_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                source_query TEXT NOT NULL,
                similar_term TEXT NOT NULL,
                collected_at_utc TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


_initialize_db()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _is_same_domain(base_url: str, candidate_url: str) -> bool:
    return urlparse(base_url).netloc == urlparse(candidate_url).netloc


def _safe_term_slug(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _normalize_text(term)).strip("-") or "term"


def _build_similar_terms(query: str, limit: int) -> list[str]:
    normalized = _normalize_text(query)
    synonyms: dict[str, list[str]] = {
        "engenheiro": ["developer", "software engineer", "backend"],
        "desenvolvedor": ["developer", "programador", "software engineer"],
        "dados": ["data", "analytics", "bi"],
        "frontend": ["front-end", "react", "javascript"],
        "backend": ["back-end", "api", "python"],
        "python": ["django", "fastapi", "backend"],
        "produto": ["product", "product manager", "pm"],
    }

    parts = [p for p in re.split(r"\W+", normalized) if p]
    candidates: list[str] = [normalized]

    for part in parts:
        candidates.extend(synonyms.get(part, []))

    if len(parts) > 1:
        candidates.extend([" ".join(parts[:2]), " ".join(parts[-2:])])

    deduped: list[str] = []
    seen: set[str] = set()
    for term in candidates:
        t = _normalize_text(term)
        if not t or t in seen:
            continue
        seen.add(t)
        deduped.append(t)
        if len(deduped) >= limit:
            break
    return deduped


async def _collect_candidate_links(page: Page, base_url: str, query: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    normalized_query = _normalize_text(query)

    anchors = page.locator("a[href]")
    total = await anchors.count()

    for i in range(total):
        anchor = anchors.nth(i)
        href = await anchor.get_attribute("href")
        text = (await anchor.inner_text()) or ""
        if not href:
            continue

        absolute_url = urljoin(base_url, href)
        if not absolute_url.startswith(("http://", "https://")):
            continue
        if absolute_url in seen or not _is_same_domain(base_url, absolute_url):
            continue

        target_text = _normalize_text(text)
        target_href = _normalize_text(absolute_url)
        if normalized_query in target_text or normalized_query in target_href:
            links.append((absolute_url, text.strip() or "Sem título"))
            seen.add(absolute_url)

    return links


async def _extract_job_description(page: Page) -> str:
    selectors = [
        "main",
        "article",
        "section",
        "[class*='description']",
        "[class*='job']",
        "body",
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        if await locator.count() == 0:
            continue
        text = (await locator.inner_text()).strip()
        if len(text) > 120:
            return re.sub(r"\s+", " ", text)
    body_text = await page.inner_text("body")
    return re.sub(r"\s+", " ", body_text).strip()


async def _scrape_jobs_for_query(browser: Browser, base_url: str, query: str, max_jobs: int) -> list[JobResult]:
    page = await browser.new_page()
    try:
        await page.goto(base_url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)
        candidates = await _collect_candidate_links(page, base_url, query)

        if not candidates:
            return []

        jobs: list[JobResult] = []
        for url, fallback_title in candidates[:max_jobs]:
            detail = await browser.new_page()
            try:
                await detail.goto(url, wait_until="domcontentloaded", timeout=45000)
                await detail.wait_for_timeout(1200)
                title = await detail.title()
                description = await _extract_job_description(detail)
                jobs.append(
                    JobResult(
                        url=url,
                        title=title.strip() or fallback_title,
                        description=description,
                    )
                )
            finally:
                await detail.close()

        return jobs
    finally:
        await page.close()


async def _agent_scrape_and_save_json(state: PipelineState) -> PipelineState:
    base_url = state["base_url"]
    query = state["job_description"]
    max_jobs = state.get("max_jobs", 10)
    limit = state.get("similar_terms_limit", 4)

    similar_terms = _build_similar_terms(query, limit)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_domain = urlparse(base_url).netloc.replace(":", "_")

    json_files: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for term in similar_terms:
                jobs = await _scrape_jobs_for_query(browser, base_url, term, max_jobs)
                filename = OUTPUT_DIR / f"jobs_{safe_domain}_{_safe_term_slug(term)}_{timestamp}.json"
                payload: dict[str, Any] = {
                    "base_url": base_url,
                    "query": query,
                    "similar_term": term,
                    "created_at_utc": timestamp,
                    "count": len(jobs),
                    "jobs": [job.model_dump() for job in jobs],
                }
                filename.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                json_files.append(str(filename))
        finally:
            await browser.close()

    return {"similar_terms": similar_terms, "json_files": json_files}


def _agent_extract_json_and_store_db(state: PipelineState) -> PipelineState:
    json_files = state.get("json_files", [])
    inserted_rows = 0

    conn = sqlite3.connect(DB_PATH)
    try:
        for file_path in json_files:
            content = json.loads(Path(file_path).read_text(encoding="utf-8"))
            source_query = content.get("query", "")
            similar_term = content.get("similar_term", "")
            created_at = content.get("created_at_utc", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))

            for job in content.get("jobs", []):
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO jobs (url, title, description, source_query, similar_term, collected_at_utc)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.get("url", ""),
                        job.get("title", "Sem título"),
                        job.get("description", ""),
                        source_query,
                        similar_term,
                        created_at,
                    ),
                )
                inserted_rows += cursor.rowcount
        conn.commit()
    finally:
        conn.close()

    return {"inserted_rows": inserted_rows}


def _profile_keywords(profile_text: str, limit: int = 12) -> list[str]:
    stopwords = {
        "de",
        "da",
        "do",
        "das",
        "dos",
        "em",
        "para",
        "com",
        "que",
        "por",
        "uma",
        "um",
        "na",
        "no",
        "e",
        "a",
        "o",
    }

    tokens = [t for t in re.split(r"\W+", _normalize_text(profile_text)) if len(t) > 2 and t not in stopwords]
    dedup: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        dedup.append(token)
        if len(dedup) >= limit:
            break
    return dedup


def _agent_match_jobs_by_profile(state: PipelineState) -> PipelineState:
    profile_text = state.get("profile_text", "")
    keywords = _profile_keywords(profile_text)

    if not keywords:
        return {"keywords": [], "matched_jobs": []}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, url, title, description, source_query, similar_term, collected_at_utc
            FROM jobs
            ORDER BY collected_at_utc DESC, id DESC
            """
        ).fetchall()
    finally:
        conn.close()

    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        blob = _normalize_text(f"{row['title']} {row['description']} {row['source_query']} {row['similar_term']}")
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


def _build_ingestion_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("scrape_agent", _agent_scrape_and_save_json)
    graph.add_node("extract_store_agent", _agent_extract_json_and_store_db)
    graph.add_edge(START, "scrape_agent")
    graph.add_edge("scrape_agent", "extract_store_agent")
    graph.add_edge("extract_store_agent", END)
    return graph.compile()


def _build_matching_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("match_agent", _agent_match_jobs_by_profile)
    graph.add_edge(START, "match_agent")
    graph.add_edge("match_agent", END)
    return graph.compile()


ingestion_graph = _build_ingestion_graph()
matching_graph = _build_matching_graph()


@app.post("/jobs/scrape", response_model=ScrapeResponse)
async def scrape_jobs(req: ScrapeRequest) -> ScrapeResponse:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            jobs = await _scrape_jobs_for_query(browser, str(req.base_url), req.job_description, req.max_jobs)
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


@app.post("/pipeline/ingest", response_model=PipelineResponse)
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


@app.post("/pipeline/match", response_model=MatchResponse)
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
