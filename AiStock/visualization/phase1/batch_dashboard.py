#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BatchDashboard：批量对比仪表板组件
功能：
  - 多标的组合分布可视化
  - 支持板块/建议/盈亏比多维度筛选
  - 交互式悬停 + 图例切换
"""

import plotly.graph_objects as go
from typing import Dict, List, Optional, Any, Union
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from ..utils.color_scales import CONFIDENCE_LEVEL_COLORS, RECOMMENDATION_COLORS

def create_batch_dashboard(
    # results: List[Dict[str, Any]],
    results: Union[List[Dict], pd.DataFrame],
    config: Optional[Dict] = None
) -> go.Figure:
    """
    创建批量对比仪表板
    
    参数:
        results: 批量计算结果列表
        config: 图表配置（可选）
    
    返回:
        Plotly Figure
    """
    config = config or {}

    # ✅ 新增：自动类型转换
    if isinstance(results, pd.DataFrame):
        if results.empty: return go.Figure()
        results = results.to_dict('records')
    
    if not results:
        return go.Figure().add_annotation(text="无数据", showarrow=False)
    
    # 1. 数据预处理
    df = pd.DataFrame([{
        'code': r['code'],
        'name': r['name'],
        'sector': r['sector'],
        'entry': r['prices']['entry'],
        'stop': r['prices']['stop_loss'],
        'target': r['prices']['target'],
        'pl_ratio': r['scores']['pl_ratio'],
        'fundamental': r['scores']['fundamental'],
        'confidence': r.get('technical_quality', {}).get('factor', 1.0),
        'recommendation': r['recommendation'],
        'risk': r['prices']['entry'] - r['prices']['stop_loss'],
        'reward': r['prices']['target'] - r['prices']['entry']
    } for r in results])
    
    # 2. 创建 2×2 子图布局
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=['板块分布', '建议分布', '盈亏比分布', '置信度分布'],
        specs=[
            [{'type': 'pie'}, {'type': 'pie'}],
            [{'type': 'histogram'}, {'type': 'histogram'}]
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    # 2.1 板块分布饼图
    sector_counts = df['sector'].value_counts()
    fig.add_trace(go.Pie(
        labels=sector_counts.index,
        values=sector_counts.values,
        name='板块',
        textinfo='label+percent',
        textposition='auto',
        insidetextfont=dict(size=9),
        hovertemplate='<b>%{label}</b><br>数量：%{value}<extra></extra>'
    ), row=1, col=1)
    
    # 2.2 建议分布饼图
    rec_counts = df['recommendation'].value_counts()
    colors = [RECOMMENDATION_COLORS.get(k, '#7f7f7f') for k in rec_counts.index]
    fig.add_trace(go.Pie(
        labels=rec_counts.index,
        values=rec_counts.values,
        marker_colors=colors,
        name='建议',
        textinfo='label+percent',
        insidetextfont=dict(size=9),
        hovertemplate='<b>%{label}</b><br>数量：%{value}<extra></extra>'
    ), row=1, col=2)
    
    # 2.3 盈亏比直方图
    fig.add_trace(go.Histogram(
        x=df['pl_ratio'],
        name='盈亏比',
        marker_color='#1f77b4',
        nbinsx=20,
        hovertemplate='<b>盈亏比</b><br>%{x:.1f}x<extra></extra>'
    ), row=2, col=1)
    
    # 添加参考线
    fig.add_vline(x=2.0, line_dash='dash', line_color='blue', 
                  annotation_text='阈值', annotation_position='top right',
                  row=2, col=1)
    
    # 2.4 置信度直方图
    fig.add_trace(go.Histogram(
        x=df['confidence'],
        name='置信度',
        marker_color='#2ca02c',
        nbinsx=20,
        hovertemplate='<b>置信度</b><br>%{x:.3f}<extra></extra>'
    ), row=2, col=2)
    
    fig.add_vline(x=1.0, line_dash='dash', line_color='gray',
                  annotation_text='中性', annotation_position='top right',
                  row=2, col=2)
    
    # 3. 统一布局
    fig.update_layout(
        title=config.get('title', f"📊 批量标的对比分析 ({len(df)} 只)"),
        height=config.get('height', 800),
        width=config.get('width', 1400),
        template=config.get('template', 'plotly_white'),
        hovermode='closest',
        showlegend=False,
        margin=dict(l=40, r=40, t=60, b=50)
    )
    
    # 4. 添加全局指标卡片
    metrics_text = (
        f"平均盈亏比: {df['pl_ratio'].mean():.2f}x | "
        f"高置信度: {sum(df['confidence']>=1.01)} 只 | "
        f"强烈推荐: {sum(df['recommendation']=='强烈推荐')} 只"
    )
    fig.add_annotation(
        x=0.5, y=-0.04,
        text=metrics_text,
        showarrow=False,
        bgcolor='rgba(240,240,240,0.9)',
        font=dict(size=11),
        xref='paper', yref='paper'
    )
    
    return fig


def create_risk_return_scatter(
    results: List[Dict[str, Any]],
    config: Optional[Dict] = None
) -> go.Figure:
    """
    创建风险 - 收益散点图
    
    参数:
        results: 批量计算结果
        config: 图表配置
    
    返回:
        Plotly Figure
    """
    config = config or {}
    
    if not results:
        return go.Figure()
    
    # 准备数据
    df = pd.DataFrame([{
        'code': r['code'],
        'name': r['name'],
        'sector': r['sector'],
        'risk': r['prices']['entry'] - r['prices']['stop_loss'],
        'reward': r['prices']['target'] - r['prices']['entry'],
        'pl_ratio': r['scores']['pl_ratio'],
        'confidence': r.get('technical_quality', {}).get('factor', 1.0),
        'recommendation': r['recommendation']
    } for r in results])
    
    # 创建散点图
    fig = px.scatter(
        df,
        x='risk',
        y='reward',
        color='recommendation',
        color_discrete_map=RECOMMENDATION_COLORS,
        size='pl_ratio',
        size_max=30,
        hover_name='name',
        hover_data={
            'code': True,
            'sector': True,
            'pl_ratio': ':.1f',
            'confidence': ':.3f'
        },
        title=config.get('title', '🎯 风险 - 收益分布'),
        labels={'risk': '风险 (入场 - 止损)', 'reward': '预期收益 (目标 - 入场)'}
    )
    
    # 添加参考线
    fig.add_hline(y=0, line_dash='dot', line_color='gray', opacity=0.3)
    fig.add_vline(x=0, line_dash='dot', line_color='gray', opacity=0.3)
    
    # 添加盈亏比等值线
    for ratio in [1.5, 2.0, 3.0]:
        fig.add_trace(go.Scatter(
            x=[0, 10],
            y=[0, 10 * ratio],
            mode='lines',
            line=dict(dash='dash', color='gray', width=1),
            name=f'{ratio}x',
            showlegend=False,
            hoverinfo='skip'
        ))
    
    # 布局优化
    fig.update_layout(
        height=config.get('height', 500),
        width=config.get('width', 900),
        template=config.get('template', 'plotly_white'),
        hovermode='closest',
        legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5)
    )
    
    return fig