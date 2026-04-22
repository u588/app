#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ConfidenceGauge：置信度仪表盘组件
"""

import plotly.graph_objects as go
from ..utils.color_scales import CONFIDENCE_COLORSCALE

def create_confidence_gauge(
    factor: float,
    score: float,
    level: str
) -> go.Figure:
    """
    创建置信度仪表盘
    
    参数:
        factor: 置信度因子 (0.98~1.02)
        score: 原始得分 (0~1)
        level: 等级 ('high'/'normal'/'low')
    
    返回:
        Plotly Figure
    """
    # 颜色映射
    color_map = {'high': '#2ca02c', 'normal': '#1f77b4', 'low': '#d62728'}
    color = color_map.get(level, '#7f7f7f')
    
    # 创建仪表盘
    fig = go.Figure(go.Indicator(
        mode='gauge+number+delta',
        value=factor,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"置信度因子 ({level})"},
        number={'font': {'size': 28}},
        delta={'reference': 1.0, 'increasing': {'color': 'green'}, 'decreasing': {'color': 'red'}},
        gauge={
            'axis': {'range': [0.98, 1.02], 'tickformat': '.3f'},
            'bar': {'color': color},
            'steps': [
                {'range': [0.98, 0.99], 'color': 'lightcoral'},
                {'range': [0.99, 1.01], 'color': 'lightyellow'},
                {'range': [1.01, 1.02], 'color': 'lightgreen'}
            ],
            'threshold': {
                'line': {'color': 'black', 'width': 2},
                'thickness': 0.75,
                'value': 1.0
            }
        },
        hovertemplate='<b>置信度因子</b><br>%{value:.3f}<br>原始得分：%{customdata[0]:.1%}<extra></extra>',
        customdata=[score]
    ))
    
    # 添加得分环形图（叠加）
    fig.add_trace(go.Indicator(
        mode='gauge+number',
        value=score,
        domain={'x': [0.2, 0.8], 'y': [0.2, 0.8]},
        gauge={
            'axis': {'range': [0, 1], 'visible': False},
            'bar': {'color': color, 'opacity': 0.3},
            'shape': 'bullet'
        },
        number={'font': {'size': 16}},
        hovertemplate='<b>原始得分</b><br>%{value:.1%}<extra></extra>'
    ))
    
    fig.update_layout(
        height=350,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig