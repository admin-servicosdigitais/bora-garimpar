from pathlib import Path

from main import (
    _agent_extract_json_and_store_db,
    _agent_match_jobs_by_profile,
    _build_similar_terms,
    _is_same_domain,
    _normalize_text,
)


def test_normalize_text():
    assert _normalize_text("  Engenheiro   de Dados \n Senior ") == "engenheiro de dados senior"


def test_is_same_domain_true():
    assert _is_same_domain("https://careers.example.com/jobs", "https://careers.example.com/vaga/123")


def test_is_same_domain_false():
    assert not _is_same_domain("https://careers.example.com/jobs", "https://example.com/vaga/123")


def test_build_similar_terms_contains_original():
    terms = _build_similar_terms("desenvolvedor python", limit=5)
    assert terms[0] == "desenvolvedor python"
    assert len(terms) <= 5


def test_extract_and_match_flow(tmp_path: Path):
    json_file = tmp_path / "jobs.json"
    json_file.write_text(
        """
        {
          "query": "python",
          "similar_term": "backend",
          "created_at_utc": "20260319T000000Z",
          "jobs": [
            {
              "url": "https://example.com/jobs/1",
              "title": "Backend Python Engineer",
              "description": "API FastAPI e microsserviços"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    result = _agent_extract_json_and_store_db({"json_files": [str(json_file)]})
    assert result["inserted_rows"] in (0, 1)

    matched = _agent_match_jobs_by_profile({"profile_text": "Profissional Python FastAPI backend", "max_jobs": 5})
    assert "python" in matched["keywords"]
    assert isinstance(matched["matched_jobs"], list)
