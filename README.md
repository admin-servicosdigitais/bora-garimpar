# Job Scraper API (Playwright + LangGraph + FastAPI)

API REST local com pipeline de **3 agentes via LangGraph**:

1. **Agente de Garimpo (Playwright)**
   - Entra no site de vagas
   - Pesquisa o termo principal e termos similares
   - Salva cada coleta em JSON na pasta `outputs/`
2. **Agente de Estruturação/ETL**
   - Lê os JSONs gerados
   - Estrutura e persiste os dados no banco SQLite (`data/jobs.db`)
3. **Agente de Matching de Perfil**
   - Recebe o perfil de um profissional
   - Busca no banco vagas com maior aderência ao perfil

---

## 1) Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## 2) Executar a API

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 3) Endpoints

### `POST /jobs/scrape`
Scrape direto (modo simples) para um termo.

Payload:

```json
{
  "base_url": "https://boards.greenhouse.io/openai",
  "job_description": "software",
  "max_jobs": 5
}
```

### `POST /pipeline/ingest`
Executa os **agentes 1 e 2** via LangGraph.

Payload:

```json
{
  "base_url": "https://boards.greenhouse.io/openai",
  "job_description": "engenheiro de software",
  "max_jobs": 5,
  "similar_terms_limit": 4
}
```

Resposta (exemplo):

```json
{
  "base_url": "https://boards.greenhouse.io/openai",
  "query": "engenheiro de software",
  "similar_terms": ["engenheiro de software", "developer", "software engineer", "backend"],
  "json_files": [
    "outputs/jobs_boards.greenhouse.io_engenheiro-de-software_20260319T000000Z.json"
  ],
  "inserted_rows": 10
}
```

### `POST /pipeline/match`
Executa o **agente 3** via LangGraph para matching por perfil.

Payload:

```json
{
  "profile_text": "Engenheiro backend Python com FastAPI, APIs REST e microsserviços",
  "limit": 20
}
```

Resposta (exemplo):

```json
{
  "profile_text": "Engenheiro backend Python com FastAPI, APIs REST e microsserviços",
  "keywords": ["engenheiro", "backend", "python", "fastapi", "apis", "rest", "microsserviços"],
  "count": 3,
  "jobs": [
    {
      "id": 10,
      "url": "https://...",
      "title": "Backend Python Engineer",
      "source_query": "engenheiro de software",
      "similar_term": "backend",
      "collected_at_utc": "20260319T000000Z",
      "score": 4
    }
  ]
}
```

## 4) Observações

- O scraper é genérico e busca links (`a[href]`) no mesmo domínio com o termo na âncora/URL.
- Sites com login, anti-bot, paginação dinâmica ou lazy loading podem exigir ajustes específicos.
- Os JSONs são salvos em `outputs/` e o banco em `data/jobs.db`.
