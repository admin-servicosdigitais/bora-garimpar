from fastapi import FastAPI

from app.api.routes import router
from app.db import initialize_db


def create_app() -> FastAPI:
    initialize_db()
    api = FastAPI(title="Job Scraper + LangGraph API", version="1.0.0")
    api.include_router(router)
    return api


app = create_app()
