from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.async_api import Browser, Page, async_playwright

from app.config import OUTPUT_DIR
from app.schemas import JobResult
from app.utils.text import safe_term_slug, normalize_text
from app.utils.url import is_same_domain


async def collect_candidate_links(page: Page, base_url: str, query: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    normalized_query = normalize_text(query)

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
        if absolute_url in seen or not is_same_domain(base_url, absolute_url):
            continue

        target_text = normalize_text(text)
        target_href = normalize_text(absolute_url)
        if normalized_query in target_text or normalized_query in target_href:
            links.append((absolute_url, text.strip() or "Sem título"))
            seen.add(absolute_url)

    return links


async def extract_job_description(page: Page) -> str:
    selectors = ["main", "article", "section", "[class*='description']", "[class*='job']", "body"]
    for selector in selectors:
        locator = page.locator(selector).first
        if await locator.count() == 0:
            continue
        text = (await locator.inner_text()).strip()
        if len(text) > 120:
            return re.sub(r"\s+", " ", text)
    body_text = await page.inner_text("body")
    return re.sub(r"\s+", " ", body_text).strip()


async def scrape_jobs_for_query(browser: Browser, base_url: str, query: str, max_jobs: int) -> list[JobResult]:
    page = await browser.new_page()
    try:
        await page.goto(base_url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)
        candidates = await collect_candidate_links(page, base_url, query)

        if not candidates:
            return []

        jobs: list[JobResult] = []
        for url, fallback_title in candidates[:max_jobs]:
            detail = await browser.new_page()
            try:
                await detail.goto(url, wait_until="domcontentloaded", timeout=45000)
                await detail.wait_for_timeout(1200)
                title = await detail.title()
                description = await extract_job_description(detail)
                jobs.append(JobResult(url=url, title=title.strip() or fallback_title, description=description))
            finally:
                await detail.close()

        return jobs
    finally:
        await page.close()


async def scrape_terms_and_save_json(base_url: str, query: str, similar_terms: list[str], max_jobs: int) -> list[str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_domain = urlparse(base_url).netloc.replace(":", "_")
    json_files: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for term in similar_terms:
                jobs = await scrape_jobs_for_query(browser, base_url, term, max_jobs)
                filename = OUTPUT_DIR / f"jobs_{safe_domain}_{safe_term_slug(term)}_{timestamp}.json"
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

    return json_files
