#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RiskChart：风险矩阵可视化组件
"""
import plotly.express as px
import pandas as pd
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def create_risk_matrix_chart(results: List[Dict[str, Any]], config: Optional[Dict] = None) -> px.scatter:
    config = config or {}
    if not results:
        return px.scatter()
    
    df = pd.DataFrame([{
        '代码': r['code'], '名称': r.get('name', '未知'),
        '波动率': float(r.get('volatility', 0.2)), '盈亏比': float(r['scores']['pl_ratio']),
        '建议': r['recommendation']
    } for r in results])
    
    color_map = {'强烈推荐': '#2ca02c', '推荐': '#1f77b4', '观望': '#ff7f0e', '谨慎': '#d62728'}
    fig = px.scatter(df, x='波动率', y='盈亏比', color='建议', color_discrete_map=color_map,
                     hover_name='名称', title='⚠️ 风险收益矩阵', opacity=0.8)
    
    if config.get('quadrant_lines', True):
        fig.add_vline(x=0.25, line_dash='dot', line_color='red', annotation_text='高波动阈值')
        fig.add_hline(y=1.5, line_dash='dot', line_color='green', annotation_text='低盈亏比阈值')
    
    fig.update_layout(height=450, hovermode='closest', template=config.get('template', 'plotly_white'))
    return fig