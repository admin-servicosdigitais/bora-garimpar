from pathlib import Path

OUTPUT_DIR = Path("outputs")
DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "jobs.db"


for directory in (OUTPUT_DIR, DATA_DIR):
    directory.mkdir(parents=True, exist_ok=True)
