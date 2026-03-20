# Job Scraper API (Playwright + LangGraph + FastAPI + Bedrock)

API REST local com pipeline de **3 agentes via LangGraph** em arquitetura modular:

1. **Agente de Garimpo Autônomo (Playwright + LLM)**
   - Entra no site de vagas
   - Testa o termo principal e termos similares
   - Faz novas tentativas automaticamente (tentativa e erro)
   - Usa LLM para sugerir novos termos quando o volume ainda não chegou ao mínimo
   - Objetivo padrão: buscar **no mínimo 10 vagas únicas**
2. **Agente de Estruturação/ETL**
   - Lê os JSONs gerados
   - Estrutura e persiste os dados no banco SQLite (`data/jobs.db`)
3. **Agente de Matching de Perfil**
   - Recebe o perfil de um profissional
   - Busca no banco vagas com maior aderência ao perfil

---

## Arquitetura

```text
app/
  api/routes.py           # Endpoints HTTP e contratos de entrada/saída
  agents/                 # Nós do grafo (orquestração por responsabilidade)
  services/scraper.py     # Coleta Playwright + retries autônomos + serialização JSON
  services/llm_bedrock.py # Sugestão de termos e estruturação por LLM (AWS Bedrock)
  db.py                   # Persistência SQLite
  graphs.py               # Construção dos grafos LangGraph
  schemas.py              # Modelos Pydantic e estado da pipeline
  utils/                  # Funções utilitárias puras
main.py                   # Entrypoint compatível (uvicorn main:app)
```

## 1) Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## 2) Configurar AWS Bedrock (opcional, recomendado)

Se configurado, a LLM passa a:
- sugerir termos para novas tentativas de busca;
- organizar campos enriquecidos no JSON (`metadata`), incluindo resumo e pontos-chave da vaga.

```bash
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
# e configure suas credenciais AWS (profile, vars, ou IAM role)
```

Sem Bedrock configurado, o scraper continua funcionando com fallback sem LLM.

## 3) Executar a API

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 4) Endpoints

### `POST /jobs/scrape`
Scrape direto para um termo e salva resultado JSON.

### `POST /pipeline/ingest`
Executa os **agentes 1 e 2** via LangGraph.

Novos parâmetros de controle no payload:
- `min_jobs` (default: 10)
- `max_attempts` (default: 8)

### `POST /pipeline/match`
Executa o **agente 3** via LangGraph para matching por perfil.

## 5) Observações

- O agente de scraping tenta preencher campos de busca na página (`input[type=search]`, placeholders e variações) antes de extrair links.
- Sites com login, anti-bot, paginação dinâmica ou lazy loading podem exigir ajustes específicos.
- Os JSONs são salvos em `outputs/` e o banco em `data/jobs.db`.
