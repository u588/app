import logging
from pathlib import Path

def setup_logging(level: str = "INFO", fmt: str = "%(asctime)s [%(levelname)s] %(message)s"):
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format=fmt)
    return logging.getLogger("fifteen_five")

def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p