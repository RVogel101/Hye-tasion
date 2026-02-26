"""
Hye-tasion entry point.
Run with:  python main.py
"""
import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("hye-tasion")


def main():
    from app.database import init_db
    from app.scheduler import create_scheduler

    # Initialise database tables
    logger.info("Initialising database…")
    init_db()

    # Start background scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Background scheduler started.")

    # Run the FastAPI server
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting Hye-tasion server on http://{host}:{port}")
    uvicorn.run("app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
