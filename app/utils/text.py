from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def safe_term_slug(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize_text(term)).strip("-") or "term"


def build_similar_terms(query: str, limit: int) -> list[str]:
    normalized = normalize_text(query)
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
        t = normalize_text(term)
        if not t or t in seen:
            continue
        seen.add(t)
        deduped.append(t)
        if len(deduped) >= limit:
            break
    return deduped


def profile_keywords(profile_text: str, limit: int = 12) -> list[str]:
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

    tokens = [t for t in re.split(r"\W+", normalize_text(profile_text)) if len(t) > 2 and t not in stopwords]
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
