import plotly.graph_objects as go
from typing import Dict, Any

class BaseVisualizer:
    def __init__(self, theme_cfg: Dict[str, Any]):
        self.theme = theme_cfg
        
    def _apply_layout(self, fig: go.Figure, title: str) -> go.Figure:
        fig.update_layout(
            title_text=title,
            font_family=self.theme.get("font_family", "Microsoft YaHei, sans-serif"),
            paper_bgcolor=self.theme.get("colors", {}).get("background", "white"),
            plot_bgcolor=self.theme.get("colors", {}).get("background", "white"),
            margin=dict(l=20, r=20, t=60, b=20),
            height=800,
            width=1200
        )
        return fig