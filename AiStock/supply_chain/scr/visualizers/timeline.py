import plotly.graph_objects as go
from typing import Dict, Any
from .base import BaseVisualizer

class TimelineVisualizer(BaseVisualizer):
    def render(self, timeline_data: Dict[str, Any]) -> go.Figure:
        phases = timeline_data.get("phases", [])
        names = [p["name"] for p in phases]
        colors = [p.get("color", "#888888") for p in phases]
        descs = [p.get("description", "") for p in phases]
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=names, y=[1]*len(names), text=descs, textposition='auto',
            marker_color=colors, name="阶段", hoverinfo='text+name'
        ))
        fig.update_layout(
            title="<b>十五五</b> 产业发展时间线",
            height=300, width=1200, barmode='stack',
            xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False, showgrid=False)
        )
        return fig