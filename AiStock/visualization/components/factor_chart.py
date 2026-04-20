#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FactorChart：因子分解可视化组件
"""
import plotly.graph_objects as go
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def create_factor_decomposition_chart(result: Dict[str, Any], config: Optional[Dict] = None) -> go.Figure:
    config = config or {}
    factors = result.get('factors', {})
    if not factors:
        logger.warning("⚠️ 因子数据为空")
        return go.Figure()
    
    names = ['技术面', '基本面', '宏观面', '综合']
    values = [factors.get('technical', 1.0), factors.get('fundamental', 1.0), 
              factors.get('macro', 1.0), factors.get('composite', 1.0)]
    
    color_map = config.get('color_map', {'技术面': '#7f7f7f', '基本面': '#ff7f0e', '宏观面': '#9467bd', '综合': '#1f77b4'})
    colors = [color_map.get(n, '#1f77b4') for n in names]
    
    fig = go.Figure(data=[go.Bar(
        x=names, y=values, marker_color=colors,
        text=[f"{v:.3f}" if config.get('show_values', True) else '' for v in values],
        textposition='auto', name='调整因子'
    )])
    
    fig.update_layout(
        title=config.get('title', f"📊 因子分解 ({result.get('code', '')})"),
        xaxis_title='因子类型', yaxis_title='调整系数',
        yaxis=dict(range=[0.85, 1.15]), height=400, hovermode='closest',
        template=config.get('template', 'plotly_white')
    )
    return fig