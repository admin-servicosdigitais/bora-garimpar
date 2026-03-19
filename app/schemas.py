from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field, HttpUrl


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
