"""Compatibility entrypoint for local execution (`uvicorn main:app`)."""

from app.agents.ingestion import extract_json_and_store_db_agent as _agent_extract_json_and_store_db
from app.agents.matching import match_jobs_by_profile_agent as _agent_match_jobs_by_profile
from app.main import app
from app.utils.text import build_similar_terms as _build_similar_terms
from app.utils.text import normalize_text as _normalize_text
from app.utils.url import is_same_domain as _is_same_domain

__all__ = [
    "app",
    "_agent_extract_json_and_store_db",
    "_agent_match_jobs_by_profile",
    "_build_similar_terms",
    "_normalize_text",
    "_is_same_domain",
]
