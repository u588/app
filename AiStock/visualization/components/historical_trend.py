#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HistoricalTrend：置信度历史趋势组件
功能：
  - 绘制因子/得分随时间变化曲线
  - 背景分色标注高/中/低置信区间
  - 标记置信度等级切换点
  - 支持双Y轴对比（因子 vs 盈亏比/波动率）
"""

import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import Optional
from ..utils.color_scales import CONFIDENCE_LEVEL_COLORS

def create_historical_trend(
    historical_confidence: pd.DataFrame,
    secondary_metric: Optional[str] = 'pl_ratio',
    window: int = 5
) -> go.Figure:
    """
    创建历史趋势图
    
    参数:
        historical_confidence: DataFrame 包含 ['date', 'factor', 'score', 'level', 可选 secondary_metric]
        secondary_metric: 次要指标列名（如 pl_ratio, volatility）
        window: 移动平均窗口（平滑噪声）
    
    返回:
        Plotly Figure
    """
    df = historical_confidence.copy()
    if 'date' not in df.columns:
        df['date'] = pd.to_datetime(df.index) if df.index.name == 'date' else pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='D')
    df = df.sort_values('date').reset_index(drop=True)
    
    if df.empty:
        return go.Figure().add_annotation(text="无历史数据", showarrow=False)
    
    # 创建双轴子图
    fig = go.Figure()
    
    # 1. 添加置信区间背景色带
    fig.add_hrect(y0=1.01, y1=1.02, fillcolor="rgba(44,160,44,0.15)", line_width=0, annotation_text="高置信")
    fig.add_hrect(y0=0.99, y1=1.01, fillcolor="rgba(31,119,180,0.10)", line_width=0, annotation_text="中置信")
    fig.add_hrect(y0=0.98, y1=0.99, fillcolor="rgba(214,39,40,0.15)", line_width=0, annotation_text="低置信")
    
    # 2. 绘制因子曲线（主Y轴）
    df['factor_ma'] = df['factor'].rolling(window, min_periods=1).mean()
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['factor_ma'],
        mode='lines+markers',
        name='置信度因子(MA)',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=4, color='#1f77b4'),
        hovertemplate='<b>因子</b><br>%{x|%Y-%m-%d}<br>值: %{y:.3f}<extra></extra>'
    ))
    
    # 3. 绘制原始因子点（辅助观察噪声）
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['factor'],
        mode='markers',
        name='原始因子',
        marker=dict(size=3, color='#1f77b4', opacity=0.4),
        hoverinfo='skip',
        showlegend=False
    ))
    
    # 4. 标记等级切换点
    level_changes = df['level'].ne(df['level'].shift())
    change_dates = df.loc[level_changes, 'date']
    change_levels = df.loc[level_changes, 'level']
    
    colors_map = {'high': '#2ca02c', 'normal': '#1f77b4', 'low': '#d62728'}
    for _, row in df.loc[level_changes].iterrows():
        fig.add_vline(
            x=row['date'], line_dash='dot', line_color=colors_map.get(row['level'], 'gray'), line_width=2,
            opacity=0.6
        )
    
    # 5. 次要指标（右Y轴，可选）
    if secondary_metric and secondary_metric in df.columns:
        df[f'{secondary_metric}_ma'] = df[secondary_metric].rolling(window, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=df['date'], y=df[f'{secondary_metric}_ma'],
            mode='lines',
            name=f'{secondary_metric}(MA)',
            line=dict(color='#ff7f0e', width=2, dash='dash'),
            yaxis='y2',
            hovertemplate=f'<b>{secondary_metric}</b><br>%{{x|%Y-%m-%d}}<br>值: %{{y:.2f}}<extra></extra>'
        ))
        fig.update_layout(yaxis2=dict(title=secondary_metric.upper(), overlaying='y', side='right', tickformat='.1f'))
    
    # 6. 参考线
    fig.add_hline(y=1.0, line_dash='dash', line_color='black', line_width=1, opacity=0.7, annotation_text='中性基准(1.0)')
    
    # 布局
    fig.update_layout(
        height=400,
        margin=dict(l=40, r=40, t=50, b=30),
        hovermode='x unified',
        xaxis_title='日期',
        yaxis=dict(title='置信度因子', range=[0.975, 1.025], tickformat='.3f'),
        legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
        template='plotly_white'
    )
    
    return fig