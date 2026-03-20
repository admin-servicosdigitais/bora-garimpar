from __future__ import annotations

import json
import os
from typing import Any

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ModuleNotFoundError:  # pragma: no cover - ambiente sem dependência opcional
    boto3 = None

    class BotoCoreError(Exception):
        pass

    class ClientError(Exception):
        pass


class BedrockLLMService:
    def __init__(self) -> None:
        self.model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        self.region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        self._client = None

        if self.region and boto3 is not None:
            self._client = boto3.client("bedrock-runtime", region_name=self.region)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _invoke_json(self, prompt: str) -> dict[str, Any] | None:
        if not self._client:
            return None

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 700,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            response = self._client.invoke_model(modelId=self.model_id, body=json.dumps(payload))
            body = json.loads(response["body"].read())
            raw_text = "".join(part.get("text", "") for part in body.get("content", []) if part.get("type") == "text")
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(raw_text[start : end + 1])
        except (BotoCoreError, ClientError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
        return None

    def suggest_retry_terms(
        self,
        original_query: str,
        current_term: str,
        collected_count: int,
        attempt: int,
        limit: int = 4,
    ) -> list[str]:
        prompt = (
            "Você gera termos de busca para vagas de emprego. "
            "Responda JSON puro no formato {\"terms\": [..]} sem texto extra. "
            f"Busca original: {original_query}. Termo atual: {current_term}. "
            f"Tentativa: {attempt}. Total coletado: {collected_count}. "
            f"Retorne até {limit} termos curtos, variados e específicos para tentar novas buscas."
        )

        output = self._invoke_json(prompt) or {}
        terms = output.get("terms", []) if isinstance(output, dict) else []
        return [str(term).strip() for term in terms if str(term).strip()][:limit]

    def organize_job(self, title: str, url: str, description: str) -> dict[str, Any]:
        prompt = (
            "Você organiza dados de vaga. Retorne JSON puro com chaves: "
            "summary (string curta), key_points (array string), seniority (string), location (string), "
            "main_skills (array string). Sem texto extra. "
            f"Título: {title}\nURL: {url}\nDescrição: {description[:5000]}"
        )
        output = self._invoke_json(prompt)
        if not isinstance(output, dict):
            return {}

        key_points = output.get("key_points", [])
        skills = output.get("main_skills", [])
        return {
            "summary": str(output.get("summary", "")).strip(),
            "key_points": [str(item).strip() for item in key_points if str(item).strip()][:8],
            "seniority": str(output.get("seniority", "")).strip(),
            "location": str(output.get("location", "")).strip(),
            "main_skills": [str(item).strip() for item in skills if str(item).strip()][:12],
        }
