# Job Scraper API (Playwright + FastAPI)

API REST local para receber:
- `base_url` de um site de vagas
- `job_description` (termo da vaga)

A API usa **Playwright** para navegar no site, localizar vagas relacionadas ao termo informado, entrar em cada vaga, capturar:
- URL da vaga
- título
- descrição completa (texto da página)

E salva os resultados em um arquivo JSON na pasta `outputs/`.

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

## 3) Endpoint

### `POST /jobs/scrape`

Payload de exemplo:

```json
{
  "base_url": "https://boards.greenhouse.io/openai",
  "job_description": "software",
  "max_jobs": 5
}
```

Resposta (resumo):

```json
{
  "base_url": "https://boards.greenhouse.io/openai",
  "query": "software",
  "count": 3,
  "output_file": "outputs/jobs_boards.greenhouse.io_20260319T000000Z.json",
  "jobs": [
    {
      "url": "...",
      "title": "...",
      "description": "..."
    }
  ]
}
```

## 4) Observações

- O scraper é genérico e busca links (`a[href]`) na mesma base de domínio contendo o termo da vaga no texto/URL.
- Para sites com login, anti-bot ou carregamento avançado, podem ser necessários ajustes por site.
- Os JSONs gerados ficam em `outputs/`.
