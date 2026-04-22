#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FactorBreakdown：三维因子贡献分解组件
功能：
  - 可视化技术/基本面/宏观面因子对基准(1.0)的偏离
  - 显示加权贡献度与合成路径
  - 支持悬停查看详情
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, Optional
from ..utils.color_scales import DIMENSION_COLORS, CONFIDENCE_LEVEL_COLORS

def create_factor_breakdown(
    technical: float,
    fundamental: float,
    macro: float,
    weights: Dict[str, float],
    composite: Optional[float] = None
) -> go.Figure:
    """
    创建因子分解图（偏离度条形图 + 合成路径）
    
    参数:
        technical: 技术面因子 (0.98~1.02)
        fundamental: 基本面因子
        macro: 宏观面因子
        weights: 权重字典 {'technical': 0.4, 'fundamental': 0.35, 'macro': 0.25}
        composite: 复合因子（可选，默认自动计算）
    
    返回:
        Plotly Figure
    """
    if composite is None:
        w_t = weights.get('technical', 0.4)
        w_f = weights.get('fundamental', 0.35)
        w_m = weights.get('macro', 0.25)
        composite = (technical**w_t) * (fundamental**w_f) * (macro**w_m)
    
    # 计算偏离中性(1.0)的贡献
    factors = {'技术面': technical, '基本面': fundamental, '宏观面': macro}
    deviations = {k: v - 1.0 for k, v in factors.items()}
    contributions = {k: dev * weights.get({'技术面':'technical','基本面':'fundamental','宏观面':'macro'}[k], 0.33) 
                     for k, dev in deviations.items()}
    
    # 准备数据
    df = pd.DataFrame({
        '因子': list(factors.keys()),
        '因子值': list(factors.values()),
        '偏离度': list(deviations.values()),
        '加权贡献': list(contributions.values()),
        '权重': [weights.get('technical', 0.4), weights.get('fundamental', 0.35), weights.get('macro', 0.25)]
    })
    
    # 创建子图
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=['因子偏离度（相对中性 1.0）', '加权贡献分解'],
        vertical_spacing=0.15,
        row_heights=[0.6, 0.4]
    )
    
    # 1. 偏离度条形图（上行）
    colors_dev = [CONFIDENCE_LEVEL_COLORS['high'] if d>0 else CONFIDENCE_LEVEL_COLORS['low'] if d<0 else '#7f7f7f' for d in df['偏离度']]
    
    fig.add_trace(go.Bar(
        x=df['因子'],
        y=df['偏离度'],
        marker_color=colors_dev,
        name='偏离度',
        hovertemplate='<b>%{x}</b><br>因子值: %{customdata[0]:.3f}<br>偏离中性: %{y:+.3%}<br>权重: %{customdata[1]:.0%}<extra></extra>',
        customdata=df[['因子值', '权重']].values
    ), row=1, col=1)
    
    # 添加中性参考线
    fig.add_hline(y=0, line_dash='dash', line_color='gray', line_width=2, row=1, col=1)
    
    # 2. 加权贡献瀑布图（下行）
    # 构造瀑布数据: 起点1.0 → 技术贡献 → 基本面贡献 → 宏观贡献 → 最终复合
    waterfall_x = ['起点(1.0)', '技术面', '基本面', '宏观面', '合成结果']
    waterfall_y = [1.0, contributions['技术面'], contributions['基本面'], contributions['宏观面'], composite]
    waterfall_measure = ['absolute', 'relative', 'relative', 'relative', 'total']
    
    fig.add_trace(go.Waterfall(
        x=waterfall_x,
        y=waterfall_y,
        measure=waterfall_measure,
        text=[f'{v:.3f}' for v in waterfall_y],
        textposition='outside',
        connector={'line': {'color': 'gray', 'width': 1}},
        increasing={'marker': {'color': '#2ca02c'}},
        decreasing={'marker': {'color': '#d62728'}},
        totals={'marker': {'color': '#1f77b4'}},
        hovertemplate='<b>%{x}</b><br>值: %{y:.3f}<extra></extra>'
    ), row=2, col=1)
    
    # 布局优化
    fig.update_layout(
        height=450,
        margin=dict(l=30, r=30, t=60, b=30),
        showlegend=False,
        hovermode='x unified',
        yaxis1=dict(tickformat='.1%', title='偏离中性幅度', range=[min(-0.05, df['偏离度'].min()-0.01), max(0.05, df['偏离度'].max()+0.01)]),
        yaxis2=dict(visible=False)  # 隐藏瀑布图Y轴（由数据自解释）
    )
    
    return fig