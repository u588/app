#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ConfidenceGauge：置信度仪表盘组件
功能：
  - 可视化置信度因子 (0.98~1.02)
  - 显示原始得分 + 等级
  - 支持分项得分展示
"""

import plotly.graph_objects as go
from typing import Dict, Optional
from ..utils.color_scales import CONFIDENCE_LEVEL_COLORS

def create_confidence_gauge(
    factor: float,
    score: float,
    level: str,
    breakdown: Optional[Dict] = None
) -> go.Figure:
    """
    创建置信度仪表盘
    
    参数:
        factor: 置信度因子 (0.98~1.02)
        score: 原始得分 (0~1)
        level: 等级 ('high'/'normal'/'low')
        breakdown: 分项得分 {data_quality, consistency, strength}
    
    返回:
        Plotly Figure
    """
    # 颜色映射
    color = CONFIDENCE_LEVEL_COLORS.get(level, '#7f7f7f')
    
    # 1. 创建主仪表盘
    fig = go.Figure(go.Indicator(
        mode='gauge+number+delta',
        value=factor,
        domain={'x': [0, 1], 'y': [0.3, 1]},
        title={'text': f"置信度因子 ({level})"},
        number={'font': {'size': 28}},
        delta={'reference': 1.0, 'increasing': {'color': 'green'}, 'decreasing': {'color': 'red'}},
        gauge={
            'axis': {'range': [0.98, 1.02], 'tickformat': '.3f'},
            'bar': {'color': color},
            'steps': [
                {'range': [0.98, 0.99], 'color': 'rgba(214,39,40,0.2)'},
                {'range': [0.99, 1.01], 'color': 'rgba(31,119,180,0.1)'},
                {'range': [1.01, 1.02], 'color': 'rgba(44,160,44,0.2)'}
            ],
            'threshold': {
                'line': {'color': 'black', 'width': 2},
                'thickness': 0.75,
                'value': 1.0
            }
        }
        # ✅ 修复：移除 hovertemplate 和 customdata，Indicator 不支持这些属性
    ))
    
    # 2. 添加分项得分条形图（底部）
    # if breakdown:
    #     # 提取分项
    #     dims = ['data_quality', 'consistency', 'strength']
    #     values = [breakdown.get(d, 0.5) for d in dims]
    #     colors = ['#1f77b4', '#ff7f0e', '#2ca02c']  # 蓝/橙/绿
        
        # fig.add_trace(go.Bar(
        #     x=dims,
        #     y=values,
        #     marker_color=colors,
        #     name='分项得分',
        #     text=[f'{v:.2f}' for v in values],
        #     textposition='auto',
        #     hovertemplate='<b>%{x}</b><br>得分：%{y:.2f}<extra></extra>'
        # ))
        
        # # 添加综合得分环形图（叠加）
        # fig.add_trace(go.Indicator(
        #     mode='gauge+number',
        #     value=score,
        #     domain={'x': [0.2, 0.8], 'y': [0, 0.4]},
        #     gauge={
        #         'axis': {'range': [0, 1], 'visible': False},
        #         'bar': {'color': color},
        #         # 'bar': {'color': color, 'opacity': 0.3},
        #         'shape': 'bullet'
        #     },
        #     number={'font': {'size': 16}},
        #     title={'text': '综合得分'}
        #     # ✅ 修复：移除 hovertemplate
        # ))
    
    # 布局优化
    fig.update_layout(
        height=400,
        margin=dict(l=30, r=30, t=50, b=30),
        showlegend=False,
        # yaxis={'visible': False},
        # yaxis2={'visible': False}
    )
    
    return fig