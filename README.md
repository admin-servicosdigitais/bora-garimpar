# Job Scraper API (Playwright + LangGraph + FastAPI)

API REST local com pipeline de **3 agentes via LangGraph** em arquitetura modular:

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

## Arquitetura

```text
app/
  api/routes.py           # Endpoints HTTP e contratos de entrada/saída
  agents/                 # Nós do grafo (orquestração por responsabilidade)
  services/scraper.py     # Coleta Playwright e serialização JSON
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

## 2) Executar a API

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 3) Endpoints

### `POST /jobs/scrape`
Scrape direto (modo simples) para um termo.

### `POST /pipeline/ingest`
Executa os **agentes 1 e 2** via LangGraph.

### `POST /pipeline/match`
Executa o **agente 3** via LangGraph para matching por perfil.

## 4) Observações

- O scraper é genérico e busca links (`a[href]`) no mesmo domínio com o termo na âncora/URL.
- Sites com login, anti-bot, paginação dinâmica ou lazy loading podem exigir ajustes específicos.
- Os JSONs são salvos em `outputs/` e o banco em `data/jobs.db`.
