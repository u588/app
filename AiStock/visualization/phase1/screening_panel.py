#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ScreeningPanel：筛选结果面板组件
功能：
  - 可视化筛选条件 + 结果对比
  - 支持多条件组合展示
  - 交互式筛选调整
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict, List, Optional, Any

def create_screening_panel(
    recommended: List[Dict],
    all_results: List[Dict],
    criteria: Optional[Dict] = None,
    config: Optional[Dict] = None
) -> go.Figure:
    """
    创建筛选结果面板
    
    参数:
        recommended: 筛选后的推荐标的
        all_results: 全部计算结果
        criteria: 筛选条件
        config: 图表配置
    
    返回:
        Plotly Figure
    """
    config = config or {}
    
    # 1. 数据准备
    rec_df = pd.DataFrame([{
        'code': r['code'],
        'name': r['name'],
        'sector': r['sector'],
        'pl_ratio': r['scores']['pl_ratio'],
        'confidence': r.get('technical_quality', {}).get('factor', 1.0),
        'fundamental': r['scores']['fundamental'],
        'recommendation': r['recommendation']
    } for r in recommended])
    
    all_df = pd.DataFrame([{
        'code': r['code'],
        'pl_ratio': r['scores']['pl_ratio'],
        'confidence': r.get('technical_quality', {}).get('factor', 1.0),
        'fundamental': r['scores']['fundamental']
    } for r in all_results])
    
    # 2. 创建子图
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=['筛选条件', '盈亏比对比', '置信度对比', '基本面评分对比'],
        specs=[
            [{'type': 'table'}, {'type': 'histogram'}],
            [{'type': 'histogram'}, {'type': 'histogram'}]
        ],
        vertical_spacing=0.15,
        horizontal_spacing=0.12,
        row_heights=[0.3, 0.7]
    )
    
    # 2.1 筛选条件表格
    if criteria:
        criteria_rows = [[k, str(v)] for k, v in criteria.items()]
    else:
        criteria_rows = [['条件', '值'], ['-', '-']]
    
    fig.add_trace(go.Table(
        header=dict(values=['条件', '值'], fill_color='royalblue', font=dict(color='white')),
        cells=dict(values=list(zip(*criteria_rows))),
        columnwidth=[100, 200]
    ), row=1, col=1)
    
    # 2.2 盈亏比分布对比
    fig.add_trace(go.Histogram(
        x=all_df['pl_ratio'],
        name='全部标的',
        marker_color='lightgray',
        opacity=0.6,
        nbinsx=20,
        hovertemplate='全部: %{x:.1f}x<extra></extra>'
    ), row=1, col=2)
    
    fig.add_trace(go.Histogram(
        x=rec_df['pl_ratio'],
        name='推荐标的',
        marker_color='#2ca02c',
        opacity=0.8,
        nbinsx=20,
        hovertemplate='推荐: %{x:.1f}x<extra></extra>'
    ), row=1, col=2)
    
    # 2.3 置信度分布对比
    fig.add_trace(go.Histogram(
        x=all_df['confidence'],
        name='全部',
        marker_color='lightgray',
        opacity=0.6,
        nbinsx=20
    ), row=2, col=1)
    
    fig.add_trace(go.Histogram(
        x=rec_df['confidence'],
        name='推荐',
        marker_color='#1f77b4',
        opacity=0.8,
        nbinsx=20
    ), row=2, col=1)
    
    # 2.4 基本面评分对比
    fig.add_trace(go.Histogram(
        x=all_df['fundamental'],
        name='全部',
        marker_color='lightgray',
        opacity=0.6,
        nbinsx=20
    ), row=2, col=2)
    
    fig.add_trace(go.Histogram(
        x=rec_df['fundamental'],
        name='推荐',
        marker_color='#9467bd',
        opacity=0.8,
        nbinsx=20
    ), row=2, col=2)
    
    # 3. 布局优化
    fig.update_layout(
        title=config.get('title', f"🔍 筛选结果面板 (推荐: {len(rec_df)}/{len(all_df)} 只)"),
        height=config.get('height', 700),
        width=config.get('width', 1200),
        template=config.get('template', 'plotly_white'),
        hovermode='closest',
        barmode='overlay',
        legend=dict(orientation='h', yanchor='bottom', y=-0.1, xanchor='center', x=0.5)
    )
    
    # 4. 添加统计注释
    stats_text = (
        f"推荐标的平均: 盈亏比 {rec_df['pl_ratio'].mean():.2f}x | "
        f"置信度 {rec_df['confidence'].mean():.3f} | "
        f"基本面 {rec_df['fundamental'].mean():.1f} 分"
    )
    fig.add_annotation(
        x=0.5, y=-0.05,
        text=stats_text,
        showarrow=False,
        bgcolor='lightyellow',
        font=dict(size=10),
        xref='paper', yref='paper'
    )
    
    return fig