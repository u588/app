# supply_chain/src/visualizer.py
import plotly.graph_objects as go
from pathlib import Path
from typing import Dict, Any

class SankeyRenderer:
    """可视化渲染器：基于 Plotly 6.7 生成交互式关系图"""
    
    def __init__(self, width: int = 1500, height: int = 950, theme: str = "plotly_dark"):
        self.width, self.height, self.theme = width, height, theme

    def render(self, graph_data: Dict[str, Any], output_path: str | Path) -> None:
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=18, thickness=14,
                line=dict(color="black", width=0.6),
                label=graph_data["nodes"]["label"],
                color=graph_data["nodes"]["color"],
                hovertemplate="<b>%{label}</b><extra></extra>"
            ),
            link=dict(
                source=graph_data["links"]["source"],
                target=graph_data["links"]["target"],
                value=graph_data["links"]["value"],
                color=graph_data["links"]["color"],
                hovertemplate=graph_data["links"]["hover"] + "<extra></extra>"
            )
        )])

        fig.update_layout(
            title_text="🔗 十五五十大赛道：产业链与标的关系图谱 (含供应链/竞争/协同)",
            font=dict(size=12, family="Microsoft YaHei, sans-serif"),
            margin=dict(l=30, r=30, t=70, b=30),
            width=self.width, height=self.height,
            template=self.theme,
            annotations=[
                dict(text="🟦 宏观流向 | 🟢 供应链供应 | 🔴 同业竞争 | 🟡 产线协同",
                     x=0.01, y=1.02, xref="paper", yref="paper",
                     showarrow=False, font=dict(size=11, color="#AAAAAA"))
            ]
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(out)
        print(f"✅ 交互式图谱已导出至: {out.absolute()}")