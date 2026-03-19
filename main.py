from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from playwright.async_api import Browser, Page, async_playwright

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Job Scraper API", version="0.1.0")


class ScrapeRequest(BaseModel):
    base_url: HttpUrl = Field(..., description="URL base do site de vagas")
    job_description: str = Field(..., min_length=3, description="Descrição/termo da vaga")
    max_jobs: int = Field(default=10, ge=1, le=50)


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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _is_same_domain(base_url: str, candidate_url: str) -> bool:
    return urlparse(base_url).netloc == urlparse(candidate_url).netloc


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


async def _scrape_jobs(browser: Browser, req: ScrapeRequest) -> list[JobResult]:
    page = await browser.new_page()
    try:
        await page.goto(str(req.base_url), wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)
        candidates = await _collect_candidate_links(page, str(req.base_url), req.job_description)

        if not candidates:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Nenhuma vaga foi encontrada com esse termo na página inicial. "
                    "Tente um termo mais genérico ou uma URL de página de vagas."
                ),
            )

        jobs: list[JobResult] = []
        for url, fallback_title in candidates[: req.max_jobs]:
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


@app.post("/jobs/scrape", response_model=ScrapeResponse)
async def scrape_jobs(req: ScrapeRequest) -> ScrapeResponse:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            jobs = await _scrape_jobs(browser, req)
        finally:
            await browser.close()

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
