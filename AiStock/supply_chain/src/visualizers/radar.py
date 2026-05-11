import plotly.graph_objects as go
from typing import Dict, Any
from .base import BaseVisualizer

class RadarVisualizer(BaseVisualizer):
    def render(self, data: Dict[str, Any]) -> go.Figure:
        chains = data.get("supply_chains", {})
        names = [v["name"] for v in chains.values()]
        policy = [v["policy_score"] for v in chains.values()]
        certainty = [v["certainty_score"] for v in chains.values()]
        
        # 闭合雷达图
        names += [names[0]]
        policy += [policy[0]]
        certainty += [certainty[0]]
        
        colors = self.theme.get("colors", {})
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=policy, theta=names, fill='toself', name='政策契合度',
            line_color=colors.get("primary", "#2563eb"), fillcolor='rgba(37, 99, 235, 0.2)'
        ))
        fig.add_trace(go.Scatterpolar(
            r=certainty, theta=names, fill='toself', name='投资确定性',
            line_color=colors.get("secondary", "#f59e0b"), fillcolor='rgba(245, 158, 11, 0.2)'
        ))
        
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 5], tickvals=[0,1,2,3,4,5])),
            showlegend=True,
            title="<b>十大投资方向</b> 综合评估雷达图",
            height=700, width=900
        )
        return fig