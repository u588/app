from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import logging

logger = logging.getLogger(__name__)

class IOManager:
    def __init__(self, base_dir: str = "output"):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        for sub in ["html", "excel", "images"]:
            (self.base / sub).mkdir(exist_ok=True)

    def save_html(self, fig: go.Figure, name: str) -> Path:
        path = self.base / "html" / f"{name}.html"
        fig.write_html(path, include_plotlyjs="cdn")
        logger.info(f"导出HTML: {path}")
        return path

    def save_excel(self, df: pd.DataFrame, name: str) -> Path:
        path = self.base / "excel" / f"{name}.xlsx"
        df.to_excel(path, index=False)
        logger.info(f"导出Excel: {path}")
        return path

    def save_png(self, fig: go.Figure, name: str) -> Path:
        path = self.base / "images" / f"{name}.png"
        fig.write_image(path)
        logger.info(f"导出PNG: {path}")
        return path